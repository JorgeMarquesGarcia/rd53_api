from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.calibration.maps.base_map import BaseCalibrationMap


class LatencyScanMap(BaseCalibrationMap):
    def __init__(self):
        self._nevents = 100
        self._nevtsburst = self._nevents
        self._ntriggers = 10
        self._injtype = 1
        self._resetmask = 0
        self._latency_start = 100
        self._latency_stop = 140
        self._col_start = 128
        self._col_stop = 263
        self._groups = 0
      
    @property
    def nevents(self) -> int:
        return self._nevents
    
    @nevents.setter
    def nevents(self, value: int) -> None:
        if value <= 0: 
            raise ValueError("Number of events must be positive.")
        elif value > 100:
            raise Warning("Number of events is quite high; this may lead to long calibration times.")
        self._nevents = value
    
    @property
    def ntriggers(self) -> int:
        return self._ntriggers
    
    @ntriggers.setter
    def ntriggers(self, value: int) -> None:
        if value <= 1 or value > 29:
            raise ValueError("Number of triggers out of range 1 to 29.")
        self._ntriggers = value
    
    @property
    def latency_start(self) -> int:
        return self._latency_start
    
    @latency_start.setter
    def latency_start(self, value: int) -> None:
        if value < 0 or value > 255:
            raise ValueError("Latency start out of range 8 bits.")
        self._latency_start = value

    @property
    def latency_stop(self) -> int:
        return self._latency_stop
    
    @latency_stop.setter
    def latency_stop(self, value: int) -> None:
        if value < 0 or value > 255:
            raise ValueError("Latency stop out of range 8 bits.")
        if value <= self._latency_start:
            raise ValueError(f"Latency stop ({value}) must be greater than latency start ({self._latency_start}).")
        self._latency_stop = value

    @property
    def groups(self) -> int:
        return self._groups
    @groups.setter
    def groups(self, value: int) -> None:
        if value < 0 :
            raise ValueError("Number of groups must be positive.")
        self._groups = value

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.COL_START: self._col_start,
            CalibrationSettings.COL_STOP: self._col_stop,
            CalibrationSettings.LAT_START: self._latency_start,
            CalibrationSettings.LAT_STOP: self._latency_stop,
            CalibrationSettings.GROUPS: self._groups,
        }
