"""detector_planes.py — Dibujo 3D de los planos del detector (matplotlib).

Solo pinta: tamaños, offsets y posiciones Z salen de src.chip.detector_geometry.
Lo comparten los plotters de trayectorias (estático e interactivo).

Estilo de diagrama: sin ejes ni rejilla, solo los chips activos como láminas
semitransparentes con algo de grosor, y la vista ajustada a ellos.
"""
from __future__ import annotations

import numpy as np
from matplotlib import colormaps
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from src.chip.detector_geometry import (
    DETECTOR_LAYOUT, TOT_MAX, chip_bounds, detector_extent, z_range,
)

# El rayo cósmico entra por arriba: el eje Z se dibuja invertido (Z=0 arriba)
# y la partícula recorre los planos en Z creciente, de Z_START a Z_END.
# El track se extiende Z_MARGIN más allá de los planos extremos.
Z_MARGIN = 1
Z_START = z_range()[0] - Z_MARGIN
Z_END = z_range()[1] + Z_MARGIN

Z_ASPECT = 420     # altura visual del eje Z frente a columnas y filas (en píxeles)
VIEW_ZOOM = 1.25   # cuánto llena la escena la caja de la figura

# Estilo de los planos
PLANE_THICKNESS = 0.2                  # grosor visual de cada lámina, en unidades de Z
PLANE_FACE_COLOR = (0.55, 0.66, 0.80)  # azul grisáceo
PLANE_EDGE_COLOR = (0.30, 0.40, 0.55)
PLANE_ALPHA = 0.25

# Tracks en un gris neutro: el color de la escena lo reserva el ToT de los impactos
TRACK_COLOR = '#4a4f57'

# Escala de ToT de los impactos: un color por valor, de 0 (azul) a TOT_MAX (rojo).
# RdYlBu (ColorBrewer) es apta para daltónicos y no es un arcoíris.
TOT_CMAP = colormaps['RdYlBu_r'].resampled(TOT_MAX + 1)
TOT_NORM = BoundaryNorm(np.arange(-0.5, TOT_MAX + 1), TOT_CMAP.N)

# Orden de dibujo fijo (computed_zorder=False): matplotlib no tiene buffer de
# profundidad, así que los tracks e impactos se pintan siempre sobre las láminas.
ZORDER_PLANES = 1
ZORDER_TRACK = 3
ZORDER_IMPACT = 5
ZORDER_LABEL = 6


def tot_color(tot: int):
    """Color RGBA de un impacto según su ToT."""
    return TOT_CMAP(TOT_NORM(tot))


def add_tot_colorbar(fig, cax) -> None:
    """Dibuja la barra de color del ToT en los ejes cax."""
    cbar = fig.colorbar(ScalarMappable(norm=TOT_NORM, cmap=TOT_CMAP), cax=cax)
    cbar.set_ticks(range(TOT_MAX + 1))
    cbar.set_label('ToT', fontsize=10)
    cbar.ax.tick_params(labelsize=8, length=0)
    cbar.outline.set_visible(False)


def _active_planes(active_chips):
    """Devuelve [(layer_idx, hybrid_id, lane, z)] de los chips activos."""
    active = set(active_chips)
    active_hybrids = {h for h, _ in active}
    planes = []
    for layer_idx, layer in DETECTOR_LAYOUT.items():
        hybrid_id = layer["hybrid"]
        for lane in layer["chips"]:
            is_active = (hybrid_id in active_hybrids if layer["single"]
                         else (hybrid_id, lane) in active)
            if is_active:
                planes.append((layer_idx, hybrid_id, lane, layer["z_pos"]))
    return planes


def _slab_faces(row_min, row_max, col_min, col_max, z) -> list:
    """Las 6 caras de una lámina centrada en z, en coordenadas (X=col, Y=fila, Z)."""
    z0, z1 = z - PLANE_THICKNESS / 2, z + PLANE_THICKNESS / 2
    c = [(col_min, row_min), (col_max, row_min), (col_max, row_max), (col_min, row_max)]
    bottom = [(x, y, z0) for x, y in c]
    top = [(x, y, z1) for x, y in c]
    sides = [[bottom[i], bottom[(i + 1) % 4], top[(i + 1) % 4], top[i]] for i in range(4)]
    return [bottom, top] + sides


def draw_detector_planes(ax, active_chips) -> None:
    """Dibuja los chips activos como láminas semitransparentes con grosor.

    active_chips: iterable de (hybrid_id, chip_lane).
    """
    faces = []
    for layer_idx, hybrid_id, lane, z in _active_planes(active_chips):
        row_min, row_max, col_min, col_max = chip_bounds(hybrid_id, lane)
        faces.extend(_slab_faces(row_min, row_max, col_min, col_max, z))
        ax.text(col_max, row_min, z, f'Z{layer_idx}  ({hybrid_id},{lane})   ',
                color=PLANE_EDGE_COLOR, fontsize=9, weight='bold',
                ha='right', va='center', zorder=ZORDER_LABEL)

    if faces:
        # Todas las caras en una sola colección: matplotlib las ordena entre sí
        ax.add_collection3d(Poly3DCollection(
            faces, facecolors=PLANE_FACE_COLOR, edgecolors=PLANE_EDGE_COLOR,
            linewidths=0.6, alpha=PLANE_ALPHA, zorder=ZORDER_PLANES,
        ))


def setup_detector_axes(ax, active_chips=()) -> None:
    """Oculta los ejes y ajusta límites, proporciones y vista a los chips activos."""
    planes = _active_planes(active_chips)
    if planes:
        bounds = [chip_bounds(h, lane) for _, h, lane, _ in planes]
        row_min = min(b[0] for b in bounds)
        row_max = max(b[1] for b in bounds)
        col_min = min(b[2] for b in bounds)
        col_max = max(b[3] for b in bounds)
    else:
        row_min, col_min = 0, 0
        row_max, col_max = detector_extent()

    ax.set_xlim(col_min, col_max)
    ax.set_ylim(row_max, row_min)
    ax.set_zlim(Z_END, Z_START)   # invertido: la entrada (Z_START) queda arriba
    ax.set_box_aspect((col_max - col_min, row_max - row_min, Z_ASPECT), zoom=VIEW_ZOOM)
    ax.set_axis_off()
    ax.computed_zorder = False
    ax.view_init(elev=25, azim=120)
