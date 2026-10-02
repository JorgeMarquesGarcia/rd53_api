"""detector_geometry.py — Geometría física del detector RD53A.

Fuente única de verdad para la disposición de hybrids, chips, tamaño de sensor,
offsets en el plano XY y posiciones Z. Cualquier capa (config, GUI, análisis,
plotters, máscaras) importa de aquí: nadie más redefine estas constantes.

Sin dependencias externas, para poder importarlo desde cualquier capa sin ciclos.

Sistema de coordenadas global, en píxeles:
    X = columna global, Y = fila global, con origen en la esquina del chip
    lane 0 de las capas 2x2.
    Z = posición del plano, en unidades arbitrarias del telescopio.

Vista XY (las filas crecen hacia abajo, como en los plots):

        0                         400                         800   (columnas)
    0   +-------------------------+-------------------------+
        |  lane 0                 |  lane 1                 |
        |  + chip de Z=0          |                         |
  192   +-------------------------+-------------------------+
        |  lane 3                 |  lane 2                 |
        |                         |                         |
  384   +-------------------------+-------------------------+
 (filas)
    Capas Z=1 y Z=2: cuatro chips cada una.
    Capa Z=0: un único chip, alineado con la lane 0 de las capas 2x2
    (todas las capas tienen la lane 0 en la esquina superior izquierda).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Chip
# ---------------------------------------------------------------------------
SENSOR_ROWS = 192   # filas por chip RD53A
SENSOR_COLS = 400   # columnas por chip RD53A

# ---------------------------------------------------------------------------
# Colocación de chips en el plano XY
# ---------------------------------------------------------------------------
# Capa 2x2 (quad): posición de cada lane en unidades de chip, (fila, columna).
QUAD_GRID: dict[int, tuple[int, int]] = {
    0: (0, 0),
    1: (0, 1),
    2: (1, 1),
    3: (1, 0),
}

# Origen (fila, columna) en píxeles de cada chip de una capa 2x2.
QUAD_ORIGINS: dict[int, tuple[int, int]] = {
    lane: (grid_row * SENSOR_ROWS, grid_col * SENSOR_COLS)
    for lane, (grid_row, grid_col) in QUAD_GRID.items()
}

# Capa de un solo chip: alineada con la lane 0 de las capas 2x2, en la
# esquina superior izquierda.
SINGLE_ORIGIN: tuple[int, int] = QUAD_ORIGINS[0]


# ---------------------------------------------------------------------------
# Layout del detector
# ---------------------------------------------------------------------------
# Cada entrada describe una capa física del telescopio:
#   label       : nombre para mostrar en la GUI
#   hybrid      : identificador del hybrid (0, 1, 2)
#   chips       : chip_ids locales al hybrid, sin offset (coinciden con el lane)
#   rd53_offset : offset que se suma al chip_id local para obtener el rd53_id
#                 global que usa CMSITminiDAQ
#   single      : True si la capa tiene un único sensor (geometría especial Z=0)
#   z_pos       : posición Z física en unidades arbitrarias del telescopio
#   chip_origins: {lane: (fila, columna)} origen de cada chip en coordenadas
#                 globales, en píxeles

def _layer(label: str, hybrid: int, rd53_offset: int, z_pos: int,
           chip_origins: dict[int, tuple[int, int]]) -> dict:
    return {
        "label":        label,
        "hybrid":       hybrid,
        "chips":        list(chip_origins),
        "rd53_offset":  rd53_offset,
        "single":       len(chip_origins) == 1,
        "z_pos":        z_pos,
        "chip_origins": dict(chip_origins),
    }


DETECTOR_LAYOUT: dict[int, dict] = {
    0: _layer("Layer 0  (Z=0)", hybrid=0, rd53_offset=0, z_pos=0,
              chip_origins={0: SINGLE_ORIGIN}),
    1: _layer("Layer 1  (Z=1)", hybrid=1, rd53_offset=4, z_pos=3,
              chip_origins=QUAD_ORIGINS),
    2: _layer("Layer 2  (Z=2)", hybrid=2, rd53_offset=4, z_pos=6,
              chip_origins=QUAD_ORIGINS),
}


# ---------------------------------------------------------------------------
# Helpers de consulta — sin dependencias externas
# ---------------------------------------------------------------------------

def layer_for_hybrid(hybrid_id: int) -> dict:
    """Devuelve la entrada de DETECTOR_LAYOUT de un hybrid."""
    for layer in DETECTOR_LAYOUT.values():
        if layer["hybrid"] == hybrid_id:
            return layer
    raise ValueError(f"hybrid_id {hybrid_id} not found in DETECTOR_LAYOUT")


def all_chip_keys() -> list[tuple[int, int]]:
    """Devuelve todos los (hybrid_id, chip_id_local) posibles del detector."""
    return [
        (layer["hybrid"], chip_id)
        for layer in DETECTOR_LAYOUT.values()
        for chip_id in layer["chips"]
    ]


def chip_keys_for_hybrid(hybrid_id: int) -> list[tuple[int, int]]:
    """Devuelve los (hybrid_id, chip_id_local) de un hybrid concreto."""
    for layer in DETECTOR_LAYOUT.values():
        if layer["hybrid"] == hybrid_id:
            return [(hybrid_id, c) for c in layer["chips"]]
    return []


def rd53_id(hybrid_id: int, chip_id_local: int) -> int:
    """Convierte (hybrid_id, chip_id_local) → rd53_id global con offset."""
    return chip_id_local + layer_for_hybrid(hybrid_id)["rd53_offset"]


def z_position(hybrid_id: int) -> int:
    """Devuelve la posición Z de un hybrid."""
    return layer_for_hybrid(hybrid_id)["z_pos"]


def z_range() -> tuple[int, int]:
    """Devuelve (z_min, z_max) de los planos del detector."""
    zs = [layer["z_pos"] for layer in DETECTOR_LAYOUT.values()]
    return min(zs), max(zs)


def chip_origin(hybrid_id: int, chip_lane: int) -> tuple[int, int]:
    """Origen (fila, columna) del chip en coordenadas globales, en píxeles.

    En una capa de un solo chip el lane no importa: siempre hay un único origen.
    """
    origins = layer_for_hybrid(hybrid_id)["chip_origins"]
    if len(origins) == 1:
        return next(iter(origins.values()))
    try:
        return origins[chip_lane]
    except KeyError:
        raise ValueError(
            f"chip_lane {chip_lane} not found in hybrid {hybrid_id}"
        ) from None


def to_global(hybrid_id: int, chip_lane: int, row: int, col: int) -> tuple[int, int]:
    """Convierte (fila, columna) locales de un chip a coordenadas globales."""
    row_off, col_off = chip_origin(hybrid_id, chip_lane)
    return row + row_off, col + col_off


def chip_bounds(hybrid_id: int, chip_lane: int) -> tuple[int, int, int, int]:
    """Devuelve (fila_min, fila_max, col_min, col_max) del chip en coordenadas globales."""
    row_off, col_off = chip_origin(hybrid_id, chip_lane)
    return row_off, row_off + SENSOR_ROWS, col_off, col_off + SENSOR_COLS


def detector_extent() -> tuple[int, int]:
    """Devuelve (n_filas, n_columnas) del área que cubren todos los planos."""
    n_rows = max(r + SENSOR_ROWS for layer in DETECTOR_LAYOUT.values()
                 for r, _ in layer["chip_origins"].values())
    n_cols = max(c + SENSOR_COLS for layer in DETECTOR_LAYOUT.values()
                 for _, c in layer["chip_origins"].values())
    return n_rows, n_cols
