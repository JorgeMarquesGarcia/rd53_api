"""analysis_tab.py - Tab de análisis del sistema RD53A.

Fase 1: interruptor Calibration/Acquisition + selector de fichero
        (Browse + 3 más recientes de la carpeta Results).
Fase 2: modo Calibration -> lista de chips del .root + botón PLOT +
        resultados en pestañas (una por fichero, subpestañas por chip).
"""
from __future__ import annotations
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QLineEdit, QCheckBox, QTabWidget, QTabBar, QToolButton,
    QListWidget, QListWidgetItem, QTextEdit, QSpinBox,
    QFileDialog, QButtonGroup,
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal

from src.config.system_config import SystemConfig
from src.core.results_finder import (
    latest_files, detect_analysis, ROOT_EXT, RAW_EXT,
    CALIBRATION_NAME_PATTERNS, ACQUISITION_NAME_PATTERNS,
)
from src.gui.tabs.acquisition_tab import Raw2RootWorker, HitAnalysisWorker
from src.gui.trajectory_view import TrajectoryView
from src.gui.noise_mask_view import NoiseMaskView
from src.plotter.calibration_view import discover_chips, build_chip_plots_widget

MODE_CALIBRATION = 0
MODE_ACQUISITION = 1

N_RECENT = 3

_SEGMENT_QSS = (
    "QPushButton { padding: 6px 18px; }"
    "QPushButton:checked { background: #003D4A; color: #00E5FF; "
    "border: 1px solid #00E5FF; font-weight: bold; }"
)


class _ThreadLogForwarder(logging.Handler):
    """Reenvía al log de la GUI los mensajes de logging emitidos en un hilo concreto."""

    def __init__(self, emit, tag: str):
        super().__init__(level=logging.INFO)
        self._emit = emit
        self._tag = tag
        self._thread = threading.get_ident()

    def emit(self, record: logging.LogRecord):
        if record.thread != self._thread:
            return   # p. ej. un análisis del Acquisition tab corriendo a la vez
        level = "" if record.levelno <= logging.INFO else f" {record.levelname}"
        self._emit(f"[{self._tag}{level}] {record.getMessage()}")


@contextmanager
def forward_analysis_logs(emit, tag: str):
    """Muestra en la GUI los logs de src.analysis del hilo actual mientras dure el bloque."""
    logger = logging.getLogger("src.analysis")
    handler = _ThreadLogForwarder(emit, tag)
    old_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


class _HitAnalysisWorkerWithLogs(HitAnalysisWorker):
    """HitAnalysisWorker que además vuelca los pasos del análisis en el log del tab."""

    # El aviso de chips vacíos ya llega con los logs de BaseAnalysis
    warn_empty_chips = False

    def run(self):
        with forward_analysis_logs(self.log_message.emit, "HITS"):
            super().run()


class NoiseAnalysisWorker(QObject):
    """Carga un .root y ejecuta NoiseAnalysis fuera del hilo de la GUI."""
    log_message = pyqtSignal(str)
    analysed    = pyqtSignal(str, object, object)   # (root_path, pixel_counts, stats)
    finished    = pyqtSignal()

    def __init__(self, root_path: str, min_repeats: int):
        super().__init__()
        self._root_path = root_path
        self._min_repeats = min_repeats

    def run(self):
        try:
            from src.analysis.analysis_noise import NoiseAnalysis

            root_manager = SystemConfig.create_root_manager(path=self._root_path)
            root_manager.load(self._root_path)
            with forward_analysis_logs(self.log_message.emit, "NOISE"):
                analysis = NoiseAnalysis(root_manager, min_repeats=self._min_repeats)
            self.analysed.emit(self._root_path, analysis.noisy_pixel_counts, analysis.stats)
        except Exception as e:
            self.log_message.emit(f"[NOISE ERROR] {Path(self._root_path).name}: {e}")
        finally:
            self.finished.emit()


