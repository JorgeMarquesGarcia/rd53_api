"""calibration_tab.py - Tab de calibración del sistema RD53A."""
from __future__ import annotations
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QCheckBox,
    QTabWidget, QSpacerItem, QSizePolicy, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from src.config.system_config import SystemConfig
from src.calibration.scans.scurve      import SCurveScan
from src.calibration.scans.threqu      import ThresholdEqualizationScan
from src.calibration.scans.noise       import NoiseScan
from src.calibration.scans.pixel_alive import PixelAliveScan
from src.calibration.scans.gain        import GainScan
from src.calibration.scans.gainopt     import GainOptimizationScan
import src.core.num_manager as num_mgr
from src.core.results_finder import ANALYSIS_FILE_SUFFIX
from src.gui.gui_utils import append_log, install_tab_close_button, make_log_view
from src.plotter.calibration_view import build_chip_plots_widget, discover_chips

# ---------------------------------------------------------------------------
# Análisis disponibles. Pendiente: que el usuario pueda modificar Vthreshold_LIN
# ---------------------------------------------------------------------------
AVAILABLE_ANALYSES = [
    ("scurve",     "S-Curve Scan",              "Threshold & noise measurement via injection scan"),
    ("threqu",     "Threshold Equalization",     "TDAC equalization to uniform threshold"),
    ("noise",      "Noise Scan",                 "Identify noisy pixels at operating threshold"),
    ("pixelalive", "Pixel Alive",                "Verify pixel responsivity with injection"),
    ("gainopt",    "Gain Optimization",          "Tune KRUM_CURR_LIN so TargetCharge reaches max ToT (updates the XML)"),
    ("gain",       "Gain Scan",                  "ToT vs injected charge, per-pixel linear fit"),
]

SCAN_MAP = {
    "scurve":     SCurveScan,
    "threqu":     ThresholdEqualizationScan,
    "noise":      NoiseScan,
    "pixelalive": PixelAliveScan,
    "gainopt":    GainOptimizationScan,
    "gain":       GainScan,
}


# ---------------------------------------------------------------------------
# Worker thread para lanzar calibraciones sin bloquear la GUI
# ---------------------------------------------------------------------------
class CalibrationWorker(QObject):
    log_message  = pyqtSignal(str)
    finished     = pyqtSignal(str, bool, int)   # (analysis_key, success, run_number)
    all_finished = pyqtSignal()

    def __init__(self, analyses: list[str]):
        super().__init__()
        self._analyses = analyses
        self._abort    = False
        self._current_scan = None

    def run(self):
        # all_finished se emite siempre: si no, la GUI se quedaría con ABORT
        # activo y el hilo sin cerrar.
        try:
            self._run_sequence()
        except Exception as e:
            self.log_message.emit(f"[ERROR] Calibration sequence: {e}")
        finally:
            self._current_scan = None
            self.all_finished.emit()

    def _run_sequence(self):
        active_chips = SystemConfig.get_active_hw_chips()
        if not active_chips:
            self.log_message.emit("[ERROR] No active chips configured.")
            return

        # Configurar num_manager con la ruta al RunNumber.txt
        run_number_path = Path(SystemConfig.get_txt_base_dir()) / "RunNumber.txt"
        num_mgr.configure(run_number_path)

        for analysis in self._analyses:
            if self._abort:
                self.log_message.emit("[ABORTED] Sequence aborted by user.")
                break

            self.log_message.emit(
                f"\n[START] Running {analysis.upper()} "
                f"with XML active chips={active_chips}..."
            )
            scan_cls = SCAN_MAP.get(analysis)
            if scan_cls is None:
                self.log_message.emit(f"[ERROR] Unknown analysis: {analysis}")
                self.finished.emit(analysis, False, -1)
                continue

            try:
                # Leer run number ANTES de lanzar el scan
                run_number = num_mgr.get()
                self.log_message.emit(f"[INFO]  Run number: {num_mgr.get_formatted()}")

                # El XML ya contiene todos los chips activos; este scan debe correr una sola vez.
                scan = scan_cls()
                self._current_scan = scan
                scan._line_callback = lambda line: self.log_message.emit(f"  {line}")
                output = scan.run()
                for msg in scan.report:
                    self.log_message.emit(msg)

                if scan.scan_ended:
                    self.log_message.emit(f"[OK]    {analysis.upper()} completed "
                                          f"(Run {num_mgr.get_formatted()} before increment).")
                    self.finished.emit(analysis, True, run_number)
                else:
                    self.log_message.emit(f"[WARN]  {analysis.upper()} finished but "
                                          f"scan_ended=False.")
                    self.log_message.emit(f"[OUTPUT] {output[-300:] if output else '(empty)'}")
                    self.finished.emit(analysis, False, run_number)

            except Exception as e:
                self.log_message.emit(f"[ERROR] {analysis.upper()}: {e}")
                self.finished.emit(analysis, False, -1)
            finally:
                self._current_scan = None

    def abort(self):
        self._abort = True
        scan = self._current_scan
        if scan is not None:
            scan.abort()


