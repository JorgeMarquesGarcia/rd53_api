"""calibration_view.py - Lógica común para mostrar resultados de calibración.

La usan CalibrationTab (tras un scan) y AnalysisTab (al abrir un .root):
  - discover_chips():           chips (hybrid, chip) que contiene un fichero ROOT.
  - build_chip_plots_widget():  rejilla de plots de un análisis para un chip.

Los sufijos de nombre de fichero (SCurve, NoiseScan, ...) viven en
src.core.results_finder (ANALYSIS_FILE_SUFFIX).
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Callable

from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QScrollArea
from PyQt5.QtCore import Qt

# plotter_base debe importarse antes que ROOT (fija batch mode y backend Qt)
from src.plotter.plotter_base import PlotterBase, ANALYSIS_PLOTS
from src.plotter.heatmap import (
    PixelAlivePlotter, ToT2DPlotter, TDAC2DPlotter, Masked2DPlotter,
)
# Estos imports registran sus plotters en PLOTTER_REGISTRY
from src.plotter import histogram1d as _histogram1d  # noqa: F401
from src.plotter import scurve as _scurve            # noqa: F401
from src.plotter import gain as _gain                # noqa: F401
import ROOT

from src.config.system_config import SystemConfig

logger = logging.getLogger(__name__)

# Nombre de cada canvas dentro del directorio del chip
CANVAS_NAMES = {
    "SCurves":         "D_B(0)_O(0)_H({h})_SCurves_Chip({c})",
    "Threshold1D":     "D_B(0)_O(0)_H({h})_Threshold1D_Chip({c})",
    "ThrEqualization": "D_B(0)_O(0)_H({h})_ThrEqualization_Chip({c})",
    "TDAC1D":          "D_B(0)_O(0)_H({h})_TDAC1D_Chip({c})",
    "TDAC2D":          "D_B(0)_O(0)_H({h})_TDAC2D_Chip({c})",
    "Masked2D":        "D_B(0)_O(0)_H({h})_Masked2D_Chip({c})",
    "PixelAlive":      "D_B(0)_O(0)_H({h})_PixelAlive_Chip({c})",
    "ToT2D":           "D_B(0)_O(0)_H({h})_ToT2D_Chip({c})",
    "ToT1D":           "D_B(0)_O(0)_H({h})_ToT1D_Chip({c})",
    "Gain":            "D_B(0)_O(0)_H({h})_Gain_Chip({c})",
    "SlopeLowQ1D":     "D_B(0)_O(0)_H({h})_SlopeLowQ1D_Chip({c})",
    "InterceptLowQ1D": "D_B(0)_O(0)_H({h})_InterceptLowQ1D_Chip({c})",
    "Chi2DoF1D":       "D_B(0)_O(0)_H({h})_Chi2DoF1D_Chip({c})",
    "KrumCurr":        "D_B(0)_O(0)_H({h})_KrumCurr_Chip({c})",
}

# Plotters que necesitan máscara de región activa (col_start / col_end)
MASKED_PLOTTERS = {
    "PixelAlive": PixelAlivePlotter,
    "ToT2D":      ToT2DPlotter,
    "TDAC2D":     TDAC2DPlotter,
    "Masked2D":   Masked2DPlotter,
}

_OPTICAL_GROUP_DIR = "Detector/Board_0/OpticalGroup_0"
_HYBRID_RE = re.compile(r"^Hybrid_(\d+)$")
_CHIP_RE = re.compile(r"^Chip_(\d+)$")

LogFn = Callable[[str], None]


# ---------------------------------------------------------------------------
# Descubrimiento de chips
# ---------------------------------------------------------------------------
def discover_chips(root_path: str | Path) -> list[tuple[int, int]]:
    """Lista los (hybrid, chip) presentes en el fichero ROOT, ordenados.

    Solo recorre los directorios Detector/Board_0/OpticalGroup_0/Hybrid_*/Chip_*
    (no lee histogramas). Los números son los que aparecen en el propio fichero.

    Raises:
        ValueError: si el fichero no se puede abrir o no tiene la estructura esperada.
    """
    f = ROOT.TFile(str(root_path), "READ")
    if not f or f.IsZombie():
        raise ValueError(f"No se pudo abrir el fichero ROOT: {root_path}")
    try:
        og = f.Get(_OPTICAL_GROUP_DIR)
        if not og:
            raise ValueError(f"'{_OPTICAL_GROUP_DIR}' no existe en {Path(root_path).name}")

        chips: list[tuple[int, int]] = []
        for hkey in og.GetListOfKeys():
            hm = _HYBRID_RE.match(hkey.GetName())
            if not hm:
                continue
            hyb = og.Get(hkey.GetName())
            if not hyb:
                continue
            for ckey in hyb.GetListOfKeys():
                cm = _CHIP_RE.match(ckey.GetName())
                if cm:
                    chips.append((int(hm.group(1)), int(cm.group(1))))

        chips.sort()
        logger.info("Chips en %s: %s", Path(root_path).name, chips)
        return chips
    finally:
        f.Close()


# ---------------------------------------------------------------------------
# Dibujado de un chip
# ---------------------------------------------------------------------------
def build_chip_plots_widget(
    analysis: str,
    root_path: str,
    hybrid: int,
    chip: int,
    col_start: int,
    col_end: int,
    log: LogFn | None = None,
) -> QScrollArea:
    """Construye la rejilla de plots de `analysis` para un (hybrid, chip).

    Si un plot falla, en su lugar se muestra una etiqueta de error y se avisa
    por `log`; el resto de plots se dibujan igualmente.
    """
    def _log(msg: str) -> None:
        logger.warning(msg)
        if log is not None:
            log(msg)

    chip_dir = SystemConfig.get_chip_dir(hybrid=hybrid, chip=chip)
    keys = ANALYSIS_PLOTS.get(analysis, [])

    tab_widget = QWidget()
    grid = QGridLayout(tab_widget)
    grid.setSpacing(8)
    col_count = 2

    if not keys:
        lbl = QLabel(f"No plots defined for analysis '{analysis}'.")
        lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, 0, 0)

    for idx, key in enumerate(keys):
        canvas_tmpl = CANVAS_NAMES.get(key)
        if canvas_tmpl is None:
            continue

        canvas_path = f"{chip_dir}/{canvas_tmpl.format(h=hybrid, c=chip)}"

        try:
            if key in MASKED_PLOTTERS:
                plotter = MASKED_PLOTTERS[key](root_path, canvas_path, col_start, col_end)
            else:
                plotter = PlotterBase.for_key(key, root_path, canvas_path)

            grid.addWidget(plotter.get_canvas(), idx // col_count, idx % col_count)
        except Exception as e:
            lbl = QLabel(f"⚠ Error en '{key}':\n{e}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "color: #B71C1C; background: #1A0000; "
                "border: 1px solid #4A0000; padding: 8px;"
            )
            grid.addWidget(lbl, idx // col_count, idx % col_count)
            _log(f"[WARN] Plot '{key}' (H{hybrid} Chip{chip}): {e}")

    scroll = QScrollArea()
    scroll.setWidget(tab_widget)
    scroll.setWidgetResizable(True)
    return scroll