class AnalysisTab(QWidget):
    # Emitida cuando el usuario elige un fichero
    file_selected = pyqtSignal(Path)
    # True/False alrededor de operaciones con PyROOT (igual que CalibrationTab)
    plots_loading = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("AnalysisTab")
        self._selected_file: Path | None = None
        self._chip_checks: list[tuple[tuple[int, int], QCheckBox]] = []
        self._file_tabs: dict[str, QWidget] = {}   # ruta -> pestaña de resultados
        self._conversion_thread: QThread | None = None
        self._conversion_worker: Raw2RootWorker | None = None
        self._conversion_ok: bool = False
        self._hit_thread: QThread | None = None
        self._hit_worker: HitAnalysisWorker | None = None
        self._noise_thread: QThread | None = None
        self._noise_worker: NoiseAnalysisWorker | None = None

        self._build_ui()
        self._refresh_recent()
        self._populate_chips(None)
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
        # Los paneles de máscara abiertos dependen de la configuración activa
        for widget in self._file_tabs.values():
            if isinstance(widget, NoiseMaskView):
                widget.refresh_sources()

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
        refresh_btn.setMinimumWidth(90)
        refresh_btn.setToolTip("Rescan the Results directory")
        refresh_btn.clicked.connect(self._refresh_recent)
        recent_header.addWidget(refresh_btn)
        file_layout.addLayout(recent_header)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(80)
        self._recent_list.setStyleSheet(
            "QListWidget { background: #1A1F2B; color: #B8C4D0; "
            "font-family: monospace; font-size: 10px; border: 1px solid #2A3040; }"
            "QListWidget::item:selected { background: #003D4A; color: #00E5FF; }"
        )
        self._recent_list.itemClicked.connect(self._on_recent_clicked)
        file_layout.addWidget(self._recent_list)

        layout.addWidget(file_group)

        # --- Chips del fichero (solo modo Calibration) ---
        self._chips_group = QGroupBox("CHIPS IN FILE")
        chips_outer = QVBoxLayout(self._chips_group)
        chips_outer.setSpacing(6)

        self._chips_status = QLabel("")
        self._chips_status.setStyleSheet("color: #7A8090; font-size: 10px;")
        self._chips_status.setWordWrap(True)
        chips_outer.addWidget(self._chips_status)

        self._chips_all = QCheckBox("All")
        self._chips_all.toggled.connect(self._on_chips_all_toggled)
        chips_outer.addWidget(self._chips_all)

        self._chips_grid_widget = QWidget()
        self._chips_grid = QGridLayout(self._chips_grid_widget)
        self._chips_grid.setContentsMargins(0, 0, 0, 0)
        self._chips_grid.setHorizontalSpacing(24)
        self._chips_grid.setVerticalSpacing(6)
        chips_outer.addWidget(self._chips_grid_widget)

        layout.addWidget(self._chips_group)

        self._btn_plot = QPushButton("PLOT")
        self._btn_plot.setObjectName("btn_launch")
        self._btn_plot.setToolTip("Draw the selected chips of the selected file")
        self._btn_plot.setEnabled(False)
        self._btn_plot.clicked.connect(self._plot)
        layout.addWidget(self._btn_plot)

        self._btn_convert = QPushButton("RAW2ROOT")
        self._btn_convert.setObjectName("btn_launch")
        self._btn_convert.setToolTip("Convert the selected RAW file to ROOT")
        self._btn_convert.clicked.connect(self._convert_raw)
        self._btn_convert.setVisible(False)
        layout.addWidget(self._btn_convert)

        self._chk_animate = QCheckBox("Animate trajectories")
        self._chk_animate.setChecked(True)
        self._chk_animate.setToolTip("Unchecked: draw all tracks at once")
        self._chk_animate.setVisible(False)
        layout.addWidget(self._chk_animate)

        self._btn_hits = QPushButton("HIT ANALYSIS")
        self._btn_hits.setObjectName("btn_launch")
        self._btn_hits.setToolTip("Run HitAnalysis on the selected ROOT file and show its trajectories")
        self._btn_hits.clicked.connect(self._run_hit_analysis)
        self._btn_hits.setVisible(False)
        layout.addWidget(self._btn_hits)

        from src.analysis.analysis_noise import MIN_REPEATS

        self._noise_repeats_row = QWidget()
        repeats_layout = QHBoxLayout(self._noise_repeats_row)
        repeats_layout.setContentsMargins(0, 0, 0, 0)
        repeats_layout.addWidget(QLabel("Noise: min. repeats per pixel (N)"))
        self._spin_repeats = QSpinBox()
        self._spin_repeats.setRange(2, 100000)
        self._spin_repeats.setValue(MIN_REPEATS)
        self._spin_repeats.setToolTip(
            "A pixel with N or more hits with low ToT in the file is noisy "
            "(besides the multiple-hits criterion)")
        repeats_layout.addWidget(self._spin_repeats)
        self._noise_repeats_row.setVisible(False)
        layout.addWidget(self._noise_repeats_row)

        self._btn_noise = QPushButton("NOISE ANALYSIS")
        self._btn_noise.setObjectName("btn_launch")
        self._btn_noise.setToolTip("Find noisy pixels in the selected ROOT file and mask them")
        self._btn_noise.clicked.connect(self._run_noise_analysis)
        self._btn_noise.setVisible(False)
        layout.addWidget(self._btn_noise)

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
            "Select a file and press PLOT. Results will appear here."
        )
        self._results_placeholder.setAlignment(Qt.AlignCenter)
        self._results_placeholder.setStyleSheet(
            "color: #3A4050; font-size: 13px; border: 1px dashed #2E3340;"
        )
        layout.addWidget(self._results_placeholder, 1)

        self._results_tabs = QTabWidget()
        self._results_tabs.setTabsClosable(True)
        self._results_tabs.tabCloseRequested.connect(self._close_result_tab)
        self._results_tabs.setStyleSheet(
            "QTabBar::tab { padding: 4px 12px; font-size: 10px; }"
            "QTabBar::tab:selected { background: #1A1D23; color: #00E5FF; }"
            "QTabBar::close-button { width: 12px; height: 12px; background: transparent; border: none; }"
            "QTabBar::close-button:hover { background: transparent; }"
        )
        self._results_tabs.hide()
        layout.addWidget(self._results_tabs, 1)
        return panel

    # ==================================================================
    # Reglas por modo
    # ==================================================================
    def _allowed_extensions(self) -> tuple[str, ...]:
        if self.mode == MODE_ACQUISITION:
            return (ROOT_EXT, RAW_EXT)
        return (ROOT_EXT,)

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
    # Callbacks de selección
    # ==================================================================
    def _on_mode_changed(self, *_):
        is_cal = self.mode == MODE_CALIBRATION
        # Los chips y PLOT son de calibración; los análisis de adquisición
        # llegarán en fases posteriores.
        self._chips_group.setVisible(is_cal)
        self._btn_plot.setVisible(is_cal)
        self._btn_convert.setVisible(not is_cal)
        self._btn_hits.setVisible(not is_cal)
        self._btn_noise.setVisible(not is_cal)
        self._noise_repeats_row.setVisible(not is_cal)
        self._chk_animate.setVisible(not is_cal)

        # Cambiar de modo invalida la selección anterior
        self._set_selected_file(None)
        self._refresh_recent()
        self._log_write(f"[INFO] Mode: {'CALIBRATION' if is_cal else 'ACQUISITION'}")

    def _browse_file(self):
        start_dir = self._results_dir()
        exts = self._allowed_extensions()
        if self.mode == MODE_ACQUISITION:
            file_filter = "ROOT and raw files (*.root *.raw)"
        else:
            file_filter = "ROOT files (*.root)"

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

    def _convert_raw(self):
        path = self._selected_file
        if path is None or path.suffix.lower() != RAW_EXT:
            self._log_write("Not .raw file selected. Please select a correct file")
            return

        if self._conversion_thread is not None and self._conversion_thread.isRunning():
            self._log_write("[WARN] A RAW to ROOT conversion is already running.")
            return

        try:
            worker = Raw2RootWorker(
                xml_path=SystemConfig.get_xml_path(),
                results_dir=SystemConfig.get_root_path(),
                raw_path=path,
            )
        except Exception as e:
            self._log_write(f"[ERROR] Cannot start RAW to ROOT conversion: {e}")
            return

        self._conversion_worker = worker   
        self._btn_convert.setEnabled(False)
        self._log_write(f"[START] Converting {path.name} to ROOT...")
        self._conversion_thread = QThread(self)
        worker.moveToThread(self._conversion_thread)
        self._conversion_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.finished.connect(self._conversion_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_conversion_result)
        self._conversion_thread.finished.connect(self._on_conversion_finished)
        self._conversion_thread.finished.connect(self._conversion_thread.deleteLater)
        self._conversion_thread.start()

    def _on_conversion_result(self, ok: bool):
        self._conversion_ok = ok
        if ok:
            self._log_write("[OK] RAW to ROOT conversion finished.")
        else:
            self._log_write("[ERROR] RAW to ROOT conversion FAILED — see messages above.")

    def _on_conversion_finished(self):
        self._conversion_thread = None
        self._conversion_worker = None
        self._btn_convert.setEnabled(True)
        self._refresh_recent()

    # ==================================================================
    # HIT ANALYSIS (modo Acquisition)
    # ==================================================================
    def _run_hit_analysis(self):
        path = self._selected_file
        if path is None or path.suffix.lower() != ROOT_EXT:
            self._log_write("[WARN] Select a .root file to run the hit analysis.")
            return

        if self._hit_thread is not None and self._hit_thread.isRunning():
            self._log_write("[WARN] A hit analysis is already running.")
            return

        worker = _HitAnalysisWorkerWithLogs(str(path), self._spin_repeats.value())
        self._hit_worker = worker
        self._btn_hits.setEnabled(False)
        self._log_write(f"[START] Running HitAnalysis on {path.name}...")
        self._hit_thread = QThread(self)
        worker.moveToThread(self._hit_thread)
        self._hit_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.analysed.connect(self._on_hits_analysed)
        worker.finished.connect(self._hit_thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._hit_thread.finished.connect(self._on_hit_thread_finished)
        self._hit_thread.finished.connect(self._hit_thread.deleteLater)
        self._hit_thread.start()

    def _on_hits_analysed(self, root_path: str, plot_coord: list, active_chips: list):
        path = Path(root_path)
        n = len(plot_coord)
        self._log_write(f"[OK]   HitAnalysis complete: {n} tracks reconstructed.")
        if n == 0:
            self._log_write(f"[WARN] No tracks found in {path.name}.")
            return

        view = TrajectoryView()
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"{n} tracks"))
        header.addStretch()
        save_btn = QPushButton("Save Plot")
        save_btn.clicked.connect(lambda *_: self._save_trajectories(view))
        header.addWidget(save_btn)
        page_layout.addLayout(header)
        page_layout.addWidget(view, 1)

        self._add_result_tab(path, page, kind="hits")
        view.reset(active_chips)
        if self._chk_animate.isChecked():
            view.animate(plot_coord)
        else:
            view.draw_all(plot_coord)

    def _on_hit_thread_finished(self):
        self._hit_thread = None
        self._hit_worker = None
        self._btn_hits.setEnabled(True)

    # ==================================================================
    # NOISE ANALYSIS (modo Acquisition)
    # ==================================================================
    def _run_noise_analysis(self):
        path = self._selected_file
        if path is None or path.suffix.lower() != ROOT_EXT:
            self._log_write("[WARN] Select a .root file to run the noise analysis.")
            return

        if self._noise_thread is not None and self._noise_thread.isRunning():
            self._log_write("[WARN] A noise analysis is already running.")
            return

        worker = NoiseAnalysisWorker(str(path), self._spin_repeats.value())
        self._noise_worker = worker
        self._btn_noise.setEnabled(False)
        self._log_write(f"[START] Running NoiseAnalysis on {path.name}...")
        self._noise_thread = QThread(self)
        worker.moveToThread(self._noise_thread)
        self._noise_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.analysed.connect(self._on_noise_analysed)
        worker.finished.connect(self._noise_thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._noise_thread.finished.connect(self._on_noise_thread_finished)
        self._noise_thread.finished.connect(self._noise_thread.deleteLater)
        self._noise_thread.start()

    def _on_noise_analysed(self, root_path: str, pixel_counts: dict, stats: dict):
        path = Path(root_path)
        n = stats["n_noisy_pixels"]
        self._log_write(f"[OK]   NoiseAnalysis complete: {n} noisy pixel(s) "
                        f"({stats['noise_percentage']:.4f} %).")
        if n == 0:
            self._log_write(f"[INFO] No noisy pixels in {path.name}: nothing to mask.")
            return

        view = NoiseMaskView(path, pixel_counts, stats)
        view.log_message.connect(self._log_write)
        self._add_result_tab(path, view, kind="noise")

    def _on_noise_thread_finished(self):
        self._noise_thread = None
        self._noise_worker = None
        self._btn_noise.setEnabled(True)

    def _save_trajectories(self, view: TrajectoryView):
        try:
            try:
                output_dir = SystemConfig.get_root_path().parent / "plots"
            except Exception:
                output_dir = None
            saved = view.save(output_dir)
            self._log_write(f"[OK]   Plot saved: {saved}")
        except Exception as e:
            self._log_write(f"[ERROR] Cannot save plot: {e}")


    # ==================================================================
    # Lista de recientes / fichero seleccionado
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

        self._recent_list.clearSelection()
        if path is not None:
            for i in range(self._recent_list.count()):
                it = self._recent_list.item(i)
                if it.data(Qt.UserRole) == str(path):
                    self._recent_list.setCurrentItem(it)
                    break
            self._log_write(f"[INFO] File selected: {path.name}")

        self._populate_chips(path)

        if path is not None:
            self.file_selected.emit(path)

    # ==================================================================
    # Chips del fichero
    # ==================================================================
    @contextmanager
    def _busy(self):
        """Cursor de espera + señal plots_loading (para parar el timer de estado)."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.plots_loading.emit(True)
        try:
            yield
        finally:
            self.plots_loading.emit(False)
            QApplication.restoreOverrideCursor()

    def _populate_chips(self, path: Path | None):
        """Rellena la lista de chips leyendo el .root seleccionado."""
        # Vaciar
        while self._chips_grid.count():
            w = self._chips_grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self._chip_checks = []
        self._chips_all.blockSignals(True)
        self._chips_all.setChecked(False)
        self._chips_all.blockSignals(False)
        self._chips_all.setEnabled(False)
        self._btn_plot.setEnabled(False)

        if path is None:
            self._chips_status.setText("Select a file to list its chips.")
            return
        if self.mode != MODE_CALIBRATION or path.suffix.lower() != ROOT_EXT:
            self._chips_status.setText("")
            return

        try:
            with self._busy():
                chips = discover_chips(path)
        except Exception as e:
            self._chips_status.setText(f"Cannot read chips: {e}")
            self._log_write(f"[ERROR] Cannot read chips from {path.name}: {e}")
            return

        if not chips:
            self._chips_status.setText("No chips found in this file.")
            return

        self._chips_status.setText(f"{len(chips)} chip(s) found.")
        for i, (h, c) in enumerate(chips):
            cb = QCheckBox(f"H{h} · Chip {c}")
            cb.setChecked(True)
            cb.toggled.connect(self._on_chip_toggled)
            self._chips_grid.addWidget(cb, i // 2, i % 2)
            self._chip_checks.append(((h, c), cb))

        self._chips_all.blockSignals(True)
        self._chips_all.setChecked(True)
        self._chips_all.blockSignals(False)
        self._chips_all.setEnabled(True)
        self._btn_plot.setEnabled(True)

    def _on_chips_all_toggled(self, checked: bool):
        for _key, cb in self._chip_checks:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._btn_plot.setEnabled(checked and bool(self._chip_checks))

    def _on_chip_toggled(self, _checked: bool):
        states = [cb.isChecked() for _k, cb in self._chip_checks]
        self._chips_all.blockSignals(True)
        self._chips_all.setChecked(bool(states) and all(states))
        self._chips_all.blockSignals(False)
        self._btn_plot.setEnabled(any(states))

    # ==================================================================
    # PLOT
    # ==================================================================
    def _plot(self):
        path = self._selected_file
        if path is None or self.mode != MODE_CALIBRATION:
            return

        analysis = detect_analysis(path)
        if analysis is None:
            self._log_write(f"[WARN] Cannot infer the analysis type from '{path.name}'.")
            return

        chips = [key for key, cb in self._chip_checks if cb.isChecked()]
        if not chips:
            self._log_write("[WARN] No chips selected.")
            return

        col_start, col_end = SystemConfig.get_active_columns()
        self._log_write(f"[INFO] Plotting {analysis.upper()} — "
                        f"{len(chips)} chip(s) from {path.name}...")

        inner = QTabWidget()
        try:
            with self._busy():
                for h, c in chips:
                    widget = build_chip_plots_widget(
                        analysis, str(path), h, c, col_start, col_end,
                        log=self._log_write,
                    )
                    inner.addTab(widget, f"H{h} · Chip {c}")
        except Exception as e:
            inner.deleteLater()
            self._log_write(f"[ERROR] Cannot plot {path.name}: {e}")
            return

        self._add_result_tab(path, inner)
        self._log_write("[OK]   Plots ready.")

    def _add_result_tab(self, path: Path, widget: QWidget, kind: str = ""):
        """Añade la pestaña de resultados de `path`; si ya existía, la reemplaza.

        `kind` distingue resultados distintos del mismo fichero (p. ej. hits y ruido).
        """
        key = f"{path}#{kind}" if kind else str(path)
        old = self._file_tabs.get(key)
        if old is not None:
            self._close_result_tab(self._results_tabs.indexOf(old))

        title = f"{path.stem} · {kind}" if kind else path.stem
        idx = self._results_tabs.addTab(widget, title)
        self._set_tab_close_button(self._results_tabs, idx)
        self._results_tabs.setTabToolTip(idx, str(path))
        self._results_tabs.setCurrentIndex(idx)
        self._file_tabs[key] = widget
        self._update_results_visibility()

    def _set_tab_close_button(self, tabs: QTabWidget, index: int) -> None:
        button = QToolButton(tabs)
        button.setAutoRaise(True)
        button.setCursor(Qt.ArrowCursor)
        button.setToolTip("Close tab")
        button.setIcon(tabs.style().standardIcon(tabs.style().SP_TitleBarCloseButton))
        button.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 0px; }"
            "QToolButton:hover { background: transparent; }"
        )
        # El índice cambia al cerrar otras pestañas: resolverlo en el clic
        widget = tabs.widget(index)
        button.clicked.connect(lambda *_: self._close_result_tab(tabs.indexOf(widget)))
        tabs.tabBar().setTabButton(index, QTabBar.RightSide, button)

    def _close_result_tab(self, index: int):
        if index < 0:
            return
        widget = self._results_tabs.widget(index)
        self._results_tabs.removeTab(index)
        for key, w in list(self._file_tabs.items()):
            if w is widget:
                del self._file_tabs[key]
        if widget is not None:
            widget.deleteLater()
        self._update_results_visibility()

    def _update_results_visibility(self):
        has_tabs = self._results_tabs.count() > 0
        self._results_tabs.setVisible(has_tabs)
        self._results_placeholder.setVisible(not has_tabs)

    # ==================================================================
    # Helper log
    # ==================================================================
    def _log_write(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
        self.logger.info(msg)