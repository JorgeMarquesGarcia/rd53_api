"""
test_plotter.py - Test integrado de todos los plotters RD53A.

Uso:
    python3 -m rd53_api.test.test_plotter

Muestra una ventana Qt con tabs por análisis, cada tab con sus figuras.
"""
from __future__ import annotations
import sys
import os
import logging

# ---------------------------------------------------------------------------
# Rutas a los ficheros ROOT de prueba
# ---------------------------------------------------------------------------
ROOT_FILES = {
    "scurve":     "Data/CALIBRATION/scurve/Run000025_SCurve.root",
    "threqu":     "Data/CALIBRATION/threqu/Run000010_ThrEqualization.root",
    "noise":      "Data/CALIBRATION/noise/Run000446_NoiseScan.root",
    "pixelalive": "Data/CALIBRATION/pixelalive/Run000375_PixelAlive.root",
}

CHIP_DIRS = {
    "scurve":     "Detector/Board_0/OpticalGroup_0/Hybrid_0/Chip_0",
    "threqu":     "Detector/Board_0/OpticalGroup_0/Hybrid_2/Chip_0",
    "noise":      "Detector/Board_0/OpticalGroup_0/Hybrid_0/Chip_0",
    "pixelalive": "Detector/Board_0/OpticalGroup_0/Hybrid_0/Chip_0",
}

CANVAS_NAMES = {
    # scurve
    "SCurves":         "D_B(0)_O(0)_H(0)_SCurves_Chip(0)",
    "Threshold1D":     "D_B(0)_O(0)_H(0)_Threshold1D_Chip(0)",
    # threqu
    "ThrEqualization": "D_B(0)_O(0)_H(2)_ThrEqualization_Chip(0)",
    "TDAC1D":          "D_B(0)_O(0)_H(2)_TDAC1D_Chip(0)",
    "TDAC2D":          "D_B(0)_O(0)_H(2)_TDAC2D_Chip(0)",
    "Masked2D":        "D_B(0)_O(0)_H(2)_Masked2D_Chip(0)",
    # noise y pixelalive
    "PixelAlive":      "D_B(0)_O(0)_H(0)_PixelAlive_Chip(0)",
    "ToT2D":           "D_B(0)_O(0)_H(0)_ToT2D_Chip(0)",
    "ToT1D":           "D_B(0)_O(0)_H(0)_ToT1D_Chip(0)",
}

# Rango de columnas activas — en producción viene de SystemConfig
ACTIVE_COL_START = 128
ACTIVE_COL_END   = 263

# Plotters que necesitan máscara de región activa
MASKED_PLOTTERS = {"PixelAlive", "ToT2D", "TDAC2D", "Masked2D"}

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Imports Qt y plotters
# ---------------------------------------------------------------------------
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QGridLayout, QLabel, QScrollArea,
)
from PyQt5.QtCore import Qt

from src.plotter.plotter_base import PlotterBase, ANALYSIS_PLOTS
from src.plotter.heatmap import (
    PixelAlivePlotter, ToT2DPlotter, Threshold2DPlotter,
    Noise2DPlotter, TDAC2DPlotter, Masked2DPlotter,
)
from src.plotter.histogram1d import (
    Threshold1DPlotter, Noise1DPlotter, Occ1DPlotter,
    ToT1DPlotter, TDAC1DPlotter, ThrEqualizationPlotter,
)
from src.plotter.scurve import SCurvePlotter


def build_canvas_path(chip_dir: str, canvas_name: str) -> str:
    return f"{chip_dir}/{canvas_name}"


def make_plotter(key: str, root_path: str, canvas_path: str) -> PlotterBase:
    """Instancia el plotter correcto. Los heatmaps con máscara reciben col_start/col_end."""
    if key in MASKED_PLOTTERS:
        cls = {
            "PixelAlive": PixelAlivePlotter,
            "ToT2D":      ToT2DPlotter,
            "TDAC2D":     TDAC2DPlotter,
            "Masked2D":   Masked2DPlotter,
        }[key]
        return cls(root_path, canvas_path,
                   col_start=ACTIVE_COL_START,
                   col_end=ACTIVE_COL_END)
    return PlotterBase.for_key(key, root_path, canvas_path)


def build_tab(analysis: str) -> QWidget:
    """Construye el widget de un tab con todas las figuras del análisis."""
    root_path = ROOT_FILES.get(analysis)
    chip_dir  = CHIP_DIRS.get(analysis)
    keys      = ANALYSIS_PLOTS.get(analysis, [])

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    grid = QGridLayout(container)
    grid.setSpacing(8)

    col_count = 2

    for idx, key in enumerate(keys):
        row = idx // col_count
        col = idx % col_count

        # Canvas no configurado
        canvas_name = CANVAS_NAMES.get(key)
        if canvas_name is None:
            grid.addWidget(_warning(f"Sin canvas configurado para '{key}'"), row, col)
            continue

        # Fichero no encontrado
        if root_path is None or not os.path.exists(root_path):
            grid.addWidget(_warning(f"Fichero no encontrado:\n{root_path}"), row, col)
            continue

        canvas_path = build_canvas_path(chip_dir, canvas_name)

        try:
            plotter = make_plotter(key, root_path, canvas_path)
            widget  = plotter.get_canvas()
            grid.addWidget(widget, row, col)
        except Exception as e:
            grid.addWidget(_warning(f"Error en '{key}':\n{e}"), row, col)
            logging.error("Error cargando '%s': %s", key, e, exc_info=True)

    scroll.setWidget(container)
    return scroll


def _warning(text: str) -> QLabel:
    """Etiqueta de aviso para mostrar en lugar de un plot fallido."""
    label = QLabel(f"⚠ {text}")
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    label.setStyleSheet("color: #B71C1C; background: #FFEBEE; border: 1px solid #EF9A9A; padding: 8px;")
    return label


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QMainWindow()
    window.setWindowTitle("RD53A Plotter — Test integrado")
    window.resize(1200, 700)

    tabs = QTabWidget()
    window.setCentralWidget(tabs)

    for analysis in ROOT_FILES.keys():
        tab = build_tab(analysis)
        tabs.addTab(tab, analysis.upper())

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()