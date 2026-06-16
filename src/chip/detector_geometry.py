"""detector_geometry.py — Geometría física del detector RD53A.

Fuente única de verdad para la disposición de hybrids, chips y offsets.
Importar desde aquí en cualquier capa (config, GUI, análisis).
NO importar de config_tab ni de acquisition_tab.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Layout del detector
# ---------------------------------------------------------------------------
# Cada entrada describe una capa física del telescopio:
#   hybrid    : identificador del hybrid (0, 1, 2)
#   chips     : chip_ids locales al hybrid (sin offset)
#   rd53_offset: offset que se suma al chip_id local para obtener el rd53_id
#                global que usa CMSITminiDAQ
#   label     : nombre para mostrar en la GUI
#   single    : True si la capa tiene un único sensor (geometría especial Z=0)
#   z_pos     : posición Z física en unidades arbitrarias del telescopio

DETECTOR_LAYOUT: dict[int, dict] = {
    0: {
        "label":       "Layer 0  (Z=0)",
        "hybrid":      0,
        "chips":       [0],
        "rd53_offset": 0,
        "single":      True,
        "z_pos":       0,
    },
    1: {
        "label":       "Layer 1  (Z=1)",
        "hybrid":      1,
        "chips":       [0, 1, 2, 3],
        "rd53_offset": 4,
        "single":      False,
        "z_pos":       3,
    },
    2: {
        "label":       "Layer 2  (Z=2)",
        "hybrid":      2,
        "chips":       [0, 1, 2, 3],
        "rd53_offset": 4,
        "single":      False,
        "z_pos":       6,
    },
}

# ---------------------------------------------------------------------------
# Helpers de consulta — sin dependencias externas
# ---------------------------------------------------------------------------

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
    for layer in DETECTOR_LAYOUT.values():
        if layer["hybrid"] == hybrid_id:
            return chip_id_local + layer["rd53_offset"]
    raise ValueError(f"hybrid_id {hybrid_id} not found in DETECTOR_LAYOUT")


def z_position(hybrid_id: int) -> int:
    """Devuelve la posición Z de un hybrid."""
    for layer in DETECTOR_LAYOUT.values():
        if layer["hybrid"] == hybrid_id:
            return layer["z_pos"]
    raise ValueError(f"hybrid_id {hybrid_id} not found in DETECTOR_LAYOUT")

