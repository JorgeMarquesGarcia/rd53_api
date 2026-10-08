from __future__ import annotations
from typing import Union
from src.chip.register_map import CalibrationSettings, FastCmdReg, ChipSettings, Value
from src.calibration.maps.gain_map import GainScanMap

KRUM_CURR_MAX = 511   # KRUM_CURR_LIN es un DAC de 9 bits


class GainOptimizationMap(GainScanMap):
    """Gain optimization: búsqueda binaria de KRUM_CURR_LIN entre krum_start y
    krum_stop haciendo en cada paso un gain scan (mismo barrido que GainScanMap).

    Elige el KRUM con el que el ToT de TargetCharge (media + NSTDEV·σ de los
    píxeles) queda en el máximo (15): cargas mayores saturan el ToT.
    TargetCharge ≈ 11.67·ΔVCal + 64 e⁻; debe caer dentro del barrido de VCal
    (con el de GainScanMap, ΔVCal ≤ 1000, hasta ~11 700 e⁻).
    """

    def __init__(self):
        super().__init__()
        self._target_charge = 10000   # [e⁻]
        self._krum_start = 0
        self._krum_stop = 127

    @property
    def target_charge(self) -> int:
        return self._target_charge
    @target_charge.setter
    def target_charge(self, value: int) -> None:
        if value <= 0:
            raise ValueError("Target charge must be positive.")
        self._target_charge = value

    @property
    def krum_start(self) -> int:
        return self._krum_start
    @krum_start.setter
    def krum_start(self, value: int) -> None:
        if value < 0 or value > KRUM_CURR_MAX:
            raise ValueError("Krummenacher current start out of range.")
        if value >= self._krum_stop:
            raise ValueError(f"Krummenacher current start ({value}) must be less than stop ({self._krum_stop}).")
        self._krum_start = value

    @property
    def krum_stop(self) -> int:
        return self._krum_stop
    @krum_stop.setter
    def krum_stop(self, value: int) -> None:
        if value < 0 or value > KRUM_CURR_MAX:
            raise ValueError("Krummenacher current stop out of range.")
        if value <= self._krum_start:
            raise ValueError(f"Krummenacher current stop ({value}) must be greater than start ({self._krum_start}).")
        self._krum_stop = value

    def to_dict(self) -> dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]:
        settings = super().to_dict()
        settings.update({
            CalibrationSettings.TARGET_CHARGE: self._target_charge,
            CalibrationSettings.KRUM_START: self._krum_start,
            CalibrationSettings.KRUM_STOP: self._krum_stop,
        })
        return settings
