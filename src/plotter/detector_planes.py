"""detector_planes.py — Dibujo 3D de los planos del detector (matplotlib).

Solo pinta: tamaños, offsets y posiciones Z salen de src.chip.detector_geometry.
Lo comparten los plotters de trayectorias (estático e interactivo).
"""
from __future__ import annotations

import numpy as np

from src.chip.detector_geometry import (
    DETECTOR_LAYOUT, chip_bounds, detector_extent, z_range,
)

# La partícula entra por Z alto y sale por debajo del primer plano:
# el track se extiende Z_MARGIN más allá de los planos extremos.
Z_MARGIN = 1
Z_START = z_range()[1] + Z_MARGIN
Z_END = z_range()[0] - Z_MARGIN

Z_ASPECT = 500   # profundidad visual del eje Z frente a filas y columnas

# Estilo de los planos
QUAD_LANE_COLORS = {0: 'lightgreen', 1: 'lightcoral', 2: 'lightyellow', 3: 'lightgray'}
SINGLE_CHIP_COLOR = 'lightblue'

# Color de los impactos por (hybrid_id, chip_lane)
CHIP_COLORS = {
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


def draw_detector_planes(ax, active_chips) -> None:
    """Dibuja todos los planos: inactivos muy transparentes, activos opacos.

    active_chips: iterable de (hybrid_id, chip_lane).
    """
    active = set(active_chips)
    active_hybrids = {h for h, _ in active}

    for layer_idx, layer in DETECTOR_LAYOUT.items():
        hybrid_id = layer["hybrid"]
        z = layer["z_pos"]

        for lane in layer["chips"]:
            row_min, row_max, col_min, col_max = chip_bounds(hybrid_id, lane)
            xx, yy = np.meshgrid([col_min, col_max], [row_min, row_max])
            zz = np.full_like(xx, z, dtype=float)
            x_mid, y_mid = (col_min + col_max) / 2, (row_min + row_max) / 2

            if layer["single"]:
                is_active = hybrid_id in active_hybrids
                ax.plot_surface(xx, yy, zz, alpha=0.25 if is_active else 0.05,
                                color=SINGLE_CHIP_COLOR)
                if is_active:
                    ax.text(x_mid, y_mid, z + 0.1, f'Z={layer_idx}\n(1 sensor)',
                            color='blue', fontsize=9, ha='center', weight='bold')
            else:
                is_active = (hybrid_id, lane) in active
                ax.plot_surface(xx, yy, zz, alpha=0.30 if is_active else 0.05,
                                color=QUAD_LANE_COLORS[lane])
                if is_active:
                    ax.text(x_mid, y_mid, z + 0.1, f'Z={layer_idx}\n({hybrid_id},{lane})',
                            color='darkgreen', fontsize=8, ha='center', weight='bold')


def setup_detector_axes(ax) -> None:
    """Etiquetas, límites, proporciones y vista de los ejes del detector."""
    n_rows, n_cols = detector_extent()
    ax.set_xlabel('X (columnas)', fontsize=11)
    ax.set_ylabel('Y (filas)', fontsize=11)
    ax.set_zlabel('Z (planos)', fontsize=11)
    ax.set_xlim(0, n_cols)
    ax.set_ylim(n_rows, 0)
    ax.set_zlim(Z_START, Z_END)
    ax.set_box_aspect((n_cols, n_rows, Z_ASPECT))
    ax.view_init(elev=25, azim=120)
