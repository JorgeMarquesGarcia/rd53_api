"""calibration_tab.py - Tab de calibración del sistema RD53A."""
from __future__ import annotations
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QCheckBox,
    QListWidget, QListWidgetItem, QTextEdit,
    QTabWidget, QScrollArea, QGridLayout,
    QSpacerItem, QSizePolicy, QProgressBar,
)

from pathlib import Path
from src.config.system_config import SystemConfig
from src.calibration.scans.scurve      import SCurveScan
from src.calibration.scans.threqu      import ThresholdEqualizationScan
from src.calibration.scans.noise       import NoiseScan
from src.calibration.scans.pixel_alive import PixelAliveScan
import src.core.num_manager as num_mgr

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor

from src.config.system_config import SystemConfig
from src.plotter.plotter_base import PlotterBase, ANALYSIS_PLOTS
from src.plotter.heatmap import (
    PixelAlivePlotter, ToT2DPlotter, TDAC2DPlotter, Masked2DPlotter
)
from src.plotter.histogram1d import (
    Threshold1DPlotter, Occ1DPlotter, ToT1DPlotter,
    TDAC1DPlotter, ThrEqualizationPlotter
)
from src.plotter.scurve import SCurvePlotter

# ---------------------------------------------------------------------------
# Análisis disponibles
# ---------------------------------------------------------------------------
AVAILABLE_ANALYSES = [
    ("scurve",     "S-Curve Scan",              "Threshold & noise measurement via injection scan"),
    ("threqu",     "Threshold Equalization",     "TDAC equalization to uniform threshold"),
    ("noise",      "Noise Scan",                 "Identify noisy pixels at operating threshold"),
    ("pixelalive", "Pixel Alive",                "Verify pixel responsivity with injection"),
]

# Canvas names por plot_key — igual que en test_plotter
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
}

MASKED_PLOTTERS = {"PixelAlive", "ToT2D", "TDAC2D", "Masked2D"}


