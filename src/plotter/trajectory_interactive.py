from __future__ import annotations
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from matplotlib.figure import Figure
from matplotlib import cm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from src.chip.detector_geometry import z_position
from src.plotter.detector_planes import (
    CHIP_COLORS, Z_START, Z_END, draw_detector_planes, setup_detector_axes,
)

logger = logging.getLogger(__name__)

ANIMATION_STEPS = 20   # posiciones por track; el ritmo lo marca quien llama a advance()


class InteractiveCoincidencePlotter:
    """Plotter 3D de trayectorias de partículas, incrustable en Qt.

    Solo dibuja: no usa pyplot, no duerme y no gestiona tiempos. La animación
    la conduce quien lo usa llamando a start_track() y luego a advance()
    hasta que devuelve False.

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
        self.colors = cm.rainbow(np.linspace(0, 1, 20))
        self.chip_colors = CHIP_COLORS

        self.fig = Figure(figsize=(12, 9))
        self._canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self._anim: dict | None = None   # estado del track que se está animando

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
        self.ax.clear()
        draw_detector_planes(self.ax, self.active_chips)
        self._setup_axes()
        self._canvas.draw_idle()

    def start_track(self, event_dict: dict) -> bool:
        """Prepara la animación de un track. Devuelve False si no se puede trazar."""
        traj = self._prepare(event_dict)
        if traj is None:
            return False
        x_ext, y_ext, z_ext, color = traj

        traj_line, = self.ax.plot([], [], [], color=color, linewidth=2,
                                  alpha=0.7, label=f'Track #{self.track_count}')
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

        # Impactos: se dibuja el hit real al cruzar cada plano con hit
        current_z = a["z"][i]
        for det_z in [zv for zv in a["pending_z"] if zv > current_z]:
            self._draw_impacts(a["event"], det_z)
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
            x_ext, y_ext, z_ext, color = traj
            self.ax.plot(x_ext, y_ext, z_ext, color=color, linewidth=2,
                         alpha=0.7, label=f'Track #{self.track_count}')
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
        setup_detector_axes(self.ax)
        self.ax.set_title('Trayectorias de partículas', fontsize=14, weight='bold')

    def _draw_impacts(self, event_dict: dict, det_z: int):
        """Dibuja los hits reales del evento en el plano det_z."""
        for (hid, lane), (row, col) in event_dict.items():
            if z_position(hid) != det_z:
                continue
            color = self.chip_colors.get((hid, lane), (0.5, 0.5, 0.5))
            self.ax.scatter([col], [row], [det_z], c=[color], s=100, alpha=0.95,
                            edgecolors='black', linewidth=1.5)

    def _finish_track(self, redraw: bool = True):
        self.track_count += 1
        if self.track_count <= 10:
            self.ax.legend(loc='upper right', fontsize=9)
        self.ax.set_title(f'Trayectorias — {self.track_count} tracks', fontsize=14, weight='bold')
        if redraw:
            self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Geometría
    # ------------------------------------------------------------------

    def _prepare(self, event_dict: dict):
        """Ajuste lineal del track y trayectoria extendida entre Z_START y Z_END.

        Devuelve (x_ext, y_ext, z_ext, color) o None si el evento no es trazable.
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
        color = self.colors[self.track_count % len(self.colors)]
        return x_poly(z_ext), y_poly(z_ext), z_ext, color

    @staticmethod
    def _fit(event_dict: dict):
        x = np.array([col for (_, _), (_, col) in event_dict.items()], dtype=float)
        y = np.array([row for (_, _), (row, _) in event_dict.items()], dtype=float)
        z = np.array([z_position(h) for (h, _) in event_dict.keys()], dtype=float)
        return np.poly1d(np.polyfit(z, x, 1)), np.poly1d(np.polyfit(z, y, 1))

    @staticmethod
    def _detector_z_values(event_dict: dict) -> list:
        return sorted(set(z_position(h) for h, _ in event_dict.keys()), reverse=True)
