"""detector_geometry.py — Geometría física del detector RD53A.

Fuente única de verdad para la disposición de hybrids, chips, tamaño de sensor,
offsets en el plano XY y posiciones Z. Cualquier capa (config, GUI, análisis,
plotters, máscaras) importa de aquí: nadie más redefine estas constantes.

Sin dependencias externas, para poder importarlo desde cualquier capa sin ciclos.

Sistema de coordenadas global, en píxeles:
    X = columna global, Y = fila global, con origen en la esquina del chip
    lane 0 de las capas 2x2.
    Z = posición del plano, en mm desde la capa Z=0 (diseño 3D del telescopio).

Un chip montado girado 180° en su plano ocupa el mismo rectángulo, pero su
píxel local (fila, columna) cae en (SENSOR_ROWS-1-fila, SENSOR_COLS-1-columna)
de ese rectángulo: to_global y to_local aplican el giro.

El alineamiento de cada capa (medido con tracks) desplaza el origen de sus
chips respecto a la posición nominal: lo aplican chip_origin y todo lo que
depende de él (to_global, to_local, chip_bounds).

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
    (todas las capas tienen la lane 0 en la esquina superior izquierda),
    montado girado 180° respecto a ellas y desplazado según su alineamiento.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Chip
# ---------------------------------------------------------------------------
SENSOR_ROWS = 192   # filas por chip RD53A
SENSOR_COLS = 400   # columnas por chip RD53A
TOT_MAX = 14        # ToT máximo del RD53A (4 bits; 15 significa sin hit)

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
#   z_pos       : posición Z física del plano, en mm
#   rotation    : giro de los chips de la capa en su plano, en grados (0 o 180)
#   chip_origins: {lane: (fila, columna)} origen nominal de cada chip en
#                 coordenadas globales, en píxeles
#   alignment   : (fila, columna) en píxeles que se suma a los orígenes
#                 nominales: corrección de alineamiento medida con tracks

def _layer(label: str, hybrid: int, rd53_offset: int, z_pos: float,
           chip_origins: dict[int, tuple[int, int]], rotation: int = 0,
           alignment: tuple[int, int] = (0, 0)) -> dict:
    if rotation not in (0, 180):
        raise ValueError(f"rotation must be 0 or 180 degrees, got {rotation}")
    return {
        "label":        label,
        "hybrid":       hybrid,
        "chips":        list(chip_origins),
        "rd53_offset":  rd53_offset,
        "single":       len(chip_origins) == 1,
        "z_pos":        z_pos,
        "rotation":     rotation,
        "chip_origins": dict(chip_origins),
        "alignment":    tuple(alignment),
    }


# Separación entre planos (diseño 3D del detector)
Z_GAP_LAYER_0_1 = 4.6    # mm
Z_GAP_LAYER_1_2 = 19.0   # mm

# Alineamiento de la capa Z=0 respecto a las 2x2, en píxeles de 50 µm:
# (+21, +31) = (1.05, 1.55) mm, ±3 px. Ajustado con los 10 tracks de 3 planos
# del Run000401 (20 h de cósmicos) que minimizan los residuos de la recta.
# Con 3 planos solo se mide el desalineo relativo: se atribuye a la capa Z=0,
# la montada aparte y girada, y las 2x2 quedan como referencia.
LAYER_0_ALIGNMENT = (21, 31)

DETECTOR_LAYOUT: dict[int, dict] = {
    # La capa de un solo chip está montada girada 180° respecto a las 2x2
    0: _layer("Layer 0  (Z=0)", hybrid=0, rd53_offset=0, z_pos=0.0,
              chip_origins={0: SINGLE_ORIGIN}, rotation=180,
              alignment=LAYER_0_ALIGNMENT),
    1: _layer("Layer 1  (Z=1)", hybrid=1, rd53_offset=4, z_pos=Z_GAP_LAYER_0_1,
              chip_origins=QUAD_ORIGINS),
    2: _layer("Layer 2  (Z=2)", hybrid=2, rd53_offset=4, z_pos=Z_GAP_LAYER_0_1 + Z_GAP_LAYER_1_2,
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


def z_position(hybrid_id: int) -> float:
    """Devuelve la posición Z de un hybrid, en mm."""
    return layer_for_hybrid(hybrid_id)["z_pos"]


def z_range() -> tuple[float, float]:
    """Devuelve (z_min, z_max) de los planos del detector, en mm."""
    zs = [layer["z_pos"] for layer in DETECTOR_LAYOUT.values()]
    return min(zs), max(zs)


def chip_origin(hybrid_id: int, chip_lane: int) -> tuple[int, int]:
    """Origen (fila, columna) del chip en coordenadas globales, en píxeles,
    con el alineamiento de su capa aplicado.

    En una capa de un solo chip el lane no importa: siempre hay un único origen.
    """
    layer = layer_for_hybrid(hybrid_id)
    origins = layer["chip_origins"]
    if len(origins) == 1:
        row, col = next(iter(origins.values()))
    else:
        try:
            row, col = origins[chip_lane]
        except KeyError:
            raise ValueError(
                f"chip_lane {chip_lane} not found in hybrid {hybrid_id}"
            ) from None
    d_row, d_col = layer["alignment"]
    return row + d_row, col + d_col


def _rotate(hybrid_id: int, row: int, col: int) -> tuple[int, int]:
    """Aplica el giro de la capa a (fila, columna) dentro del chip (el giro de 180° es su propio inverso)."""
    if layer_for_hybrid(hybrid_id)["rotation"] == 180:
        return SENSOR_ROWS - 1 - row, SENSOR_COLS - 1 - col
    return row, col


def to_global(hybrid_id: int, chip_lane: int, row: int, col: int) -> tuple[int, int]:
    """Convierte (fila, columna) locales de un chip a coordenadas globales."""
    row_off, col_off = chip_origin(hybrid_id, chip_lane)
    row, col = _rotate(hybrid_id, row, col)
    return row + row_off, col + col_off


def to_local(hybrid_id: int, chip_lane: int, row: int, col: int) -> tuple[int, int]:
    """Convierte (fila, columna) globales a las locales del chip (inversa de to_global)."""
    row_off, col_off = chip_origin(hybrid_id, chip_lane)
    return _rotate(hybrid_id, row - row_off, col - col_off)


def chip_bounds(hybrid_id: int, chip_lane: int) -> tuple[int, int, int, int]:
    """Devuelve (fila_min, fila_max, col_min, col_max) del chip en coordenadas globales."""
    row_off, col_off = chip_origin(hybrid_id, chip_lane)
    return row_off, row_off + SENSOR_ROWS, col_off, col_off + SENSOR_COLS


def detector_extent() -> tuple[int, int]:
    """Devuelve (n_filas, n_columnas) del área que cubren todos los planos."""
    bounds = [chip_bounds(h, lane) for h, lane in all_chip_keys()]
    return max(b[1] for b in bounds), max(b[3] for b in bounds)