# ---------------------------------------------------------------------------
# Worker thread para lanzar calibraciones sin bloquear la GUI
# ---------------------------------------------------------------------------
class CalibrationWorker(QObject):
    log_message  = pyqtSignal(str)
    finished     = pyqtSignal(str, bool, int)   # (analysis_key, success, run_number)
    all_finished = pyqtSignal()
    plots_loading = pyqtSignal(bool)  # True=empezando, False=terminado

    

    def __init__(self, analyses: list[str]):
        super().__init__()
        self._analyses = analyses
        self._abort    = False

    def run(self):


        SCAN_MAP = {
            "scurve":     SCurveScan,
            "threqu":     ThresholdEqualizationScan,
            "noise":      NoiseScan,
            "pixelalive": PixelAliveScan,
        }

        hybrid_id = SystemConfig.get_active_hybrids()[0]
        chip_id   = SystemConfig.get_active_chips()[0]

        # Configurar num_manager con la ruta al RunNumber.txt
        run_number_path = Path(SystemConfig.get_txt_base_dir()) / "RunNumber.txt"
        num_mgr.configure(run_number_path)

        for analysis in self._analyses:
            if self._abort:
                self.log_message.emit("[ABORTED] Sequence aborted by user.")
                break

            self.log_message.emit(f"\n[START] Running {analysis.upper()} "
                                  f"(Hybrid {hybrid_id}, Chip {chip_id})...")
            scan_cls = SCAN_MAP.get(analysis)
            if scan_cls is None:
                self.log_message.emit(f"[ERROR] Unknown analysis: {analysis}")
                self.finished.emit(analysis, False, -1)
                continue

            try:
                # Leer run number ANTES de lanzar el scan
                run_number = num_mgr.get()
                self.log_message.emit(f"[INFO]  Run number: {num_mgr.get_formatted()}")

                scan = scan_cls(hybrid_id=hybrid_id, rd53_id=chip_id)
                self._current_scan = scan
                scan._line_callback = lambda line: self.log_message.emit(f"  {line}")
                output = scan.run()

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

        self.all_finished.emit()

    def abort(self):
        self._abort = True
        if hasattr(self, '_current_scan') and self._current_scan:
            self._current_scan.abort()
            self._current_scan = None


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
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(lambda: self._log.clear())
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Calibration output will appear here...")
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
        self._plot_tabs.setStyleSheet(
            "QTabBar::tab { padding: 4px 12px; font-size: 10px; }"
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
        pct = int(self._completed / self._total * 100)
        self._progress.setValue(pct)
        if success and run_number >= 0:
            self.plots_loading.emit(True)
            self._load_plots(analysis, run_number)
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
        """Carga los plots del análisis terminado en el panel de resultados."""
        from pathlib import Path

        pattern_map = {
            "scurve":     "SCurve",
            "threqu":     "ThrEqualization",
            "noise":      "NoiseScan",
            "pixelalive": "PixelAlive",
            #"fine_noise": "Physics_Board000"
        }
        pattern  = pattern_map.get(analysis, "")
        run_str  = str(run_number).zfill(6)
        results_dir = Path(SystemConfig.get_txt_base_dir()) / "Results" #Esto hay que cambiarlo, el usuario ya le da el path de ese directorio
        root_path   = results_dir / f"Run{run_str}_{pattern}.root"

        if not root_path.exists():
            self._log_write(f"[WARN] ROOT file not found: {root_path.name}")
            return

        self._log_write(f"[INFO] Loading plots from: {root_path.name}")

        try:
            col_start, col_end = SystemConfig.get_active_columns()
            chip_dir = SystemConfig.get_chip_dir()
        except Exception as e:
            self._log_write(f"[WARN] Cannot load plots: {e}")
            return

        root_path = str(root_path)

        keys = ANALYSIS_PLOTS.get(analysis, [])
        if not keys:
            return

        tab_widget = QWidget()
        grid = QGridLayout(tab_widget)
        grid.setSpacing(8)
        col_count = 2

        for idx, key in enumerate(keys):
            canvas_tmpl = CANVAS_NAMES.get(key)
            if canvas_tmpl is None:
                continue

            # Usar primer chip activo para el canvas path
            active = SystemConfig.get_active_hybrids()
            h = active[0] if active else 0
            c = SystemConfig.get_active_chips()[0] if SystemConfig.get_active_chips() else 0
            canvas_name = canvas_tmpl.format(h=h, c=c)
            canvas_path = f"{chip_dir}/{canvas_name}"

            try:
                if key in MASKED_PLOTTERS:
                    cls_map = {
                        "PixelAlive": PixelAlivePlotter,
                        "ToT2D":      ToT2DPlotter,
                        "TDAC2D":     TDAC2DPlotter,
                        "Masked2D":   Masked2DPlotter,
                    }
                    plotter = cls_map[key](root_path, canvas_path, col_start, col_end)
                else:
                    plotter = PlotterBase.for_key(key, root_path, canvas_path)

                widget = plotter.get_canvas()
                grid.addWidget(widget, idx // col_count, idx % col_count)
            except Exception as e:
                lbl = QLabel(f"⚠ Error en '{key}':\n{e}")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    "color: #B71C1C; background: #1A0000; "
                    "border: 1px solid #4A0000; padding: 8px;"
                )
                grid.addWidget(lbl, idx // col_count, idx % col_count)
                self._log_write(f"[WARN] Plot '{key}': {e}")

        scroll = QScrollArea()
        scroll.setWidget(tab_widget)
        scroll.setWidgetResizable(True)

        label = dict((k, n) for k, n, _ in AVAILABLE_ANALYSES).get(analysis, analysis.upper())
        self._plot_tabs.addTab(scroll, label)
        self._plot_tabs.setCurrentWidget(scroll)

    # ------------------------------------------------------------------
    # Helper log
    # ------------------------------------------------------------------
    def _log_write(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
        self.logger.info(msg)