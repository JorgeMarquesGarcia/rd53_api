from __future__ import annotations
from typing import Union
from rd53_api.chip.register_map import CalibrationSettings, FastCmdReg, Value, ChipSettings
from rd53_api.calibration.maps.base_map import BaseCalibrationMap

class NoiseScanMap(BaseCalibrationMap):
    def __init__(self):
        self._nevents = 1e6
        self._nevtsburst = 1e4
        self._ntriggers = 10
        self._injtype = 0
        self._resetmask = 0
        self._occ_pp = 2e-5

    @property
    def resetmask(self) -> int:
        return self._resetmask
    @resetmask.setter
    def resetmask(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("Reset mask must be 0 or 1.")
        self._resetmask = value
    
    @property
    def nevents(self) -> int:
        return self._nevents
    @nevents.setter
    def nevents(self, value: int) -> None:
        if value <= 0: 
            raise ValueError("Number of events must be positive.")
        elif value > 1e7:
            raise Warning("Number of events is quite high; this may lead to long calibration times.")
        self._nevents = value
    
    @property
    def nevtsburst(self) -> int:
        return self._nevtsburst
    @nevtsburst.setter
    def nevtsburst(self, value: int) -> None:
        if value % self._nevents > 1000:
            raise ValueError("Too much difference between number of events and events per burst.")
        self._nevtsburst = value
    
    @property
    def ntriggers(self) -> int:
        return self._ntriggers
    @ntriggers.setter
    def ntriggers(self, value: int) -> None:
        if value <= 1 or value > 29:
            raise ValueError("Number of triggers out of range 1 to 29.")
        self._ntriggers = value
    
    @property
    def occ_pp(self) -> float:
        return self._occ_pp
    @occ_pp.setter
    def occ_pp(self, value: float) -> None:
        if value <= 0 or value > 0.1:
            raise ValueError("Occupancy per pixel must be in range (0, 0.1].")
        self._occ_pp = value
    
    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.OCC_PP: self._occ_pp,
        }