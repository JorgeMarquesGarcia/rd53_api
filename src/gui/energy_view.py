"""energy_view.py - Resultado de EnergyAnalysis: energía depositada por cluster en cada chip."""
from __future__ import annotations
import csv
from pathlib import Path

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

from src.analysis.analysis_energy import CLUSTER_FIELDS
from src.plotter.energy_histogram import build_energy_canvas

ChipKey = tuple[int, int]


class EnergyView(QWidget):
    """Página de resultados de energía de un fichero .root: un histograma por chip."""

    log_message = pyqtSignal(str)

    def __init__(self, root_path: Path, gain_path: Path,
                 clusters: dict[str, np.ndarray], stats: dict[ChipKey, dict], parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._clusters = clusters

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        n = len(clusters["energy_kev"])
        info = QLabel(f"{n} clusters in {len(stats)} chip(s)  ·  gain calibration: {gain_path.name}")
        info.setToolTip(str(gain_path))
        header.addWidget(info)
        header.addStretch()
        save_btn = QPushButton("Save CSV")
        save_btn.setToolTip("One row per cluster: track, chip, size, ToT, charge and energy")
        save_btn.clicked.connect(self._save_csv)
        header.addWidget(save_btn)
        layout.addLayout(header)

        tabs = QTabWidget()
        for (h, c), s in sorted(stats.items()):
            sel = (clusters["hybrid"] == h) & (clusters["lane"] == c)
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            title = (f"H{h} · Chip {c} — {s['n_clusters']} clusters, "
                     f"mean size {s['mean_size']:.2f} px")
            canvas = build_energy_canvas(clusters["energy_kev"][sel], clusters["saturated"][sel], title)
            page_layout.addWidget(NavigationToolbar2QT(canvas, page))
            page_layout.addWidget(canvas, 1)
            tabs.addTab(page, f"H{h} · Chip {c} ({s['n_clusters']})")
        layout.addWidget(tabs, 1)

    def _save_csv(self):
        default = self._root_path.with_name(f"{self._root_path.stem}_energy.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Save cluster energies", str(default),
                                              "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CLUSTER_FIELDS)
                columns = [self._clusters[name] for name in CLUSTER_FIELDS]
                for row in zip(*columns):
                    values = (x.item() for x in row)   # numpy → int / float / bool de Python
                    writer.writerow([f"{v:.6g}" if isinstance(v, float) else v for v in values])
            self.log_message.emit(f"[OK]   Cluster energies saved: {path}")
        except OSError as e:
            self.log_message.emit(f"[ERROR] Cannot save CSV: {e}")
