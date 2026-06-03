from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)

SENSOR_ROWS = 192
SENSOR_COLS = 400

Z_POSITIONS = {0: 0, 1: 3, 2: 6}


class CoincidencePlotter:
    """Plotter para visualizar trayectorias de partículas a partir de datos filtrados."""

    def __init__(self, plot_coord_data: List[dict], active_chips: List[Tuple] = None):
        self.plot_data = plot_coord_data
        self.active_chips = active_chips or []
        self.track_count = 0
        self.colors = plt.cm.rainbow(np.linspace(0, 1, 20))

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

        plt.ion()
        self.fig = plt.figure(figsize=(12, 9))
        self.ax = self.fig.add_subplot(111, projection='3d')

        self._draw_detector_planes()
        self._setup_axes()

        plt.show(block=False)

    def _active_hybrid_ids(self):
        """Retorna el conjunto de hybrid_ids activos."""
        return set(h for h, _ in self.active_chips)

    def _draw_detector_planes(self):
        """Dibuja todos los planos: inactivos muy transparentes, activos opacos."""
        active_hybrids = self._active_hybrid_ids()
        active_lanes_by_hybrid = {
            hybrid_id: set(lane for h, lane in self.active_chips if h == hybrid_id)
            for hybrid_id in active_hybrids
        }

        sensor_positions = [
            (0, '(h,0)', 0,            SENSOR_COLS,   0,            SENSOR_ROWS,   'lightgreen'),
            (1, '(h,1)', SENSOR_COLS,  2*SENSOR_COLS, 0,            SENSOR_ROWS,   'lightcoral'),
            (2, '(h,2)', SENSOR_COLS,  2*SENSOR_COLS, SENSOR_ROWS,  2*SENSOR_ROWS, 'lightyellow'),
            (3, '(h,3)', 0,            SENSOR_COLS,   SENSOR_ROWS,  2*SENSOR_ROWS, 'lightgray'),
        ]

        # Z=0: sensor único centrado en la matriz 2x2
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

        # Z=1 y Z=2: matriz 2x2, siempre dibujamos todos los sensores
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
        self.ax.set_zlim(7, -1)
        self.ax.set_box_aspect((800, 384, 500))
        self.ax.view_init(elev=25, azim=120)
        self.ax.set_title('Trayectorias de partículas', fontsize=14, weight='bold')

    def plot_single_event(self, event_index: int):
        if event_index >= len(self.plot_data):
            print(f"⚠️  Índice {event_index} fuera de rango")
            return

        event_dict = self.plot_data[event_index]

        if len(event_dict) < 2:
            print(f"⚠️  Evento {event_index}: solo {len(event_dict)} hit(s), insuficiente para trazar")
            return

        self._plot_trajectory(event_dict, event_label=f"Event #{event_index}")

    def plot_multiple_events(self, event_indices: List[int] = None, max_events: int = None):
        if event_indices is None:
            n = len(self.plot_data)
            if max_events is not None:
                n = min(n, max_events)
            event_indices = list(range(n))

        for idx in event_indices:
            if idx < len(self.plot_data):
                self.plot_single_event(idx)

    def _plot_trajectory(self, event_dict: dict, event_label: str = None):
        x_coords, y_coords, z_coords, colors_list = [], [], [], []

        for (hybrid_id, chip_lane), (row, col) in event_dict.items():
            x_coords.append(col)
            y_coords.append(row)
            z_coords.append(Z_POSITIONS[hybrid_id])
            colors_list.append(
                self.chip_colors.get((hybrid_id, chip_lane), (0.5, 0.5, 0.5))
            )

        x = np.array(x_coords, dtype=float)
        y = np.array(y_coords, dtype=float)
        z = np.array(z_coords, dtype=float)

        try:
            x_poly = np.poly1d(np.polyfit(z, x, 1))
            y_poly = np.poly1d(np.polyfit(z, y, 1))
        except Exception as e:
            print(f"❌ Error ajustando trayectoria: {e}")
            return

        z_ext = np.linspace(-1, 7, 100)
        x_ext = x_poly(z_ext)
        y_ext = y_poly(z_ext)

        track_color = self.colors[self.track_count % len(self.colors)]
        label = event_label or f'Track #{self.track_count + 1}'

        self.ax.plot(x_ext, y_ext, z_ext,
                     color=track_color, linewidth=2, alpha=0.7, label=label)
        self.ax.scatter(x, y, z,
                        c=colors_list, s=100, alpha=0.95,
                        edgecolors='black', linewidth=1.5)

        self.track_count += 1

        if self.track_count <= 10:
            self.ax.legend(loc='upper right', fontsize=9)

        self.ax.set_title(f'Trayectorias — {self.track_count} tracks',
                          fontsize=14, weight='bold')

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(0.001)

    def save(self, output_dir: Path = None) -> Path:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "plots"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"Coincidence_{timestamp}.png"

        self.fig.suptitle(f'Coincidence Trajectories — {self.track_count} trayectorias',
                          fontsize=14, weight='bold')
        self.fig.tight_layout()
        self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {filepath}")
        return filepath

    def close(self):
        plt.close(self.fig)