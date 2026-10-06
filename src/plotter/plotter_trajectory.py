from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

from src.chip.detector_geometry import z_position
from src.plotter.detector_planes import (
    TRACK_COLOR, Z_START, Z_END, add_tot_colorbar, draw_detector_planes,
    setup_detector_axes, tot_color,
)

logger = logging.getLogger(__name__)


class CoincidencePlotter:
    """Plotter para visualizar trayectorias de partículas a partir de datos filtrados."""

    def __init__(self, plot_coord_data: List[dict], active_chips: List[Tuple] = None):
        self.plot_data = plot_coord_data
        self.active_chips = active_chips or []
        self.track_count = 0

        plt.ion()
        self.fig = plt.figure(figsize=(12, 9))
        self.fig.subplots_adjust(right=0.9)
        self.ax = self.fig.add_subplot(111, projection='3d')
        add_tot_colorbar(self.fig, self.fig.add_axes([0.91, 0.25, 0.015, 0.5]))

        draw_detector_planes(self.ax, self.active_chips)
        self._setup_axes()

        plt.show(block=False)

    def _setup_axes(self):
        setup_detector_axes(self.ax, self.active_chips)
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

        for (hybrid_id, chip_lane), (row, col, tot) in event_dict.items():
            x_coords.append(col)
            y_coords.append(row)
            z_coords.append(z_position(hybrid_id))
            colors_list.append(tot_color(tot))

        x = np.array(x_coords, dtype=float)
        y = np.array(y_coords, dtype=float)
        z = np.array(z_coords, dtype=float)

        try:
            x_poly = np.poly1d(np.polyfit(z, x, 1))
            y_poly = np.poly1d(np.polyfit(z, y, 1))
        except Exception as e:
            print(f"❌ Error ajustando trayectoria: {e}")
            return

        z_ext = np.linspace(Z_START, Z_END, 100)
        x_ext = x_poly(z_ext)
        y_ext = y_poly(z_ext)

        label = event_label or f'Track #{self.track_count + 1}'

        self.ax.plot(x_ext, y_ext, z_ext,
                     color=TRACK_COLOR, linewidth=2, alpha=0.7, label=label)
        self.ax.scatter(x, y, z,
                        c=colors_list, s=100, alpha=0.95,
                        edgecolors='black', linewidth=1.5)

        self.track_count += 1

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