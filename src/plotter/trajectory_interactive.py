from __future__ import annotations
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from matplotlib.figure import Figure
from matplotlib.transforms import offset_copy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from src.chip.detector_geometry import chip_origin, z_position
from src.plotter.detector_planes import (
    TRACK_COLOR, Z_START, Z_END, ZORDER_TRACK, ZORDER_IMPACT, ZORDER_LABEL,
    add_tot_colorbar, draw_detector_planes, setup_detector_axes, tot_color,
)

logger = logging.getLogger(__name__)

ANIMATION_STEPS = 20   # posiciones por track; el ritmo lo marca quien llama a advance()
LABEL_OFFSET_PT = 6    # separación (puntos) entre la bola de impacto y sus coordenadas


class InteractiveCoincidencePlotter:
    """Plotter 3D de trayectorias de partículas, incrustable en Qt.

    Solo dibuja: no usa pyplot, no duerme y no gestiona tiempos. La animación
    la conduce quien lo usa llamando a start_track() y luego a advance()
    hasta que devuelve False.

    Cada evento es un dict {(hybrid_id, chip_lane): (row, col, tot)}. Las bolas
    de impacto se colorean por ToT, con su barra de color a la derecha.

    Flujo de uso:
        plotter = InteractiveCoincidencePlotter()
        widget  = plotter.get_canvas()     # FigureCanvas para insertar en Qt
        plotter.reset(active_chips)
        if plotter.start_track(event_dict):
            while plotter.advance(): ...   # una posición por llamada
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
        self._hit_labels: list = []      # coordenadas junto a los impactos del último track animado

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
        self._hit_labels = []            # ax.clear() ya los elimina
        self.ax.clear()
        draw_detector_planes(self.ax, self.active_chips)
        self._setup_axes()
        self._canvas.draw_idle()

    def start_track(self, event_dict: dict) -> bool:
        """Prepara la animación de un track. Devuelve False si no se puede trazar."""
        traj = self._prepare(event_dict)
        if traj is None:
            return False
        x_ext, y_ext, z_ext = traj

        # Solo se rotulan los impactos del track en curso: se borran los del anterior
        for label in self._hit_labels:
            label.remove()
        self._hit_labels = []

        traj_line, = self.ax.plot([], [], [], color=TRACK_COLOR, linewidth=2, alpha=0.8,
                                  zorder=ZORDER_TRACK)
        particle = self.ax.scatter([], [], [], c='white', s=120,
                                   edgecolors='black', linewidth=1.5, zorder=10)
        detector_z_values = self._detector_z_values(event_dict)

        self._anim = {
            "event": event_dict,
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
            self._draw_impacts(a["event"], det_z, labels=self._hit_labels)
            a["pending_z"].remove(det_z)

        a["step"] += 1
        if a["step"] < len(a["z"]):
            self._canvas.draw_idle()
            return True

        a["particle"].remove()
        self._anim = None
        self._finish_track()
        return False

    def draw_tracks(self, events: list[dict]) -> int:
        """Dibuja los tracks completos, sin animación, con un único redibujado.

        Devuelve cuántos se han podido trazar.
        """
        drawn = 0
        for event_dict in events:
            traj = self._prepare(event_dict)
            if traj is None:
                continue
            self.ax.plot(*traj, color=TRACK_COLOR, linewidth=2, alpha=0.8, zorder=ZORDER_TRACK)
            for det_z in self._detector_z_values(event_dict):
                self._draw_impacts(event_dict, det_z)
            self._finish_track(redraw=False)
            drawn += 1
        self._canvas.draw_idle()
        return drawn

    def save(self, output_dir: Path = None) -> Path:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "plots"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"Coincidence_interactive_{timestamp}.png"

        self.fig.suptitle(f'Coincidence Trajectories — {self.track_count} trayectorias',
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

    def _draw_impacts(self, event_dict: dict, det_z: int, labels: list | None = None):
        """Dibuja los hits reales del evento en el plano det_z, coloreados por ToT.

        Si se pasa labels, rotula cada impacto con sus coordenadas locales en
        el chip (columna, fila) y su ToT, y añade los textos a esa lista.
        """
        # Desplazamiento en puntos de pantalla: la etiqueta queda junto a la bola
        # sea cual sea la rotación de la vista
        label_offset = offset_copy(self.ax.transData, fig=self.fig,
                                   x=LABEL_OFFSET_PT, y=LABEL_OFFSET_PT, units='points')
        for (hid, lane), (row, col, tot) in event_dict.items():
            if z_position(hid) != det_z:
                continue
            self.ax.scatter([col], [row], [det_z], c=[tot_color(tot)], s=100, alpha=0.95,
                            edgecolors='black', linewidth=1.5, zorder=ZORDER_IMPACT)
            if labels is not None:
                row_off, col_off = chip_origin(hid, lane)
                labels.append(self.ax.text(
                    col, row, det_z, f'({col - col_off}, {row - row_off})  ToT {tot}',
                    transform=label_offset, fontsize=7, ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.7),
                    zorder=ZORDER_LABEL,
                ))

    def _finish_track(self, redraw: bool = True):
        self.track_count += 1
        self.ax.set_title(f'Trayectorias — {self.track_count} tracks', fontsize=14, weight='bold')
        if redraw:
            self._canvas.draw_idle()

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
