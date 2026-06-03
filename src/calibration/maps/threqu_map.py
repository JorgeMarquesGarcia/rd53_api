from __future__ import annotations
from typing import Union
from rd53_api.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from rd53_api.calibration.maps.base_map import BaseCalibrationMap

class ThresholdEqualizationMap(BaseCalibrationMap): 
    def __init__(self):
        self._nevents = 100
        self._nevtsburst = self._nevents
        self._ntriggers = 10
        self._injtype = 1
        self._resetmask = 0
        self._vcal_hstart = 100
        self._vcal_hstop = 600
    
    @property
    def vcal_hstart(self) -> int:
        return self._vcal_hstart
    @vcal_hstart.setter
    def vcal_hstart(self, value: int) -> None:
        if value < 0 or value > 1000:
            raise ValueError("VCAL High Start out of range.")
        self._vcal_hstart = value
    
    @property
    def vcal_hstop(self) -> int:
        return self._vcal_hstop
    @vcal_hstop.setter
    def vcal_hstop(self, value: int) -> None:
        if value < 0 or value > 1000:
            raise ValueError("VCAL High Stop out of range.")
        if value <= self._vcal_hstart:
            raise ValueError(f"VCAL High Stop ({value}) must be greater than VCAL High Start ({self._vcal_hstart}).")
        self._vcal_hstop = value
    
    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.VCAL_START: self._vcal_hstart,
            CalibrationSettings.VCAL_STOP: self._vcal_hstop,
        }