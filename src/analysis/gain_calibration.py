"""gain_calibration.py - Conversión ToT → carga → energía con el Gain scan de Ph2_ACF.

El Gain scan ajusta para cada píxel una recta ToT = intercept + slope·ΔVCal
(canvas SlopeLowQ2D / InterceptLowQ2D del .root; el RD53A no usa doble pendiente).
Aquí se invierte para cada hit:

    ΔVCal   = (ToT - intercept) / slope
    Q [e⁻]  = ELECTRONS_PER_VCAL · ΔVCal + CHARGE_OFFSET      (RD53A::VCal2Charge)
    E [keV] = Q · W_SI / 1000

La calibración solo vale para datos tomados con la misma configuración del chip
(KRUM_CURR_LIN, umbral, TDAC) que el Gain scan. El ToT del ajuste y RD53_hit_tot
son el mismo código de 4 bits (hit.tot en Ph2_ACF).

load_gain_calibration() lee el .root con PyROOT (uproot no sabe leer los TCanvas
de Ph2_ACF); el resto del módulo es numpy puro.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ChipKey = tuple[int, int]   # (hybrid_id, rd53_id), como Hybrid_*/Chip_* en el .root

# ---------------------------------------------------------------------------
# VCal → carga: RD53A::VCal2Charge (Ph2_ACF/HWDescription/RD53A.{h,cc})
# ---------------------------------------------------------------------------
VREF_ADC = 0.9            # [V] VREF_ADC de los <Settings> del XML (900 mV)
VCAL_DAC_RANGE = 4096     # rango del DAC de VCal
INJ_CAPACITANCE = 8.5     # [fF] condensador de inyección
ELEMENTARY_CHARGE = 1.6   # [1e-19 C]
ELECTRONS_PER_VCAL = VREF_ADC / VCAL_DAC_RANGE * INJ_CAPACITANCE * 1e4 / ELEMENTARY_CHARGE  # ≈ 11.67 e⁻
CHARGE_OFFSET = 64        # [e⁻] diferencia de offset entre VCAL_HIGH y VCAL_MED

W_SI = 3.6                # [eV] energía media para crear un par electrón-hueco en silicio

# Canvas de cada chip con el ajuste del Gain scan
_SLOPE_CANVAS = "SlopeLowQ2D"
_INTERCEPT_CANVAS = "InterceptLowQ2D"


def vcal_to_charge(dvcal):
    """ΔVCal → carga [e⁻]."""
    return ELECTRONS_PER_VCAL * dvcal + CHARGE_OFFSET


def charge_to_energy_kev(charge):
    """Carga [e⁻] → energía depositada [keV]."""
    return charge * W_SI / 1000.0


@dataclass
class ChipGain:
    """Ajuste del Gain scan de un chip, con los mapas indexados [fila, columna].

    Un píxel es válido si su pendiente es positiva y finita: Ph2_ACF deja la
    pendiente a 0 en los ajustes fallidos y en los píxeles sin inyectar.
    """
    slope: np.ndarray       # [ToT/ΔVCal]
    intercept: np.ndarray   # [ToT]
    valid: np.ndarray = field(init=False)
    median_slope: float = field(init=False)
    median_intercept: float = field(init=False)

    def __post_init__(self):
        self.valid = np.isfinite(self.slope) & np.isfinite(self.intercept) & (self.slope > 0)
        if self.valid.any():
            self.median_slope = float(np.median(self.slope[self.valid]))
            self.median_intercept = float(np.median(self.intercept[self.valid]))
        else:
            self.median_slope = self.median_intercept = float("nan")

    @property
    def n_valid(self) -> int:
        return int(self.valid.sum())


class GainCalibration:
    """Ajustes del Gain scan por chip: {(hybrid_id, rd53_id): ChipGain}."""

    def __init__(self, chips: dict[ChipKey, ChipGain], source: str = ""):
        self.chips = chips
        self.source = source

    def usable(self, chip: ChipKey) -> bool:
        """True si el chip está en la calibración y tiene algún píxel con ajuste válido."""
        gain = self.chips.get(chip)
        return gain is not None and gain.n_valid > 0

    def to_charge(self, chip: ChipKey, rows, cols, tots) -> tuple[np.ndarray, np.ndarray]:
        """Carga [e⁻] de cada hit y máscara de los hits sin ajuste propio.

        Los píxeles sin ajuste válido usan la recta mediana del chip. Un ToT por
        debajo de la recta (ΔVCal < 0) se toma como ΔVCal = 0.
        """
        gain = self.chips[chip]
        rows = np.asarray(rows, dtype=np.int64)
        cols = np.asarray(cols, dtype=np.int64)
        own = gain.valid[rows, cols]
        slope = np.where(own, gain.slope[rows, cols], gain.median_slope)
        intercept = np.where(own, gain.intercept[rows, cols], gain.median_intercept)
        dvcal = np.clip((np.asarray(tots, dtype=np.float64) - intercept) / slope, 0.0, None)
        return vcal_to_charge(dvcal), ~own


def load_gain_calibration(root_path: str | Path) -> GainCalibration:
    """Lee el ajuste de cada chip de un .root de Gain o GainOptimization (PyROOT).

    Raises:
        ValueError: si el fichero no se puede abrir o no tiene los mapas del ajuste.
    """
    import ROOT
    from src.config.system_config import SystemConfig
    from src.plotter.calibration_view import discover_chips
    from src.plotter.plotter_base import PlotterBase

    root_path = Path(root_path)
    chip_keys = discover_chips(root_path)
    if not chip_keys:
        raise ValueError(f"No chips found in {root_path.name}")

    f = ROOT.TFile(str(root_path), "READ")
    if not f or f.IsZombie():
        raise ValueError(f"Cannot open ROOT file: {root_path}")
    chips: dict[ChipKey, ChipGain] = {}
    try:
        for h, c in chip_keys:
            maps = {}
            for name in (_SLOPE_CANVAS, _INTERCEPT_CANVAS):
                path = f"{SystemConfig.get_chip_dir(hybrid=h, chip=c)}/D_B(0)_O(0)_H({h})_{name}_Chip({c})"
                canvas = f.Get(path)
                hist = None
                if canvas and isinstance(canvas, ROOT.TCanvas):
                    hist = next((p for p in canvas.GetListOfPrimitives()
                                 if p.ClassName().startswith("TH2")), None)
                if hist is None:
                    raise ValueError(f"'{name}' not found for H{h} Chip {c} in {root_path.name}: "
                                     f"is it a Gain scan file?")
                # TH2 (columna, fila) → [fila, columna], como los hits
                maps[name] = PlotterBase._th2_values(hist).T
            gain = ChipGain(slope=maps[_SLOPE_CANVAS], intercept=maps[_INTERCEPT_CANVAS])
            chips[(h, c)] = gain
            logger.info("Gain H%d Chip %d: %d pixels with a valid fit, median slope %.4f ToT/ΔVCal, "
                        "median intercept %.2f ToT", h, c, gain.n_valid,
                        gain.median_slope, gain.median_intercept)
    finally:
        f.Close()
    return GainCalibration(chips, source=str(root_path))
