from __future__ import annotations
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from matplotlib.figure import Figure
from matplotlib.transforms import offset_copy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from src.chip.detector_geometry import to_local, z_position
from src.plotter.detector_planes import (
    TRACK_COLOR, Z_START, Z_END, ZORDER_TRACK, ZORDER_IMPACT, ZORDER_LABEL,
    add_tot_colorbar, draw_detector_planes, setup_detector_axes, tot_color,
)

logger = logging.getLogger(__name__)

ANIMATION_STEPS = 20   # posiciones por track; el ritmo lo marca quien llama a advance()
LABEL_OFFSET_PT = 6    # separación (puntos) entre la bola de impacto y sus coordenadas

# Estilo de los tracks: normal y resaltado (el que se anima o el elegido con highlight())
TRACK_WIDTH = 2
TRACK_ALPHA = 0.8
IMPACT_SIZE = 100
IMPACT_EDGE_WIDTH = 1.5
HIGHLIGHT_TRACK_WIDTH = 3.5
HIGHLIGHT_TRACK_ALPHA = 1.0
HIGHLIGHT_IMPACT_SIZE = 150
HIGHLIGHT_IMPACT_EDGE_WIDTH = 3.5
HIGHLIGHT_ZORDER_LIFT = 0.5   # el track resaltado se pinta sobre los demás


