from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.calibration.maps.base_map import BaseCalibrationMap


class PixelAliveMap(BaseCalibrationMap): 
    def __init__(self):
        self._nevents = 100
        self._nevtsburst = self._nevents
        self._injtype = 1
        self._resetmask = 0
        self._vcal_med = 100
        self._vcal_high = 600
        self._col_start = 128
        self._col_stop = 263
        self._occ_pp = 0.9


    @property
    def vcal_high(self) -> int:
        return self._vcal_high
    @vcal_high.setter
    def vcal_high(self, value: int) -> None:
        if value < 0 or value > 1000:
            raise ValueError("VCAL High out of range.")
        self._vcal_high = value
    
    @property 
    def vcal_med(self) -> int: 
        return self._vcal_med
    @vcal_med.setter
    def vcal_med(self, value: int) -> None:
        if value < 0 or value > 1000:
            raise ValueError("VCAL Medium out of range.")
        if value >= self._vcal_high:
            raise ValueError(f"VCAL Medium ({value}) must be less than VCAL High ({self._vcal_high}).")
        self._vcal_med = value
    
    @property
    def resetmask(self) -> int:
        return self._resetmask
    @resetmask.setter
    def resetmask(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("Reset mask must be 0 or 1.")
        self._resetmask = value

    @property
    def update(self) -> int:
        return self._update
    @update.setter
    def update(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("Update must be 0 (no) or 1 (yes).")
        self._update = value

    @property
    def latency(self) -> int:
        return self._latency
    @latency.setter
    def latency(self, value: int) -> None:
        if value < 0 or value > 255:
            raise ValueError("Latency out of range 8 bits.")
        self._latency = value
    
    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.COL_START: self._col_start,
            CalibrationSettings.COL_STOP: self._col_stop,
            CalibrationSettings.OCC_PP: self._occ_pp,
            ChipSettings.VCAL_H: self._vcal_high,
            ChipSettings.VCAL_M: self._vcal_med,
        }