# ---------------------------------------------------------------------------
# CalibrationTab
# ---------------------------------------------------------------------------
class CalibrationTab(QWidget):
    plots_loading = pyqtSignal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger   = logging.getLogger("CalibrationTab")
        self._checks: dict[str, QCheckBox] = {}
        self._worker: CalibrationWorker | None = None
        self._thread: QThread | None = None
        self._file_tabs: dict[str, QWidget] = {}   # ruta .root -> pestaña de resultados
        self._completed = 0
        self._total = 0
        self._build_ui()
        self.logger.info("CalibrationTab inicializado.")

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # Splitter superior: controles | log
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self._build_control_panel())
        top_splitter.addWidget(self._build_log_panel())
        top_splitter.setSizes([340, 700])

        # Splitter vertical: controles+log | plots
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(top_splitter)
        v_splitter.addWidget(self._build_plot_panel())
        v_splitter.setSizes([340, 460])

        main.addWidget(v_splitter)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("CALIBRATION SEQUENCE")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # Lista de análisis con checkboxes
        analyses_group = QGroupBox("AVAILABLE ANALYSES")
        ag_layout = QVBoxLayout(analyses_group)
        ag_layout.setSpacing(6)

        for key, name, desc in AVAILABLE_ANALYSES:
            cb = QCheckBox(name)
            cb.setToolTip(desc)
            cb.setChecked(False)
            self._checks[key] = cb
            ag_layout.addWidget(cb)

        layout.addWidget(analyses_group)

        # Botones
        btn_single = QPushButton("RUN SELECTED")
        btn_single.setObjectName("btn_launch")
        btn_single.setToolTip("Run the checked analyses in sequence")
        btn_single.clicked.connect(self._run_selected)
        layout.addWidget(btn_single)

        btn_all = QPushButton("RUN ALL")
        btn_all.setToolTip("Run all analyses in order")
        btn_all.clicked.connect(self._run_all)
        layout.addWidget(btn_all)

        self._btn_abort = QPushButton("ABORT")
        self._btn_abort.setStyleSheet(
            "QPushButton { color: #FF5252; border-color: #FF5252; }"
            "QPushButton:hover { background: #FF5252; color: #1A1D23; }"
        )
        self._btn_abort.setEnabled(False)
        self._btn_abort.clicked.connect(self._abort)
        layout.addWidget(self._btn_abort)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            "QProgressBar { border: 1px solid #2E3340; border-radius: 3px; "
            "background: #0F1117; color: #212529; text-align: center; }"
            "QProgressBar::chunk { background: #00E5FF; }"
        )
        layout.addWidget(self._progress)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("EXECUTION LOG")
        title.setObjectName("section_title")
        header.addWidget(title)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(100)
        clear_btn.clicked.connect(lambda: self._log.clear())
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._log = make_log_view("Calibration output will appear here...")
        layout.addWidget(self._log)

        return panel

    def _build_plot_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        title = QLabel("RESULTS")
        title.setObjectName("section_title")
        layout.addWidget(title)

        self._plot_tabs = QTabWidget()
        self._plot_tabs.setTabsClosable(True)
        self._plot_tabs.tabCloseRequested.connect(self._close_plot_tab)
        self._plot_tabs.setStyleSheet(
            "QTabBar::tab { padding: 4px 12px; font-size: 10px; }"
            "QTabBar::tab:selected { background: #1A1D23; color: #00E5FF; }"
            "QTabBar::close-button { width: 12px; height: 12px; background: transparent; border: none; }"
            "QTabBar::close-button:hover { background: transparent; }"
        )
        layout.addWidget(self._plot_tabs)

        return panel

    # ------------------------------------------------------------------
    # Lógica de lanzamiento
    # ------------------------------------------------------------------
    def _run_selected(self):
        selected = [k for k, cb in self._checks.items() if cb.isChecked()]
        if not selected:
            self._log_write("[WARN] No analyses selected.")
            return
        self._launch(selected)

    def _run_all(self):
        self._launch([k for k, _, _ in AVAILABLE_ANALYSES])

    def _launch(self, analyses: list[str]):
        if self._thread and self._thread.isRunning():
            self._log_write("[WARN] A calibration is already running.")
            return

        self._log_write(f"[INFO] Launching: {', '.join(a.upper() for a in analyses)}")
        self._progress.setValue(0)
        self._btn_abort.setEnabled(True)
        self._completed = 0
        self._total     = len(analyses)

        self._worker = CalibrationWorker(analyses)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log_message.connect(self._log_write)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.all_finished.connect(self._on_all_finished)

        self._thread.start()

    def _abort(self):
        if self._worker:
            self._worker.abort()
            self._log_write("[ABORTED] Abort requested...")
            self._btn_abort.setEnabled(False)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_analysis_finished(self, analysis: str, success: bool, run_number: int):
        self._completed += 1
        pct = int(self._completed / self._total * 100) if self._total else 100
        self._progress.setValue(pct)
        if success and run_number >= 0:
            self.plots_loading.emit(True)
            try:
                self._load_plots(analysis, run_number)
            finally:
                self.plots_loading.emit(False)

    def _on_all_finished(self):
        self._btn_abort.setEnabled(False)
        self._progress.setValue(100)
        self._log_write("[DONE] All calibrations completed.")

        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None

    def _load_plots(self, analysis: str, run_number: int):
        """Carga los plots del análisis terminado: una subpestaña por chip."""
        pattern = ANALYSIS_FILE_SUFFIX.get(analysis, "")
        run_str = str(run_number).zfill(6)
        # Carpeta "ROOT output directory" de la pestaña Config (misma que Analysis/Acquisition)
        try:
            results_dir = SystemConfig.get_root_path()
        except Exception:
            self._log_write(
                "[WARN] 'ROOT output directory' is not set in the Config tab — "
                "cannot locate the results."
            )
            return
        root_path = results_dir / f"Run{run_str}_{pattern}.root"

        if not root_path.exists():
            self._log_write(f"[WARN] ROOT file not found: {root_path.name}")
            return

        self._log_write(f"[INFO] Loading plots from: {root_path.name}")

        try:
            col_start, col_end = SystemConfig.get_active_columns()
            chips = discover_chips(root_path)
        except Exception as e:
            self._log_write(f"[WARN] Cannot load plots: {e}")
            return

        if not chips:
            self._log_write(f"[WARN] No chips found in {root_path.name}")
            return

        inner = QTabWidget()
        for h, c in chips:
            widget = build_chip_plots_widget(
                analysis, str(root_path), h, c, col_start, col_end,
                log=self._log_write,
            )
            inner.addTab(widget, f"H{h} · Chip {c}")

        # Volver a dibujar el mismo fichero reemplaza su pestaña en lugar de duplicarla
        old = self._file_tabs.get(str(root_path))
        if old is not None:
            self._close_plot_tab(self._plot_tabs.indexOf(old))

        idx = self._plot_tabs.addTab(inner, root_path.stem)
        install_tab_close_button(self._plot_tabs, idx, self._close_plot_tab)
        self._plot_tabs.setTabToolTip(idx, str(root_path))
        self._plot_tabs.setCurrentIndex(idx)
        self._file_tabs[str(root_path)] = inner
        self._log_write(f"[OK]   {len(chips)} chip(s) plotted.")

    def _close_plot_tab(self, index: int):
        """Cierra una pestaña de resultados y libera sus canvas."""
        if index < 0:
            return
        widget = self._plot_tabs.widget(index)
        self._plot_tabs.removeTab(index)
        for key, w in list(self._file_tabs.items()):
            if w is widget:
                del self._file_tabs[key]
        if widget is not None:
            widget.deleteLater()

    # ------------------------------------------------------------------
    # Helper log
    # ------------------------------------------------------------------
    def _log_write(self, msg: str):
        append_log(self._log, msg)
        self.logger.info(msg)