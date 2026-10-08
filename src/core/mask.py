from __future__ import annotations

from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS


def _copy_columns(columns: list) -> list:
    """Copia una matriz col[row]: cada columna es una lista nueva (sin aliasing)."""
    return [list(col) for col in columns]


class Mask(object):
    # Definition: col[row]
    def __init__(self):
        self.registers = []
        self.enable = []
        self.hitBUS = []
        self.injEN  = []
        self.TDAC   = []

    def reset(self):
        self.enable = [['0'] * SENSOR_ROWS for _ in range(SENSOR_COLS)]
        self.injEN  = [['0'] * SENSOR_ROWS for _ in range(SENSOR_COLS)]

    def preset(self, source):
        self.enable = [['1'] * SENSOR_ROWS for _ in range(SENSOR_COLS)]
        self.injEN  = [['1'] * SENSOR_ROWS for _ in range(SENSOR_COLS)]
        self.hitBUS    = _copy_columns(source.hitBUS)
        self.registers = source.registers[:]
        self.TDAC      = _copy_columns(source.TDAC)

    def copy(self, target):
        target.registers = self.registers[:]
        target.enable    = _copy_columns(self.enable)
        target.hitBUS    = _copy_columns(self.hitBUS)
        target.injEN     = _copy_columns(self.injEN)
        target.TDAC      = _copy_columns(self.TDAC)
