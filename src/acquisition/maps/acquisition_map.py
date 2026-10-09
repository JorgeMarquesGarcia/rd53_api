from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, FastCmdReg, ChipSettings, Value
from src.acquisition.maps.base_map import BaseAcquisitionMap

DEFAULT_LATENCY = 33   # LATENCY_CONFIG de las adquisiciones si no se indica otro
LATENCY_MAX = 511      # LATENCY_CONFIG es un registro de 9 bits
DEFAULT_NTRIGGERS = 5  # nTRIGxEvent de las adquisiciones si no se indica otro
NTRIGGERS_MAX = 32     # trigger_id del RD53A: 5 bits (0-31)


class AcquisitionMap(BaseAcquisitionMap):
    def __init__(self, latency: int | None = None, ntriggers: int | None = None):
        """latency:   LATENCY_CONFIG de todos los chips (None = DEFAULT_LATENCY).
        ntriggers: nTRIGxEvent, BX que lee cada trigger (None = DEFAULT_NTRIGGERS).
        """
        self._ntriggers = DEFAULT_NTRIGGERS
        self._save_binary = 1
        self._latency = DEFAULT_LATENCY
        self._injtype = 0
        self._trigger_source = 6
        self._hitor_enable = 1
        self._clkdelay = 180
        if latency is not None:
            self.latency = latency
        if ntriggers is not None:
            self.ntriggers = ntriggers

    @property
    def ntriggers(self) -> int:
        """nTRIGxEvent: BX que lee cada trigger."""
        return self._ntriggers

    @ntriggers.setter
    def ntriggers(self, value: int) -> None:
        if not 1 <= int(value) <= NTRIGGERS_MAX:
            raise ValueError(f"nTRIGxEvent out of range (1-{NTRIGGERS_MAX}): {value}")
        self._ntriggers = int(value)

    @property
    def latency(self) -> int:
        return self._latency

    @latency.setter
    def latency(self, value: int) -> None:
        if not 0 <= int(value) <= LATENCY_MAX:
            raise ValueError(f"LATENCY_CONFIG out of range (0-{LATENCY_MAX}): {value}")
        self._latency = int(value)

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
