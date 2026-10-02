from __future__ import annotations
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from matplotlib.figure import Figure
from matplotlib import cm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

logger = logging.getLogger(__name__)

SENSOR_ROWS = 192
SENSOR_COLS = 400

Z_POSITIONS = {0: 0, 1: 3, 2: 6}

# La partícula entra por Z alto y sale por debajo de Z=0
Z_START = 7
Z_END = -1
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

        self.chip_colors = {
            (0, 0): (0.3, 0.7, 1.0),
            (1, 0): (0.2, 0.8, 0.2),
            (1, 1): (1.0, 0.2, 0.2),
            (1, 2): (1.0, 0.8, 0.0),
            (1, 3): (0.5, 0.5, 0.5),
            (2, 0): (0.3, 0.7, 1.0),
            (2, 1): (0.2, 0.8, 0.2),
            (2, 2): (1.0, 0.2, 0.2),
            (2, 3): (1.0, 0.8, 0.0),
        }

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
        self._draw_detector_planes()
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

    def _active_hybrid_ids(self):
        return set(h for h, _ in self.active_chips)

    def _draw_detector_planes(self):
        """Dibuja todos los planos: inactivos muy transparentes, activos opacos."""
        active_hybrids = self._active_hybrid_ids()
        active_lanes_by_hybrid = {
            hybrid_id: set(lane for h, lane in self.active_chips if h == hybrid_id)
            for hybrid_id in active_hybrids
        }

        sensor_positions = [
            (0, '(h,0)', 0,           SENSOR_COLS,   0,           SENSOR_ROWS,   'lightgreen'),
            (1, '(h,1)', SENSOR_COLS, 2*SENSOR_COLS, 0,           SENSOR_ROWS,   'lightcoral'),
            (2, '(h,2)', SENSOR_COLS, 2*SENSOR_COLS, SENSOR_ROWS, 2*SENSOR_ROWS, 'lightyellow'),
            (3, '(h,3)', 0,           SENSOR_COLS,   SENSOR_ROWS, 2*SENSOR_ROWS, 'lightgray'),
        ]

        # Z=0: sensor único centrado
        z = Z_POSITIONS[0]
        x0, x1 = SENSOR_COLS // 2, SENSOR_COLS // 2 + SENSOR_COLS
        y0, y1 = SENSOR_ROWS // 2, SENSOR_ROWS // 2 + SENSOR_ROWS
        xx, yy = np.meshgrid([x0, x1], [y0, y1])
        is_active = 0 in active_hybrids
        self.ax.plot_surface(xx, yy, np.full_like(xx, z, dtype=float),
                             alpha=0.25 if is_active else 0.05, color='lightblue')
        if is_active:
            self.ax.text((x0 + x1) / 2, (y0 + y1) / 2, z + 0.1,
                         'Z=0\n(1 sensor)', color='blue', fontsize=9,
                         ha='center', weight='bold')

        # Z=1 y Z=2: matriz 2x2
        for hybrid_id in [1, 2]:
            z = Z_POSITIONS[hybrid_id]
            active_lanes = active_lanes_by_hybrid.get(hybrid_id, set())

            for lane, name, x_min, x_max, y_min, y_max, color in sensor_positions:
                xx, yy = np.meshgrid([x_min, x_max], [y_min, y_max])
                is_active = lane in active_lanes
                self.ax.plot_surface(xx, yy, np.full_like(xx, z, dtype=float),
                                     alpha=0.30 if is_active else 0.05, color=color)
                if is_active:
                    label = name.replace('h', str(hybrid_id))
                    self.ax.text((x_min + x_max) / 2, (y_min + y_max) / 2, z + 0.1,
                                 f'Z={hybrid_id}\n{label}', color='darkgreen',
                                 fontsize=8, ha='center', weight='bold')

    def _setup_axes(self):
        self.ax.set_xlabel('X (columnas)', fontsize=11)
        self.ax.set_ylabel('Y (filas)', fontsize=11)
        self.ax.set_zlabel('Z (planos)', fontsize=11)
        self.ax.set_xlim(0, 2 * SENSOR_COLS)
        self.ax.set_ylim(2 * SENSOR_ROWS, 0)
        self.ax.set_zlim(Z_START, Z_END)
        self.ax.set_box_aspect((800, 384, 500))
        self.ax.view_init(elev=25, azim=120)
        self.ax.set_title('Trayectorias de partículas', fontsize=14, weight='bold')

    def _draw_impacts(self, event_dict: dict, det_z: int):
        """Dibuja los hits reales del evento en el plano det_z."""
        for (hid, lane), (row, col) in event_dict.items():
            if Z_POSITIONS[hid] != det_z:
                continue
            color = self.chip_colors.get((hid, lane), (0.5, 0.5, 0.5))
            self.ax.scatter([col], [row], [det_z], c=[color], s=100, alpha=0.95,
                            edgecolors='black', linewidth=1.5)

    def _finish_track(self):
        self.track_count += 1
        if self.track_count <= 10:
            self.ax.legend(loc='upper right', fontsize=9)
        self.ax.set_title(f'Trayectorias — {self.track_count} tracks', fontsize=14, weight='bold')
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
        z = np.array([Z_POSITIONS[h] for (h, _) in event_dict.keys()], dtype=float)
        return np.poly1d(np.polyfit(z, x, 1)), np.poly1d(np.polyfit(z, y, 1))

    @staticmethod
    def _detector_z_values(event_dict: dict) -> list:
        return sorted(set(Z_POSITIONS[h] for h, _ in event_dict.keys()), reverse=True)
