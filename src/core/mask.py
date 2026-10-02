from __future__ import annotations

from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS

class Mask(object):
    # Definition: col[row]
    def __init__(self):
        self.registers = []
        self.enable = []
        self.hitBUS = []
        self.injEN  = []
        self.TDAC   = []

    def reset(self):
        self.enable = [['0' for row in range(SENSOR_ROWS)] for col in range(SENSOR_COLS)]
        self.injEN  = [['0' for row in range(SENSOR_ROWS)] for col in range(SENSOR_COLS)]
    
    def preset(self, source):
        self.enable = [['1' for row in range(SENSOR_ROWS)] for col in range(SENSOR_COLS)]
        self.injEN  = [['1' for row in range(SENSOR_ROWS)] for col in range(SENSOR_COLS)]
        self.hitBUS    = source.hitBUS[:]
        self.registers = source.registers[:]
        self.TDAC      = source.TDAC[:]

    def copy(self, target):
        target.registers = self.registers[:]
        target.enable    = self.enable[:]
        target.hitBUS    = self.hitBUS[:]
        target.injEN     = self.injEN[:]
        target.TDAC      = self.TDAC[:]