from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.calibration.maps.base_map import BaseCalibrationMap

class ThresholdEqualizationMap(BaseCalibrationMap):
    def __init__(self):
        self._nevents = 100
        self._nevtsburst = self._nevents
        self._ntriggers = 10
        self._injtype = 1
        self._resetmask = 0
        # Rango de VCal: None = no se toca, manda el valor del XML
        # (VCalHstart / VCalHstop). Solo se escribe si se fija.
        self._vcal_hstart: int | None = None
        self._vcal_hstop: int | None = None

    @property
    def vcal_hstart(self) -> int | None:
        return self._vcal_hstart
    @vcal_hstart.setter
    def vcal_hstart(self, value: int | None) -> None:
        if value is not None and (value < 0 or value > 1000):
            raise ValueError("VCAL High Start out of range.")
        self._vcal_hstart = value

    @property
    def vcal_hstop(self) -> int | None:
        return self._vcal_hstop
    @vcal_hstop.setter
    def vcal_hstop(self, value: int | None) -> None:
        if value is not None:
            if value < 0 or value > 1000:
                raise ValueError("VCAL High Stop out of range.")
            if self._vcal_hstart is not None and value <= self._vcal_hstart:
                raise ValueError(f"VCAL High Stop ({value}) must be greater than VCAL High Start ({self._vcal_hstart}).")
        self._vcal_hstop = value

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        settings: dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value] = {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
        }
        if self._vcal_hstart is not None:
            settings[CalibrationSettings.VCAL_START] = self._vcal_hstart
        if self._vcal_hstop is not None:
            settings[CalibrationSettings.VCAL_STOP] = self._vcal_hstop
        return settings