class InteractiveCoincidencePlotter:
    """Plotter 3D de trayectorias de partículas, incrustable en Qt.

    Solo dibuja: no usa pyplot, no duerme y no gestiona tiempos. La animación
    la conduce quien lo usa llamando a start_track() y luego a advance()
    hasta que devuelve False.

    Cada evento es un dict {(hybrid_id, chip_lane): (row, col, tot)}. Las bolas
    de impacto se colorean por ToT, con su barra de color a la derecha.

    Un track a la vez puede estar resaltado: impactos con el contorno grueso,
    línea más gruesa y las coordenadas de cada impacto. El que se está animando
    es siempre el resaltado; highlight() resalta cualquier otro ya dibujado.
    set_track_visible() quita un track del plot o lo vuelve a añadir.

    Flujo de uso:
        plotter = InteractiveCoincidencePlotter()
        widget  = plotter.get_canvas()     # FigureCanvas para insertar en Qt
        plotter.reset(active_chips)
        if plotter.start_track(event_dict):
            while plotter.advance(): ...   # una posición por llamada
        plotter.highlight(0)               # resalta el primer track dibujado
    """

    def __init__(self, num_steps: int = ANIMATION_STEPS):
        self.num_steps = num_steps
        self.track_count = 0
        self.active_chips: List[Tuple] = []

        self.fig = Figure(figsize=(12, 9))
        self.fig.subplots_adjust(left=0, right=0.9, bottom=0, top=0.94)
        self._canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='3d')
        # La barra de ToT vive en sus propios ejes: ax.clear() no la borra
        add_tot_colorbar(self.fig, self.fig.add_axes([0.91, 0.25, 0.015, 0.5]))
        self._anim: dict | None = None   # estado del track que se está animando
        self._tracks: list[dict] = []    # tracks dibujados, en orden: número, evento, línea e impactos
        self._highlighted: int | None = None   # índice en _tracks del track resaltado
        self._hit_labels: list = []      # coordenadas junto a los impactos del track resaltado

        self.reset()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_canvas(self) -> FigureCanvas:
        return self._canvas

    def reset(self, active_chips: List[Tuple] | None = None):
        """Borra todos los tracks y redibuja los planos del detector."""
        if active_chips is not None:
            self.active_chips = list(active_chips)
        self.track_count = 0
        self._anim = None
        self._tracks = []                # ax.clear() ya borra sus líneas e impactos
        self._highlighted = None
        self._hit_labels = []            # ax.clear() ya los elimina
        self.ax.clear()
        draw_detector_planes(self.ax, self.active_chips)
        self._setup_axes()
        self._canvas.draw_idle()

    @property
    def n_tracks(self) -> int:
        """Tracks dibujados o en animación desde reset()."""
        return len(self._tracks)

    def track(self, index: int) -> tuple[int, dict]:
        """(número, evento) del track index, en orden de dibujo."""
        track = self._tracks[index]
        return track["number"], track["event"]

    @property
    def highlighted(self) -> int | None:
        """Índice del track resaltado (None si no hay ninguno)."""
        return self._highlighted

    def highlight(self, index: int | None) -> None:
        """Resalta el track index (orden de dibujo); None quita el resaltado."""
        self._set_highlight(index)
        self._canvas.draw_idle()

    def is_track_visible(self, index: int) -> bool:
        return self._tracks[index]["visible"]

    def set_track_visible(self, index: int, visible: bool) -> None:
        """Quita del plot (visible=False) o vuelve a añadir un track ya dibujado.

        Un track quitado deja de resaltarse, no cuenta en el título y no sale
        en la figura guardada.
        """
        track = self._tracks[index]
        track["visible"] = visible
        if not visible and self._highlighted == index:
            self._set_highlight(None)
        track["line"].set_visible(visible)
        for impact, *_ in track["impacts"]:
            impact.set_visible(visible)
        if self._anim is not None and self._anim["track"] is track:
            self._anim["particle"].set_visible(visible)
        self._update_title()
        self._canvas.draw_idle()

    def start_track(self, event_dict: dict, number: int | None = None) -> bool:
        """Prepara la animación de un track. Devuelve False si no se puede trazar.

        number: número con que se identifica el track (por defecto, su posición
        en el orden de dibujo, desde 1).
        """
        traj = self._prepare(event_dict)
        if traj is None:
            return False
        x_ext, y_ext, z_ext = traj

        traj_line, = self.ax.plot([], [], [], color=TRACK_COLOR, linewidth=TRACK_WIDTH,
                                  alpha=TRACK_ALPHA, zorder=ZORDER_TRACK)
        particle = self.ax.scatter([], [], [], c='white', s=120,
                                   edgecolors='black', linewidth=1.5, zorder=10)
        detector_z_values = self._detector_z_values(event_dict)

        track = self._add_track(event_dict, traj_line, number)
        # El track en curso pasa a ser el resaltado: el anterior vuelve al estilo normal
        self._set_highlight(self.n_tracks - 1)

        self._anim = {
            "track": track,
            "x": x_ext, "y": y_ext, "z": z_ext,
            "line": traj_line,
            "particle": particle,
            "pending_z": detector_z_values,
            "step": 0,
        }
        return True

    def advance(self) -> bool:
        """Dibuja la siguiente posición del track en curso.

        Devuelve True mientras queden posiciones; al terminar cierra el track
        y devuelve False.
        """
        a = self._anim
        if a is None:
            return False

        i = a["step"]
        a["line"].set_data(a["x"][:i + 1], a["y"][:i + 1])
        a["line"].set_3d_properties(a["z"][:i + 1])
        a["particle"]._offsets3d = ([a["x"][i]], [a["y"][i]], [a["z"][i]])

        # Impactos: se dibuja el hit real, con sus coordenadas, al cruzar cada plano con hit
        current_z = a["z"][i]
        for det_z in [zv for zv in a["pending_z"] if zv <= current_z]:
            self._draw_impacts(a["track"], det_z)
            a["pending_z"].remove(det_z)

        a["step"] += 1
        if a["step"] < len(a["z"]):
            self._canvas.draw_idle()
            return True

        a["particle"].remove()
        self._anim = None
        self._finish_track(a["track"])
        return False

    def draw_tracks(self, events: list[dict], numbers: list[int] | None = None) -> int:
        """Dibuja los tracks completos, sin animación, con un único redibujado.

        numbers: número de cada track (como en start_track). Devuelve cuántos
        se han podido trazar.
        """
        if numbers is None:
            numbers = [None] * len(events)
        drawn = 0
        for event_dict, number in zip(events, numbers):
            traj = self._prepare(event_dict)
            if traj is None:
                continue
            line, = self.ax.plot(*traj, color=TRACK_COLOR, linewidth=TRACK_WIDTH,
                                 alpha=TRACK_ALPHA, zorder=ZORDER_TRACK)
            track = self._add_track(event_dict, line, number)
            for det_z in self._detector_z_values(event_dict):
                self._draw_impacts(track, det_z)
            self._finish_track(track, redraw=False)
            drawn += 1
        if drawn:
            self._update_title()
        self._canvas.draw_idle()
        return drawn

    def save(self, output_dir: Path = None) -> Path:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "plots"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"Coincidence_interactive_{timestamp}.png"

        self.fig.suptitle(f'Coincidence Trajectories — {self._shown_count()} trayectorias',
                          fontsize=14, weight='bold')
        self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {filepath}")
        return filepath

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------

    def _setup_axes(self):
        setup_detector_axes(self.ax, self.active_chips)
        self.ax.set_title('Trayectorias de partículas', fontsize=14, weight='bold')

    def _add_track(self, event_dict: dict, line, number: int | None) -> dict:
        """Registra un track dibujado; sus impactos se añaden al dibujarlos."""
        track = {
            "number": number if number is not None else self.n_tracks + 1,
            "event": event_dict,
            "line": line,
            "impacts": [],   # (scatter, (hybrid, lane), (row, col, tot), z) de cada hit
            "visible": True,     # False: quitado del plot con set_track_visible
            "finished": False,   # dibujado del todo (no en animación)
        }
        self._tracks.append(track)
        return track

    def _draw_impacts(self, track: dict, det_z: int):
        """Dibuja los hits reales del track en el plano det_z, coloreados por ToT.

        Si el track es el resaltado, los dibuja resaltados y con sus coordenadas.
        """
        highlighted = (self._highlighted is not None
                       and self._tracks[self._highlighted] is track)
        size, edge_width, lift = self._impact_style(highlighted)
        for (hid, lane), (row, col, tot) in track["event"].items():
            if z_position(hid) != det_z:
                continue
            impact = self.ax.scatter([col], [row], [det_z], c=[tot_color(tot)], s=size,
                                     alpha=0.95, edgecolors='black', linewidth=edge_width,
                                     zorder=ZORDER_IMPACT + lift)
            impact.set_visible(track["visible"])   # quitado durante su animación
            track["impacts"].append((impact, (hid, lane), (row, col, tot), det_z))
            if highlighted:
                self._label_impact(hid, lane, row, col, tot, det_z)

    def _label_impact(self, hid: int, lane: int, row: int, col: int, tot: int, det_z):
        """Rotula un impacto con sus coordenadas locales en el chip (columna, fila) y su ToT."""
        # Desplazamiento en puntos de pantalla: la etiqueta queda junto a la bola
        # sea cual sea la rotación de la vista
        label_offset = offset_copy(self.ax.transData, fig=self.fig,
                                   x=LABEL_OFFSET_PT, y=LABEL_OFFSET_PT, units='points')
        local_row, local_col = to_local(hid, lane, row, col)
        self._hit_labels.append(self.ax.text(
            col, row, det_z, f'({local_col}, {local_row})  ToT {tot}',
            transform=label_offset, fontsize=7, ha='left', va='bottom',
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.7),
            zorder=ZORDER_LABEL,
        ))

    def _set_highlight(self, index: int | None):
        """Pasa el resaltado (estilo y coordenadas) al track index, sin redibujar."""
        for label in self._hit_labels:
            label.remove()
        self._hit_labels = []
        if self._highlighted is not None:
            self._style_track(self._tracks[self._highlighted], highlighted=False)
        self._highlighted = index
        if index is not None:
            track = self._tracks[index]
            self._style_track(track, highlighted=True)
            for _impact, (hid, lane), (row, col, tot), det_z in track["impacts"]:
                self._label_impact(hid, lane, row, col, tot, det_z)

    def _style_track(self, track: dict, highlighted: bool):
        """Aplica el estilo normal o resaltado a la línea y los impactos de un track."""
        size, edge_width, lift = self._impact_style(highlighted)
        line = track["line"]
        line.set_linewidth(HIGHLIGHT_TRACK_WIDTH if highlighted else TRACK_WIDTH)
        line.set_alpha(HIGHLIGHT_TRACK_ALPHA if highlighted else TRACK_ALPHA)
        line.set_zorder(ZORDER_TRACK + lift)
        for impact, *_ in track["impacts"]:
            impact.set_sizes([size])
            impact.set_linewidth(edge_width)
            impact.set_zorder(ZORDER_IMPACT + lift)

    @staticmethod
    def _impact_style(highlighted: bool) -> tuple[float, float, float]:
        """(tamaño, grosor del contorno, elevación del zorder) de los impactos."""
        if highlighted:
            return HIGHLIGHT_IMPACT_SIZE, HIGHLIGHT_IMPACT_EDGE_WIDTH, HIGHLIGHT_ZORDER_LIFT
        return IMPACT_SIZE, IMPACT_EDGE_WIDTH, 0

    def _finish_track(self, track: dict, redraw: bool = True):
        """Cierra un track dibujado; sin redraw no actualiza ni el título ni el canvas."""
        track["finished"] = True
        self.track_count += 1
        if redraw:
            self._update_title()
            self._canvas.draw_idle()

    def _shown_count(self) -> int:
        """Tracks terminados que siguen en el plot (sin los quitados)."""
        return sum(1 for t in self._tracks if t["finished"] and t["visible"])

    def _update_title(self):
        self.ax.set_title(f'Trayectorias — {self._shown_count()} tracks', fontsize=14, weight='bold')

    # ------------------------------------------------------------------
    # Geometría
    # ------------------------------------------------------------------

    def _prepare(self, event_dict: dict):
        """Ajuste lineal del track y trayectoria extendida entre Z_START y Z_END.

        Devuelve (x_ext, y_ext, z_ext) o None si el evento no es trazable.
        """
        if len(event_dict) < 2:
            logger.warning("Evento con %d hit(s): insuficiente para trazar", len(event_dict))
            return None
        if len(self._detector_z_values(event_dict)) < 2:
            # Todos los hits en el mismo plano: el ajuste en Z no está definido
            logger.warning("Evento con hits en un único plano: insuficiente para trazar")
            return None
        try:
            x_poly, y_poly = self._fit(event_dict)
        except Exception as e:
            logger.warning("Error construyendo trayectoria: %s", e)
            return None

        z_ext = np.linspace(Z_START, Z_END, self.num_steps)
        return x_poly(z_ext), y_poly(z_ext), z_ext

    @staticmethod
    def _fit(event_dict: dict):
        coords = list(event_dict.values())
        x = np.array([col for _, col, _ in coords], dtype=float)
        y = np.array([row for row, _, _ in coords], dtype=float)
        z = np.array([z_position(h) for (h, _) in event_dict.keys()], dtype=float)
        return np.poly1d(np.polyfit(z, x, 1)), np.poly1d(np.polyfit(z, y, 1))

    @staticmethod
    def _detector_z_values(event_dict: dict) -> list:
        """Planos con hit, en el orden en que los cruza la partícula (Z creciente)."""
        return sorted(set(z_position(h) for h, _ in event_dict.keys()))
