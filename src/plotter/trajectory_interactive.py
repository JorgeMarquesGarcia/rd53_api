from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)

SENSOR_ROWS = 192
SENSOR_COLS = 400

Z_POSITIONS = {0: 0, 1: 3, 2: 6}


class InteractiveCoincidencePlotter:
    """Plotter interactivo con animación de trayectorias de partículas."""

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
        plt.pause(0.1)

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
        self.ax.set_zlim(7, -1)
        self.ax.set_box_aspect((800, 384, 500))
        self.ax.view_init(elev=25, azim=120)
        self.ax.set_title('Trayectorias de partículas', fontsize=14, weight='bold')

    def _build_trajectory(self, event_dict: dict):
        """Construye los arrays x, y, z y el ajuste lineal a partir del event_dict."""
        x_coords, y_coords, z_coords, colors_list = [], [], [], []

        for (hybrid_id, chip_lane), (row, col) in event_dict.items():
            x_coords.append(col)
            y_coords.append(row)
            z_coords.append(Z_POSITIONS[hybrid_id])
            colors_list.append(self.chip_colors.get((hybrid_id, chip_lane), (0.5, 0.5, 0.5)))

        x = np.array(x_coords, dtype=float)
        y = np.array(y_coords, dtype=float)
        z = np.array(z_coords, dtype=float)

        x_poly = np.poly1d(np.polyfit(z, x, 1))
        y_poly = np.poly1d(np.polyfit(z, y, 1))

        return x, y, z, colors_list, x_poly, y_poly

    def plot_single_event(self, event_index: int, duration: float = 0.5, num_steps: int = 60):
        """Dibuja un evento con animación de la partícula moviéndose."""
        if event_index >= len(self.plot_data):
            print(f"⚠️  Índice {event_index} fuera de rango")
            return

        event_dict = self.plot_data[event_index]

        if len(event_dict) < 2:
            print(f"⚠️  Evento {event_index}: solo {len(event_dict)} hit(s), insuficiente para trazar")
            return

        self._animate_trajectory(event_dict, event_index, duration, num_steps)

    def plot_multiple_events(self, event_indices: List[int] = None, max_events: int = None,
                             duration: float = 0.5, num_steps: int = 60):
        """Anima múltiples eventos secuencialmente."""
        if event_indices is None:
            n = len(self.plot_data)
            if max_events is not None:
                n = min(n, max_events)
            event_indices = list(range(n))

        for idx in event_indices:
            if idx < len(self.plot_data):
                self.plot_single_event(idx, duration=duration, num_steps=num_steps)

    def _animate_trajectory(self, event_dict: dict, event_index: int,
                            duration: float, num_steps: int):
        """Anima la trayectoria de un evento: la partícula entra por Z alto y sale por Z=0."""
        try:
            x, y, z, colors_list, x_poly, y_poly = self._build_trajectory(event_dict)
        except Exception as e:
            print(f"❌ Error construyendo trayectoria: {e}")
            return

        # La partícula entra por Z alto (6) y sale por Z=-1
        z_start = 7
        z_end = -1
        z_ext = np.linspace(z_start, z_end, num_steps)
        x_ext = x_poly(z_ext)
        y_ext = y_poly(z_ext)

        track_color = self.colors[self.track_count % len(self.colors)]

        # Objetos de animación
        traj_line, = self.ax.plot([], [], [], color=track_color, linewidth=2,
                                  alpha=0.7, label=f'Event #{event_index}')
        particle = self.ax.scatter([], [], [], c='white', s=120,
                                   edgecolors='black', linewidth=1.5, zorder=10)

        # Z positions de los detectores activos para detectar impactos
        detector_z_values = sorted(set(Z_POSITIONS[h] for h, _ in event_dict.keys()), reverse=True)
        hit_registered = {zv: False for zv in detector_z_values}

        dt = duration / num_steps

        print(f"🚀 Evento #{event_index} — {len(event_dict)} detectores con hit")

        for i in range(num_steps):
            # Actualizar trayectoria
            traj_line.set_data(x_ext[:i+1], y_ext[:i+1])
            traj_line.set_3d_properties(z_ext[:i+1])

            # Actualizar posición de la partícula
            particle._offsets3d = ([x_ext[i]], [y_ext[i]], [z_ext[i]])

            # Detectar impactos en planos
            current_z = z_ext[i]
            if i > 0:
                prev_z = z_ext[i - 1]
                for det_z in detector_z_values:
                    if not hit_registered[det_z] and prev_z >= det_z > current_z:
                        # Dibujar punto de impacto real (del event_dict)
                        hits_at_z = [
                            (row, col) for (hid, lane), (row, col) in event_dict.items()
                            if Z_POSITIONS[hid] == det_z
                        ]
                        colors_at_z = [
                            self.chip_colors.get((hid, lane), (0.5, 0.5, 0.5))
                            for (hid, lane) in event_dict.keys()
                            if Z_POSITIONS[hid] == det_z
                        ]
                        for (row, col), color in zip(hits_at_z, colors_at_z):
                            self.ax.scatter([col], [row], [det_z],
                                            c=[color], s=100, alpha=0.95,
                                            edgecolors='black', linewidth=1.5)
                        hit_registered[det_z] = True
                        print(f"   💥 Impacto en Z={det_z}: {hits_at_z}")

            self.fig.canvas.draw()
            self.fig.canvas.flush_events()
            time.sleep(dt)

        self.track_count += 1
        if self.track_count <= 10:
            self.ax.legend(loc='upper right', fontsize=9)
        self.ax.set_title(f'Trayectorias — {self.track_count} tracks', fontsize=14, weight='bold')

        print(f"✅ Evento #{event_index} completado\n")

    def save(self, output_dir: Path = None) -> Path:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "plots"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"Coincidence_interactive_{timestamp}.png"

        self.fig.suptitle(f'Coincidence Trajectories — {self.track_count} trayectorias',
                          fontsize=14, weight='bold')
        self.fig.tight_layout()
        self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {filepath}")
        return filepath

    def close(self):
        plt.close(self.fig)