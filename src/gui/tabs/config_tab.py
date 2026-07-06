"""config_tab.py - Tab de configuración del sistema RD53A."""
from __future__ import annotations
import json
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QCheckBox, QFileDialog, QMessageBox, QSplitter,
    QScrollArea, QSpacerItem, QSizePolicy, QPlainTextEdit,
    QComboBox, QListWidget, QListWidgetItem,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from src.config.system_config import SystemConfig
from src.config.xml.xml_manager import XmlManager

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

        # Mapeo (hybrid_id, chip_id_local) -> rd53_id (id global usado en el XML)
        self._chip_to_rd53: dict[tuple[int, int], int] = {}

        # Checkboxes "All": uno por layer multi-chip (hybrid_id -> checkbox)
        # y uno maestro para todo el detector.
        self._layer_all_checks: dict[int, QCheckBox] = {}
        self._all_chips_check: QCheckBox | None = None

        # Widgets de la caja de ficheros TXT por chip
        self._txt_combo: dict[tuple[int, int], QComboBox] = {}
        self._txt_rows:  dict[tuple[int, int], QWidget]   = {}
        self._txt_file_list: QListWidget | None = None

        self._build_ui()
        self._load_settings()
        self._refresh_txt_file_list()
        self.logger.info("ConfigTab inicializado.")

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Barra superior: título + botón APPLY CONFIG compacto a la derecha
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        header_title = QLabel("SYSTEM CONFIGURATION")
        header_title.setObjectName("section_title")
        header_layout.addWidget(header_title)
        header_layout.addStretch(1)

        apply_btn = QPushButton("APPLY CONFIG")
        apply_btn.setObjectName("btn_launch")
        apply_btn.setMaximumWidth(160)
        apply_btn.setMaximumHeight(28)
        apply_btn.setToolTip("Apply the current detector/path configuration")
        apply_btn.clicked.connect(self._apply_config)
        header_layout.addWidget(apply_btn)

        main_layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_detector_panel())
        splitter.addWidget(self._build_paths_panel())
        splitter.setSizes([480, 480])

        main_layout.addWidget(splitter, 1)

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

        # Checkbox "All" maestro: selecciona/deselecciona todos los chips
        # del detector. Vive junto al chip único de Layer 0.
        self._all_chips_check = QCheckBox("All")
        self._all_chips_check.setToolTip("Select / deselect all chips in the detector")

        for layer_id, layer_info in DETECTOR_LAYOUT.items():
            layer_box = QGroupBox(layer_info["label"])
            layer_box.setStyleSheet("QGroupBox { color: #90A4B0; font-size: 10px; }")
            layer_layout = QHBoxLayout(layer_box)
            layer_layout.setSpacing(12)

            offset    = layer_info["rd53_offset"]
            hybrid_id = layer_info["hybrid"]

            if layer_info["single"]:
                cb = QCheckBox("Chip 0  (single sensor)")
                cb.setChecked(True)
                key = (hybrid_id, 0)
                self._chip_checks[key] = cb
                self._chip_to_rd53[key] = 0 + offset
                cb.toggled.connect(
                    lambda checked, h=hybrid_id: self._on_chip_checkbox_toggled(h, checked)
                )
                layer_layout.addWidget(cb)

                # "All" maestro, empujado al extremo derecho de la caja.
                layer_layout.addStretch(1)
                layer_layout.addWidget(self._all_chips_check)
            else:
                grid = QGridLayout()
                grid.setHorizontalSpacing(100)
                grid.setVerticalSpacing(8)
                positions = {0: (1,0), 1: (1,1), 2: (0,0), 3: (0,1)}
                for chip_id in layer_info["chips"]:
                    cb = QCheckBox(f"Chip {chip_id}")
                    row, col = positions[chip_id]
                    grid.addWidget(cb, row, col)
                    key = (hybrid_id, chip_id)
                    self._chip_checks[key] = cb
                    self._chip_to_rd53[key] = chip_id + offset
                    cb.toggled.connect(
                        lambda checked, h=hybrid_id: self._on_chip_checkbox_toggled(h, checked)
                    )
                layer_layout.addLayout(grid)

                # "All" del layer: separado del resto, empujado al extremo
                # derecho de la caja (no forma parte de la rejilla 2x2).
                layer_all_cb = QCheckBox("All")
                layer_all_cb.setToolTip(f"Select / deselect all chips in {layer_info['label']}")
                layer_all_cb.toggled.connect(
                    lambda checked, h=hybrid_id: self._on_layer_all_toggled(h, checked)
                )
                self._layer_all_checks[hybrid_id] = layer_all_cb

                layer_layout.addStretch(1)
                layer_layout.addWidget(layer_all_cb, alignment=Qt.AlignVCenter)

            chips_layout.addWidget(layer_box)

        # Estado inicial coherente de los checkboxes "All" según los chips
        # marcados por defecto (layer 0 empieza activo, 1 y 2 no).
        for hybrid_id, all_cb in self._layer_all_checks.items():
            chips_in_layer = [cb for (h, _c), cb in self._chip_checks.items() if h == hybrid_id]
            all_cb.blockSignals(True)
            all_cb.setChecked(bool(chips_in_layer) and all(cb.isChecked() for cb in chips_in_layer))
            all_cb.blockSignals(False)

        self._all_chips_check.toggled.connect(self._on_master_all_toggled)
        self._update_master_all_check()

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


        summary_group = QGroupBox("CURRENT CONFIGURATION")
        summary_layout = QVBoxLayout(summary_group)
        self._summary_box = QPlainTextEdit("No configuration applied.")
        self._summary_box.setReadOnly(True)
        self._summary_box.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #1A1F2B;"
            "  color: #505868;"
            "  font-family: monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #2A3040;"
            "  padding: 4px;"
            "}"
        )
        summary_layout.addWidget(self._summary_box)
        layout.addWidget(summary_group, 1)
        return panel

    # ------------------------------------------------------------------
    # Checkboxes "All": selección/deselección cruzada de chips
    # ------------------------------------------------------------------
    def _on_layer_all_toggled(self, hybrid_id: int, checked: bool):
        """Marca/desmarca todos los chips de un layer al pulsar su 'All'."""
        for (h, _c), cb in self._chip_checks.items():
            if h == hybrid_id:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)
        self._refresh_chip_txt_rows()
        self._update_master_all_check()

    def _on_master_all_toggled(self, checked: bool):
        """Marca/desmarca todos los chips del detector al pulsar el 'All' maestro."""
        for cb in self._chip_checks.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        for all_cb in self._layer_all_checks.values():
            all_cb.blockSignals(True)
            all_cb.setChecked(checked)
            all_cb.blockSignals(False)
        self._refresh_chip_txt_rows()

    def _on_chip_checkbox_toggled(self, hybrid_id: int, checked: bool):
        """Mantiene sincronizados los checkboxes 'All' (layer y maestro)
        cuando el usuario marca/desmarca un chip individual."""
        all_cb = self._layer_all_checks.get(hybrid_id)
        if all_cb is not None:
            chips_in_layer = [cb for (h, _c), cb in self._chip_checks.items() if h == hybrid_id]
            all_checked = bool(chips_in_layer) and all(cb.isChecked() for cb in chips_in_layer)
            all_cb.blockSignals(True)
            all_cb.setChecked(all_checked)
            all_cb.blockSignals(False)
        self._update_master_all_check()

    def _update_master_all_check(self):
        """Recalcula el estado del checkbox 'All' maestro según los chips activos."""
        if self._all_chips_check is None or not self._chip_checks:
            return
        all_checked = all(cb.isChecked() for cb in self._chip_checks.values())
        self._all_chips_check.blockSignals(True)
        self._all_chips_check.setChecked(all_checked)
        self._all_chips_check.blockSignals(False)

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

        # --------------------------------------------------------------
        # Caja: ficheros TXT de configuración por chip.
        # El botón de aplicar ahora vive en la cabecera superior de la
        # ventana (APPLY CONFIG), así que esta caja puede usar el espacio
        # vertical restante para mostrar más filas de la lista de .txt.
        # --------------------------------------------------------------
        txt_files_group = self._build_txt_files_panel()
        layout.addWidget(txt_files_group, 1)

        # Refrescar la lista de .txt disponibles cuando cambia el directorio
        self._path_edits["txt_base_dir"].textChanged.connect(self._refresh_txt_file_list)

        return panel

    # ------------------------------------------------------------------
    # Caja: ficheros TXT de configuración por chip
    # ------------------------------------------------------------------
    def _build_txt_files_panel(self) -> QGroupBox:
        """Caja para renombrar el fichero .txt (configFile) de cada chip
        activo y para ver de un vistazo qué .txt existen ya en el
        directorio TXT base configurado arriba."""
        group = QGroupBox("CHIP TXT CONFIG FILES")
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        rows_container = QWidget()
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)

        for (hybrid_id, chip_local), rd53_id in sorted(
            self._chip_to_rd53.items(), key=lambda kv: (kv[0][0], kv[1])
        ):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            lbl = QLabel(f"H{hybrid_id} Chip{rd53_id}:")
            lbl.setMinimumWidth(90)
            lbl.setStyleSheet("color: #90A4B0; font-size: 11px;")
            row_layout.addWidget(lbl)

            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.NoInsert)
            combo.setPlaceholderText("CMSIT_RD53A_xx.txt")
            combo.setMinimumWidth(200)
            row_layout.addWidget(combo, 1)

            rows_layout.addWidget(row)

            key = (hybrid_id, rd53_id)
            self._txt_combo[key] = combo
            self._txt_rows[key] = row

            cb = self._chip_checks.get((hybrid_id, chip_local))
            if cb is not None:
                cb.toggled.connect(self._refresh_chip_txt_rows)

        layout.addWidget(rows_container)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load names from XML")
        load_btn.setToolTip("Lee el configFile actual de cada chip activo desde el XML seleccionado arriba.")
        load_btn.clicked.connect(self._load_configfiles_from_xml)
        btn_row.addWidget(load_btn)

        refresh_btn = QPushButton("Refresh file list")
        refresh_btn.setToolTip("Vuelve a escanear el directorio TXT base en busca de ficheros .txt.")
        refresh_btn.clicked.connect(self._refresh_txt_file_list)
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

        list_lbl = QLabel("Available config files in TXT base directory:")
        list_lbl.setStyleSheet("color: #7A8090; font-size: 10px;")
        layout.addWidget(list_lbl)

        self._txt_file_list = QListWidget()
        self._txt_file_list.setMinimumHeight(90)
        self._txt_file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._txt_file_list.setStyleSheet(
            "QListWidget {"
            "  background: #1A1F2B;"
            "  color: #B8C4D0;"
            "  font-family: monospace;"
            "  font-size: 10px;"
            "  border: 1px solid #2A3040;"
            "}"
        )
        layout.addWidget(self._txt_file_list, 1)

        self._refresh_chip_txt_rows()
        return group

    def _refresh_chip_txt_rows(self):
        """Muestra/oculta las filas de la caja TXT según los chips activos."""
        for (hybrid_id, chip_local), rd53_id in self._chip_to_rd53.items():
            cb = self._chip_checks.get((hybrid_id, chip_local))
            row = self._txt_rows.get((hybrid_id, rd53_id))
            if row is not None:
                row.setVisible(bool(cb and cb.isChecked()))

    def _refresh_txt_file_list(self):
        """Escanea txt_base_dir y actualiza tanto la lista de referencia
        como las opciones desplegables de cada combo de chip."""
        if self._txt_file_list is None:
            return

        txt_dir_str = self._path_edits["txt_base_dir"].text().strip()
        filenames: list[str] = []
        if txt_dir_str:
            txt_dir = Path(txt_dir_str)
            if txt_dir.exists() and txt_dir.is_dir():
                filenames = sorted(p.name for p in txt_dir.glob("*.txt"))

        self._txt_file_list.clear()
        if not filenames:
            item = QListWidgetItem("(sin ficheros .txt en este directorio)")
            item.setFlags(Qt.NoItemFlags)
            self._txt_file_list.addItem(item)
        else:
            for name in filenames:
                self._txt_file_list.addItem(name)

        for combo in self._txt_combo.values():
            current_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(filenames)
            combo.setCurrentText(current_text)
            combo.blockSignals(False)

    def _load_configfiles_from_xml(self):
        """Lee el XML seleccionado (modo solo lectura) y rellena cada
        combo de chip activo con su configFile actual."""
        xml_path = self._path_edits["xml_path"].text().strip()
        if not xml_path or not Path(xml_path).exists():
            QMessageBox.warning(self, "XML not found",
                                 "Selecciona primero un XML config file válido.")
            return

        try:
            xml_mgr = XmlManager(xml_path, read_only=True)
            xml_mgr.load()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo leer el XML:\n{e}")
            return

        loaded, missing = 0, []
        for (hybrid_id, rd53_id), combo in self._txt_combo.items():
            try:
                fname = xml_mgr.get_chip_config_file(hybrid_id, rd53_id) or ""
                combo.setCurrentText(fname)
                loaded += 1
            except Exception as chip_err:
                missing.append(f"H{hybrid_id} Chip{rd53_id}")
                self.logger.warning(
                    "No se pudo leer configFile de Hybrid %d / RD53A %d: %s",
                    hybrid_id, rd53_id, chip_err,
                )

        msg = f"Nombres cargados para {loaded} chip(s) desde el XML."
        if missing:
            msg += "\n\nNo encontrados en el XML: " + ", ".join(missing)
        QMessageBox.information(self, "Load from XML", msg)

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

        # Construir selección completa: {(hybrid_id, rd53_id): is_active}
        # rd53_id = chip_id_local + rd53_offset definido en DETECTOR_LAYOUT
        chip_selection: dict[tuple[int, int], bool] = {}
        active_hybrids: set[int] = set()
        active_chips:   list[int] = []

        for layer_info in DETECTOR_LAYOUT.values():
            offset    = layer_info["rd53_offset"]
            hybrid_id = layer_info["hybrid"]
            for chip_id in layer_info["chips"]:
                rd53_id = chip_id + offset
                cb      = self._chip_checks.get((hybrid_id, chip_id))
                checked = bool(cb and cb.isChecked())
                chip_selection[(hybrid_id, rd53_id)] = checked
                if checked:
                    active_hybrids.add(hybrid_id)
                    active_chips.append(rd53_id)

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
            QMessageBox.warning(self, "Configuration Error", "\n\n".join(errors))
            return

        try:
            # 1. Registrar paths en el singleton
            SystemConfig.configure(
                ph2_acf_dir=ph2_acf,
                xml_path=xml,
                root_path=root if root else None,
                txt_base_dir=txt if txt else None,
            )
            SystemConfig.set_active_columns(col_start, col_end)
            SystemConfig.set_active_hybrids(sorted(active_hybrids))
            SystemConfig.set_active_chips(active_chips)
            SystemConfig.set_active_hw_chips(
                [(h, r) for (h, r), active in chip_selection.items() if active]
            )
            # txt_base_dir puede estar vacío: si no lo está, lo usamos para
            # verificar si el .txt de cada chip existe físicamente en disco.
            txt_base = Path(txt) if txt else None

            # 2. Abrir el XML, activar/desactivar chips, aplicar renombrados
            #    de configFile pendientes en la caja TXT, leer configFile y
            #    comprobar existencia del .txt en disco.
            xml_mgr = SystemConfig.create_xml_manager(read_only=False)
            config_files: dict[tuple[int, int], str] = {}
            xml_log_lines: list[str] = []

            for (hybrid_id, rd53_id), is_active in sorted(chip_selection.items()):
                try:
                    xml_mgr.set_chip_enable(hybrid_id, rd53_id, is_active)

                    # Si el usuario ha escrito/elegido un nombre distinto en
                    # la caja "CHIP TXT CONFIG FILES", lo persistimos en el XML.
                    combo = self._txt_combo.get((hybrid_id, rd53_id))
                    if combo is not None:
                        new_name = combo.currentText().strip()
                        if new_name:
                            current_name = xml_mgr.get_chip_config_file(hybrid_id, rd53_id) or ""
                            if new_name != current_name:
                                xml_mgr.set_chip_config_file(hybrid_id, rd53_id, new_name)

                    fname = xml_mgr.get_chip_config_file(hybrid_id, rd53_id) or ""

                    if fname:
                        config_files[(hybrid_id, rd53_id)] = fname

                    # Símbolo de existencia del fichero .txt en disco:
                    #   ✓  existe   ✗  no existe   –  no hay txt_base_dir
                    if not fname:
                        file_symbol = "–"
                    elif txt_base is None:
                        file_symbol = "–"
                    elif (txt_base / fname).exists():
                        file_symbol = "✓"
                    else:
                        file_symbol = "✗"

                    status = "ON" if is_active else "OFF"
                    xml_log_lines.append(
                        f"H{hybrid_id} Chip{rd53_id:>2}    [{status}]"
                        f"   {fname or '(no configFile)':<28}"
                        f"   {file_symbol}"
                    )
                except Exception as chip_err:
                    # El chip puede no existir en este XML (slot vacío)
                    self.logger.warning(
                        "Hybrid %d / RD53A %d no encontrado en el XML: %s",
                        hybrid_id, rd53_id, chip_err,
                    )

            # 3. Persistir el mapa de configFiles en el singleton
            #    (genera un INFO por chip en el logger de Python)
            SystemConfig.set_chip_config_files(config_files)

            if plots:
                Path(plots).mkdir(parents=True, exist_ok=True)

            self._update_summary(ph2_acf, xml, col_start, col_end, xml_log_lines)
            self._refresh_txt_file_list()
            self.config_applied.emit()
            self.logger.info(
                "Configuración aplicada: cols=%d-%d chips=%s",
                col_start, col_end, active_chips,
            )
            self._save_settings()
            QMessageBox.information(self, "Configuration Applied",
                                    "System configured successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Configuration Error", str(e))
            self.logger.error("Error aplicando configuración: %s", e)

    def _update_summary(
        self,
        ph2_acf: str,
        xml: str,
        col_start: int,
        col_end: int,
        xml_log_lines: list[str],
    ):
        header = (
            f"Ph2_ACF : {Path(ph2_acf).name}\n"
            f"XML     : {Path(xml).name}\n"
            f"Columns : {col_start} → {col_end}\n"
            f"{'─' * 60}\n"
            f"{'Chip':<12} {'Status':<6}  {'ConfigFile':<28}  File\n"
            f"{'─' * 60}\n"
        )
        body = "\n".join(xml_log_lines)
        self._summary_box.setPlainText(header + body)
        self._summary_box.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #1A1F2B;"
            "  color: #69F0AE;"
            "  font-family: monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #2A3040;"
            "  padding: 4px;"
            "}"
        )

    # ------------------------------------------------------------------
    # Persistencia entre sesiones
    # ------------------------------------------------------------------
    def _save_settings(self):
        """Guarda paths, chips activos y nombres de .txt en ~/.rd53a_gui_settings.json"""
        try:
            settings = {
                "paths": {k: v.text() for k, v in self._path_edits.items()},
                "active_chips": {
                    f"{h},{c}": cb.isChecked()
                    for (h, c), cb in self._chip_checks.items()
                },
                "col_start": self._col_start.text(),
                "col_end":   self._col_end.text(),
                "txt_names": {
                    f"{h},{r}": combo.currentText()
                    for (h, r), combo in self._txt_combo.items()
                    if combo.currentText().strip()
                },
            }
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
            self.logger.info("Settings saved to %s", SETTINGS_FILE)
        except Exception as e:
            self.logger.warning("Could not save settings: %s", e)

    def _load_settings(self):
        """Carga paths, chips y nombres de .txt desde ~/.rd53a_gui_settings.json si existe."""
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

            for key, name in settings.get("txt_names", {}).items():
                h, r = map(int, key.split(","))
                combo = self._txt_combo.get((h, r))
                if combo is not None and name:
                    combo.setCurrentText(name)

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