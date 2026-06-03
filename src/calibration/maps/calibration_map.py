from __future__ import annotations
from typing import Union
from rd53_api.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from rd53_api.calibration.maps.base_map import BaseCalibrationMap

class CalibrationMap(BaseCalibrationMap):
    def __init__(self):
        self._latency = 139
        self._nclkdelay = 280
        self._trigger_source = 3
        self._hitor_enable = 0
        self._resettdac = -1
        self._save_binary = 0
        self._update = 1 

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            ChipSettings.LATENCY: self._latency,
            CalibrationSettings.CLK_DELAY: self._nclkdelay,
            FastCmdReg.TRIGGER_SOURCE: self._trigger_source,
            FastCmdReg.HITOR_ENABLE: self._hitor_enable,
            CalibrationSettings.RST_TDAC: self._resettdac,
            CalibrationSettings.SAVE_BINARY: self._save_binary,
            CalibrationSettings.UPDATE: self._update,
        }