from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, FastCmdReg, ChipSettings, Value
from src.calibration.maps.base_map import BaseCalibrationMap

VCAL_HIGH_MAX = 4095   # VCAL_HIGH es un DAC de 12 bits


class GainScanMap(BaseCalibrationMap):
    def __init__(self):
        self._nevents = 100
        self._nevtsburst = self._nevents
        self._ntriggers = 10
        self._injtype = 1
        self._resetmask = 0
        # Barrido de VCal propio: más amplio que el de SCurve (que usa el del
        # XML) para cubrir el rango de ToT. ΔVCal = VCalH - VCalMED (100 en el XML):
        # 0 → 1000 ΔVCal en 50 pasos. Ajustar viendo dónde satura el ToT.
        self._vcal_hstart = 100
        self._vcal_hstop = 1100
        self._vcal_hstep = 50   # VCalHnsteps: número de pasos
        self._groups = 0

    @property
    def resetmask(self) -> int:
        return self._resetmask
    @resetmask.setter
    def resetmask(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("Reset mask must be 0 or 1.")
        self._resetmask = value

    @property
    def vcal_hstart(self) -> int:
        return self._vcal_hstart
    @vcal_hstart.setter
    def vcal_hstart(self, value: int) -> None:
        if value < 0 or value > VCAL_HIGH_MAX:
            raise ValueError("VCAL High Start out of range.")
        if value >= self._vcal_hstop:
            raise ValueError(f"VCAL High Start ({value}) must be less than VCAL High Stop ({self._vcal_hstop}).")
        self._vcal_hstart = value

    @property
    def vcal_hstop(self) -> int:
        return self._vcal_hstop
    @vcal_hstop.setter
    def vcal_hstop(self, value: int) -> None:
        if value < 0 or value > VCAL_HIGH_MAX:
            raise ValueError("VCAL High Stop out of range.")
        if value <= self._vcal_hstart:
            raise ValueError(f"VCAL High Stop ({value}) must be greater than VCAL High Start ({self._vcal_hstart}).")
        self._vcal_hstop = value

    @property
    def vcal_hstep(self) -> int:
        """Número de pasos del barrido de VCal (VCalHnsteps)."""
        return self._vcal_hstep
    @vcal_hstep.setter
    def vcal_hstep(self, value: int) -> None:
        if value <= 0:
            raise ValueError("VCAL High number of steps must be positive.")
        self._vcal_hstep = value

    @property
    def groups(self) -> int:
        return self._groups
    @groups.setter
    def groups(self, value: int) -> None:
        if value < 0:
            raise ValueError("Number of groups must be positive.")
        self._groups = value

    @property
    def ntriggers(self) -> int:
        return self._ntriggers
    @ntriggers.setter
    def ntriggers(self, value: int) -> None:
        if value <= 1 or value > 29:
            raise ValueError("Number of triggers out of range 1 to 29.")
        self._ntriggers = value

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        return {
            CalibrationSettings.N_EVENTS: self._nevents,
            CalibrationSettings.N_EVTBURST: self._nevtsburst,
            CalibrationSettings.N_TRIGGERS: self._ntriggers,
            CalibrationSettings.INJ_TYPE: self._injtype,
            CalibrationSettings.RST_MASK: self._resetmask,
            CalibrationSettings.VCAL_START: self._vcal_hstart,
            CalibrationSettings.VCAL_STOP: self._vcal_hstop,
            CalibrationSettings.VCAL_STEP: self._vcal_hstep,
            CalibrationSettings.GROUPS: self._groups,
        }
