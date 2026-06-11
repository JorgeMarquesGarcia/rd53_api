from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, FastCmdReg, ChipSettings, Value
from src.acquisition.maps.base_map import BaseAcquisitionMap


class AcquisitionMap(BaseAcquisitionMap):
    def __init__(self):
        self._ntriggers = 10
        self._save_binary = 0
        self._latency = 39
        self._injtype = 0
        self._trigger_source = 6
        self._hitor_enable = 1
        self._clkdelay = 180

    def to_dict(self) -> dict[Union[CalibrationSettings, FastCmdReg, ChipSettings], Value]:
        return {
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.SAVE_BINARY: self._save_binary,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.CLK_DELAY: self._clkdelay,
            ChipSettings.LATENCY: self._latency,
            FastCmdReg.TRIGGER_SOURCE: self._trigger_source,
            FastCmdReg.HITOR_ENABLE: self._hitor_enable,
        }