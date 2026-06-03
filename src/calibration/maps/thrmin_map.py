from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, FastCmdReg, ChipSettings, Value
from src.calibration.maps.base_map import BaseCalibrationMap

class ThresholdMinimizationMap(BaseCalibrationMap): 
    def __init__(self):
        self._nevents = 1e7
        self._nevtsburst = 1e4
        self._ntriggers = 10
        self._injtype = 0
        self._resetmask = 0
        self._thr_stop = 400
        self._thr_start = 350
        self._thr_target = 2000
        self._target_occ = 1e-6


    @property
    def thr_start(self) -> int:
        return self._thr_start
    @thr_start.setter
    def thr_start(self, value: int) -> None:
        if value < 330 or value > 400:
            raise ValueError("Threshold Start out of range.")
        self._thr_start = value
    
    @property
    def thr_stop(self) -> int:
        return self._thr_stop
    @thr_stop.setter
    def thr_stop(self, value: int) -> None:
        if value < 330 or value > 400:
            raise ValueError("Threshold Stop out of range.")
        if value <= self._thr_start:
            raise ValueError(f"Threshold Stop ({value}) must be greater than Threshold Start ({self._thr_start}).")
        self._thr_stop = value

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.THR_START: self._thr_start,
            CalibrationSettings.THR_STOP: self._thr_stop,
            CalibrationSettings.THR_TARGET: self._thr_target,
            CalibrationSettings.T_OCCUPANCY: self._target_occ,
        }