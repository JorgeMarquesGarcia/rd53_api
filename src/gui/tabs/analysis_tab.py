"""analysis_tab.py - Tab de análisis del sistema RD53A.

Fase 1: interruptor Calibration/Acquisition + selector de fichero
(Browse + 3 más recientes de la carpeta Results) + área de resultados vacía.
"""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QTextEdit,
    QFileDialog, QButtonGroup,
)
from PyQt5.QtCore import Qt, pyqtSignal

from src.config.system_config import SystemConfig
from src.core.results_finder import (
    latest_files, ROOT_EXT, RAW_EXT, 
    CALIBRATION_NAME_PATTERNS, ACQUISITION_NAME_PATTERNS
)

MODE_CALIBRATION = 0
MODE_ACQUISITION = 1

N_RECENT = 3

_SEGMENT_QSS = (
    "QPushButton { padding: 6px 18px; }"
    "QPushButton:checked { background: #003D4A; color: #00E5FF; "
    "border: 1px solid #00E5FF; font-weight: bold; }"
)


class AnalysisTab(QWidget):
    # Emitida cuando el usuario elige un fichero (para las siguientes fases)
    file_selected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("AnalysisTab")
        self._selected_file: Path | None = None

        self._build_ui()
        self._refresh_recent()
        self.logger.info("AnalysisTab inicializado.")

    # ==================================================================
    # Propiedades / API pública
    # ==================================================================
    @property
    def mode(self) -> int:
        return self._mode_group.checkedId()

    @property
    def selected_file(self) -> Path | None:
        return self._selected_file

    def on_config_applied(self):
        """Llamado desde MainWindow cuando se aplica la configuración."""
        self._refresh_recent()

    # ==================================================================
    # Construcción UI
    # ==================================================================
    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self._build_control_panel())
        left_splitter.addWidget(self._build_log_panel())
        left_splitter.setSizes([600, 200])
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 0)
        left_splitter.setMaximumWidth(420)

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(self._build_results_panel())
        h_splitter.setSizes([380, 900])

        main.addWidget(h_splitter)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("ANALYSIS")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # --- Interruptor de modo (control segmentado) ---
        mode_group = QGroupBox("MODE")
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setSpacing(0)

        self._btn_cal = QPushButton("Calibration")
        self._btn_acq = QPushButton("Acquisition")
        for btn in (self._btn_cal, self._btn_acq):
            btn.setCheckable(True)
            btn.setStyleSheet(_SEGMENT_QSS)
            mode_layout.addWidget(btn)
        self._btn_cal.setChecked(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._btn_cal, MODE_CALIBRATION)
        self._mode_group.addButton(self._btn_acq, MODE_ACQUISITION)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        layout.addWidget(mode_group)

        # --- Selector de fichero ---
        file_group = QGroupBox("FILE TO ANALYZE")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(8)

        browse_row = QHBoxLayout()
        self._file_edit = QLineEdit()
        self._file_edit.setReadOnly(True)
        self._file_edit.setPlaceholderText("No file selected")
        browse_row.addWidget(self._file_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        browse_row.addWidget(browse_btn)
        file_layout.addLayout(browse_row)

        recent_header = QHBoxLayout()
        self._recent_label = QLabel("")
        self._recent_label.setStyleSheet("color: #7A8090; font-size: 10px;")
        recent_header.addWidget(self._recent_label, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(90)
        refresh_btn.setToolTip("Rescan the Results directory")
        refresh_btn.clicked.connect(self._refresh_recent)
        recent_header.addWidget(refresh_btn)
        file_layout.addLayout(recent_header)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(110)
        self._recent_list.setStyleSheet(
            "QListWidget { background: #1A1F2B; color: #B8C4D0; "
            "font-family: monospace; font-size: 10px; border: 1px solid #2A3040; }"
            "QListWidget::item:selected { background: #003D4A; color: #00E5FF; }"
        )
        self._recent_list.itemClicked.connect(self._on_recent_clicked)
        file_layout.addWidget(self._recent_list)

        layout.addWidget(file_group)
        layout.addStretch(1)
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("ANALYSIS LOG")
        title.setObjectName("section_title")
        header.addWidget(title)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(lambda: self._log.clear())
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Analysis output will appear here...")
        layout.addWidget(self._log)
        return panel

    def _build_results_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        title = QLabel("RESULTS")
        title.setObjectName("section_title")
        layout.addWidget(title)

        self._results_placeholder = QLabel(
            "Select a file to analyze. Results will appear here."
        )
        self._results_placeholder.setAlignment(Qt.AlignCenter)
        self._results_placeholder.setStyleSheet(
            "color: #3A4050; font-size: 13px; border: 1px dashed #2E3340;"
        )
        layout.addWidget(self._results_placeholder, 1)
        return panel

    # ==================================================================
    # Reglas por modo
    # ==================================================================
    def _allowed_extensions(self) -> tuple[str, ...]:
        if self.mode == MODE_CALIBRATION:
            return (ROOT_EXT,)
        return (ROOT_EXT, RAW_EXT)

    def _name_patterns(self) -> tuple[str, ...]:
        if self.mode == MODE_CALIBRATION:
            return CALIBRATION_NAME_PATTERNS
        return ACQUISITION_NAME_PATTERNS
    
    def _results_dir(self) -> Path | None:
        """Carpeta 'ROOT output directory' de config_tab (None si no configurada)."""
        try:
            return SystemConfig.get_root_path()
        except Exception:
            return None

    # ==================================================================
    # Callbacks
    # ==================================================================
    def _on_mode_changed(self, *_):
        # Cambiar de modo invalida la selección anterior (las reglas de
        # extensión/nombre son distintas)
        self._set_selected_file(None)
        self._refresh_recent()
        self._log_write(f"[INFO] Mode: "
                        f"{'CALIBRATION' if self.mode == MODE_CALIBRATION else 'ACQUISITION'}")

    def _browse_file(self):
        start_dir = self._results_dir()
        exts = self._allowed_extensions()
        if len(exts) == 1:
            file_filter = "ROOT files (*.root)"
        else:
            file_filter = "ROOT / RAW files (*.root *.raw)"

        path, _ = QFileDialog.getOpenFileName(
            self, "Select file to analyze",
            str(start_dir) if start_dir else "", file_filter,
        )
        if not path:
            return

        p = Path(path)
        if p.suffix.lower() not in exts:
            self._log_write(f"[WARN] Invalid file type for this mode: {p.name}")
            return
        self._set_selected_file(p)

    def _on_recent_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self._set_selected_file(Path(path))

    # ==================================================================
    # Lógica
    # ==================================================================
    def _refresh_recent(self):
        self._recent_list.clear()
        results_dir = self._results_dir()

        if results_dir is None:
            self._recent_label.setText("Set 'ROOT output directory' in Config tab.")
            return

        files = latest_files(
            results_dir,
            extensions=self._allowed_extensions(),
            name_patterns=self._name_patterns(),
            n=N_RECENT,
        )

        self._recent_label.setText(f"Latest {N_RECENT} in {results_dir.name}/")
        if not files:
            item = QListWidgetItem("(no matching files)")
            item.setFlags(Qt.NoItemFlags)
            self._recent_list.addItem(item)
            return

        name_width = max(len(f.name) for f in files)
        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")
            item = QListWidgetItem(f"{f.name.ljust(name_width)}   {mtime}")
            item.setData(Qt.UserRole, str(f))
            item.setToolTip(str(f))
            self._recent_list.addItem(item)

            if self._selected_file == f:
                self._recent_list.setCurrentItem(item)

    def _set_selected_file(self, path: Path | None):
        self._selected_file = path
        self._file_edit.setText(str(path) if path else "")

        if path is None:
            self._recent_list.clearSelection()
            return

        # Sincronizar selección visual con la lista de recientes
        self._recent_list.clearSelection()
        for i in range(self._recent_list.count()):
            it = self._recent_list.item(i)
            if it.data(Qt.UserRole) == str(path):
                self._recent_list.setCurrentItem(it)
                break

        self._log_write(f"[INFO] File selected: {path.name}")
        self.file_selected.emit(path)

    # ==================================================================
    # Helper log
    # ==================================================================
    def _log_write(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
        self.logger.info(msg)