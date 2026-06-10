from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, ChipSettings, Value, FastCmdReg
from src.acquisition.maps.base_map import BaseAcquisitionMap


class PhysicsMap(BaseAcquisitionMap):
    def __init__(self):
        self._triggers = 0
        self._vthresh_lin = 350
        
    
    @property
    def triggers(self) -> int:
        return self._triggers   
    @triggers.setter
    def triggers(self, value: int) -> None:
        if value < 0:
            raise ValueError("Number of triggers must be non-negative.")
        self._triggers = value
    
    @property
    def vthresh_lin(self) -> int:
        return self._vthresh_lin
    @vthresh_lin.setter
    def vthresh_lin(self, value: int) -> None:
        if value < 0 or value > 1000:
            raise ValueError("Vthreshold_LIN out of range.")
        self._vthresh_lin = value
    
    def to_dict(self) -> dict[Union[FastCmdReg, ChipSettings, CalibrationSettings], Value]:
        return {
            FastCmdReg.NUM_TRIGGERS: self._triggers,
            ChipSettings.VTHRESHOLD_LIN: self._vthresh_lin,
        }

        