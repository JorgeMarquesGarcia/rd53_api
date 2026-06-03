"""config_tab.py - Tab de configuración del sistema RD53A."""
from __future__ import annotations
import json
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QFileDialog, QMessageBox, QSplitter,
    QScrollArea, QSpacerItem, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from src.config.system_config import SystemConfig

SETTINGS_FILE = Path.home() / ".rd53a_gui_settings.json"

# ---------------------------------------------------------------------------
# Geometría del detector
# ---------------------------------------------------------------------------
DETECTOR_LAYOUT = {
    0: {"label": "Layer 0  (Z=0)",  "hybrid": 0, "chips": [0],       "rd53_offset": 0, "single": True},
    1: {"label": "Layer 1  (Z=1)",  "hybrid": 1, "chips": [0,1,2,3], "rd53_offset": 4, "single": False},
    2: {"label": "Layer 2  (Z=2)",  "hybrid": 2, "chips": [0,1,2,3], "rd53_offset": 4, "single": False},
}

class ConfigTab(QWidget):
    """Tab de configuración: detector activo + paths del sistema."""

    config_applied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("ConfigTab")
        self._chip_checks: dict[tuple, QCheckBox] = {}
        self._path_edits:  dict[str, QLineEdit]   = {}
        self._build_ui()
        self._load_settings()
        self.logger.info("ConfigTab inicializado.")

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_detector_panel())
        splitter.addWidget(self._build_paths_panel())
        splitter.setSizes([480, 480])

        main_layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Panel izquierdo: Detector
    # ------------------------------------------------------------------
    def _build_detector_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("DETECTOR CONFIGURATION")
        title.setObjectName("section_title")
        layout.addWidget(title)

        chips_group = QGroupBox("ACTIVE CHIPS")
        chips_layout = QVBoxLayout(chips_group)
        chips_layout.setSpacing(10)

        for layer_id, layer_info in DETECTOR_LAYOUT.items():
            layer_box = QGroupBox(layer_info["label"])
            layer_box.setStyleSheet("QGroupBox { color: #90A4B0; font-size: 10px; }")
            layer_layout = QHBoxLayout(layer_box)
            layer_layout.setSpacing(12)

            if layer_info["single"]:
                cb = QCheckBox("Chip 0  (single sensor)")
                cb.setChecked(True)
                key = (layer_info["hybrid"], 0)
                self._chip_checks[key] = cb
                layer_layout.addWidget(cb)
            else:
                grid = QGridLayout()
                grid.setSpacing(8)
                positions = {0: (1,0), 1: (1,1), 2: (0,0), 3: (0,1)}
                for chip_id in layer_info["chips"]:
                    cb = QCheckBox(f"Chip {chip_id}")
                    row, col = positions[chip_id]
                    grid.addWidget(cb, row, col)
                    key = (layer_info["hybrid"], chip_id)
                    self._chip_checks[key] = cb
                layer_layout.addLayout(grid)

            chips_layout.addWidget(layer_box)

        layout.addWidget(chips_group)

        cols_group = QGroupBox("ACTIVE COLUMNS")
        cols_layout = QGridLayout(cols_group)
        cols_layout.setSpacing(8)

        cols_layout.addWidget(QLabel("Start col:"), 0, 0)
        self._col_start = QLineEdit("128")
        self._col_start.setMaximumWidth(80)
        cols_layout.addWidget(self._col_start, 0, 1)

        cols_layout.addWidget(QLabel("End col:"), 0, 2)
        self._col_end = QLineEdit("263")
        self._col_end.setMaximumWidth(80)
        cols_layout.addWidget(self._col_end, 0, 3)

        note = QLabel("  (chip columns 0–399, active range typically 128–263)")
        note.setStyleSheet("color: #505868; font-size: 10px;")
        cols_layout.addWidget(note, 1, 0, 1, 4)

        layout.addWidget(cols_group)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return panel

    # ------------------------------------------------------------------
    # Panel derecho: Paths
    # ------------------------------------------------------------------
    def _build_paths_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("SYSTEM PATHS")
        title.setObjectName("section_title")
        layout.addWidget(title)

        paths_group = QGroupBox("FILE PATHS")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setSpacing(8)
        paths_layout.setColumnStretch(1, 1)

        path_defs = [
            ("ph2_acf_dir",  "Ph2_ACF directory",    True),
            ("xml_path",     "XML config file",       False),
            ("root_path",    "ROOT output directory", True),
            ("txt_base_dir", "TXT base directory",    True),
            ("plots_dir",    "Plots output directory",True),
        ]

        for row, (key, label, is_dir) in enumerate(path_defs):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #7A8090; font-size: 11px;")
            paths_layout.addWidget(lbl, row, 0)

            edit = QLineEdit()
            edit.setPlaceholderText(f"Select {label.lower()}...")
            self._path_edits[key] = edit
            paths_layout.addWidget(edit, row, 1)

            btn = QPushButton("...")
            btn.setMaximumWidth(60)
            btn.setFont(QFont("Arial", 10))
            btn.setToolTip(f"Browse {label}")
            btn.clicked.connect(lambda checked, k=key, d=is_dir: self._browse_path(k, d))
            paths_layout.addWidget(btn, row, 2)

        layout.addWidget(paths_group)

        apply_btn = QPushButton("APPLY CONFIGURATION")
        apply_btn.setObjectName("btn_launch")
        apply_btn.clicked.connect(self._apply_config)
        layout.addWidget(apply_btn)

        summary_group = QGroupBox("CURRENT CONFIGURATION")
        summary_layout = QVBoxLayout(summary_group)
        self._summary_label = QLabel("No configuration applied.")
        self._summary_label.setStyleSheet("color: #505868; font-size: 11px;")
        self._summary_label.setWordWrap(True)
        summary_layout.addWidget(self._summary_label)
        layout.addWidget(summary_group)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return panel

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------
    def _browse_path(self, key: str, is_dir: bool):
        if is_dir:
            path = QFileDialog.getExistingDirectory(self, "Select directory")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self._path_edits[key].setText(path)

    def _apply_config(self):
        """Valida y aplica la configuración al SystemConfig singleton."""
        errors = []

        ph2_acf = self._path_edits["ph2_acf_dir"].text().strip()
        xml     = self._path_edits["xml_path"].text().strip()
        root    = self._path_edits["root_path"].text().strip()
        txt     = self._path_edits["txt_base_dir"].text().strip()
        plots   = self._path_edits["plots_dir"].text().strip()

        if not ph2_acf:
            errors.append("Ph2_ACF directory is required.")
        elif not Path(ph2_acf).exists():
            errors.append(f"Ph2_ACF directory not found:\n{ph2_acf}")

        if not xml:
            errors.append("XML config file is required.")
        elif not Path(xml).exists():
            errors.append(f"XML file not found:\n{xml}")

        active_hybrids = set()
        active_chips   = []
        for layer_info in DETECTOR_LAYOUT.values():
            offset = layer_info["rd53_offset"]
            for chip_id in layer_info["chips"]:
                key = (layer_info["hybrid"], chip_id)
                cb = self._chip_checks.get(key)
                if cb and cb.isChecked():
                    active_hybrids.add(layer_info["hybrid"])
                    active_chips.append(chip_id + offset)

        if not active_chips:
            errors.append("At least one chip must be active.")

        try:
            col_start = int(self._col_start.text())
            col_end   = int(self._col_end.text())
            if not (0 <= col_start < col_end <= 399):
                errors.append("Column range must satisfy: 0 ≤ start < end ≤ 399")
        except ValueError:
            errors.append("Column start/end must be integers.")
            col_start, col_end = 128, 263

        if errors:
            QMessageBox.warning(self, "Configuration Error",
                                "\n\n".join(errors))
            return

        try:
            SystemConfig.configure(
                ph2_acf_dir=ph2_acf,
                xml_path=xml,
                root_path=root if root else None,
                txt_base_dir=txt if txt else None,
            )
            SystemConfig.set_active_columns(col_start, col_end)
            SystemConfig.set_active_hybrids(list(active_hybrids))
            SystemConfig.set_active_chips(active_chips)

            if plots:
                Path(plots).mkdir(parents=True, exist_ok=True)

            self._update_summary(ph2_acf, xml, col_start, col_end, active_chips)
            self.config_applied.emit()
            self.logger.info("Configuración aplicada: cols=%d-%d chips=%s",
                             col_start, col_end, active_chips)
            self._save_settings()
            QMessageBox.information(self, "Configuration Applied",
                                    "System configured successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", str(e))
            self.logger.error("Error aplicando configuración: %s", e)

    def _update_summary(self, ph2_acf, xml, col_start, col_end, chips):
        active = [f"H{h}/C{c}" for (h, c), cb in self._chip_checks.items() if cb.isChecked()]
        self._summary_label.setText(
            f"Ph2_ACF:  {Path(ph2_acf).name}\n"
            f"XML:      {Path(xml).name}\n"
            f"Columns:  {col_start} → {col_end}\n"
            f"Active:   {', '.join(active)}"
        )
        self._summary_label.setStyleSheet("color: #69F0AE; font-size: 11px;")

    # ------------------------------------------------------------------
    # Persistencia entre sesiones
    # ------------------------------------------------------------------
    def _save_settings(self):
        """Guarda paths y chips activos en ~/.rd53a_gui_settings.json"""
        try:
            settings = {
                "paths": {k: v.text() for k, v in self._path_edits.items()},
                "active_chips": {
                    f"{h},{c}": cb.isChecked()
                    for (h, c), cb in self._chip_checks.items()
                },
                "col_start": self._col_start.text(),
                "col_end":   self._col_end.text(),
            }
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
            self.logger.info("Settings saved to %s", SETTINGS_FILE)
        except Exception as e:
            self.logger.warning("Could not save settings: %s", e)

    def _load_settings(self):
        """Carga paths y chips desde ~/.rd53a_gui_settings.json si existe."""
        if not SETTINGS_FILE.exists():
            return
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)

            for key, value in settings.get("paths", {}).items():
                if key in self._path_edits and value:
                    self._path_edits[key].setText(value)

            for key, checked in settings.get("active_chips", {}).items():
                h, c = map(int, key.split(","))
                if (h, c) in self._chip_checks:
                    self._chip_checks[(h, c)].setChecked(checked)

            if "col_start" in settings:
                self._col_start.setText(settings["col_start"])
            if "col_end" in settings:
                self._col_end.setText(settings["col_end"])

            self.logger.info("Settings loaded from %s", SETTINGS_FILE)

            # Auto-aplicar si los paths obligatorios existen
            ph2 = settings.get("paths", {}).get("ph2_acf_dir", "")
            xml = settings.get("paths", {}).get("xml_path", "")
            if ph2 and xml and Path(ph2).exists() and Path(xml).exists():
                self._apply_config()
                self.logger.info("Auto-applied saved configuration.")

        except Exception as e:
            self.logger.warning("Could not load settings: %s", e)

    # ------------------------------------------------------------------
    # API pública para otros tabs
    # ------------------------------------------------------------------
    def get_active_chip_keys(self) -> list[tuple[int, int]]:
        """Devuelve lista de (hybrid_id, chip_id) activos."""
        return [(h, c) for (h, c), cb in self._chip_checks.items() if cb.isChecked()]