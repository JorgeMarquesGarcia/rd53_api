"""acquisition_tab.py - Tab de adquisición del sistema RD53A."""
from __future__ import annotations
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton,
    QTextEdit, QSpinBox, QRadioButton,
    QButtonGroup, QSpacerItem, QSizePolicy,
    QScrollArea, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from src.config.system_config import SystemConfig

"""Tengo que poder modificar el threshold desde la GUI"""
# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class TimedAcquisitionWorker(QObject):
    log_message = pyqtSignal(str)
    finished    = pyqtSignal(bool)

    def __init__(self, chips: list[tuple[int, int]], scan_time: int,
                 triggers: int = 0,
                 vthresh_per_chip: dict[tuple[int, int], int] | None = None):
        super().__init__()
        self._chips             = chips
        self._scan_time         = scan_time
        self._triggers          = triggers
        self._vthresh_per_chip  = vthresh_per_chip or {}
        self._scan              = None

    def run(self):
        self.log_message.emit(
            f"[START] Physics scan  chips={self._chips}  time={self._scan_time}s  "
            f"triggers={self._triggers}  vthresh={self._vthresh_per_chip}"
        )
        try:
            from src.acquisition.scans.physics import PhysicsScan

            self._scan = PhysicsScan(
                chips=self._chips,
                scan_time=self._scan_time,
                timeout=max(self._scan_time * 2, self._scan_time + 120),
                triggers=self._triggers,
                vthresh_per_chip=self._vthresh_per_chip,
            )
            self._scan._line_callback = lambda line: self.log_message.emit(f"[DAQ] {line}")
            self._scan.run()

            if self._scan.scan_ended:
                self.log_message.emit("[OK]   Scan completed successfully.")
                self.finished.emit(True)
            else:
                self.log_message.emit("[WARN] Scan ended without end-pattern — possible abort.")
                self.finished.emit(False)

        except Exception as e:
            self.log_message.emit(f"[ERROR] {e}")
            self.finished.emit(False)

    def abort(self):
        if self._scan is not None:
            self._scan.abort()


class ContinuousAcquisitionWorker(QObject):
    """Placeholder para modo continuo — lógica real pendiente."""
    log_message = pyqtSignal(str)
    finished    = pyqtSignal(bool)

    def __init__(self, chips: list[tuple[int, int]]):
        super().__init__()
        self._chips = chips
        self._abort = False

    def run(self):
        self.log_message.emit("[START] Continuous acquisition started (placeholder)...")
        import time
        i = 0
        while not self._abort:
            time.sleep(1)
            i += 1
            self.log_message.emit(f"[INFO]  {i}s elapsed (continuous mode)...")
        self.log_message.emit("[STOP] Continuous acquisition stopped.")
        self.finished.emit(True)

    def abort(self):
        self._abort = True


# ---------------------------------------------------------------------------
# AcquisitionTab
# ---------------------------------------------------------------------------

class AcquisitionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger  = logging.getLogger("AcquisitionTab")
        self._worker = None
        self._thread: QThread | None = None
        self._last_hit_analysis = None   # HitAnalysis tras el último scan timed
        self._current_plotter   = None   # CoincidencePlotter activo
        self._build_ui()
        self.logger.info("AcquisitionTab inicializado.")

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self._build_control_panel())
        left_splitter.addWidget(self._build_log_panel())
        left_splitter.setSizes([520, 280])
        left_splitter.setMaximumWidth(420)

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(self._build_trajectory_panel())
        h_splitter.setSizes([380, 900])

        main.addWidget(h_splitter)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("ACQUISITION CONTROL")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # --- Modo ---
        mode_group = QGroupBox("ACQUISITION MODE")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(8)

        self._radio_timed = QRadioButton("Timed  — acquire for N seconds, then plot")
        self._radio_cont  = QRadioButton("Continuous  — acquire until stopped")
        self._radio_timed.setChecked(True)
        self._mode_group  = QButtonGroup()
        self._mode_group.addButton(self._radio_timed, 0)
        self._mode_group.addButton(self._radio_cont,  1)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        mode_layout.addWidget(self._radio_timed)
        mode_layout.addWidget(self._radio_cont)
        layout.addWidget(mode_group)

        # --- Parámetros ---
        params_group = QGroupBox("SCAN PARAMETERS")
        params_layout = QHBoxLayout(params_group)
        params_layout.setSpacing(12)

        self._lbl_scan_time = QLabel("Scan time (s):")
        params_layout.addWidget(self._lbl_scan_time)
        self._scan_time = QSpinBox()
        self._scan_time.setRange(1, 3600)
        self._scan_time.setValue(30)
        self._scan_time.setMaximumWidth(80)
        params_layout.addWidget(self._scan_time)
        params_layout.addStretch()
        layout.addWidget(params_group)

        # --- Chips activos (informativo) ---
        chips_group = QGroupBox("ACTIVE CHIPS")
        chips_layout = QVBoxLayout(chips_group)
        self._chips_label = QLabel("Configure chips in the Config tab.")
        self._chips_label.setStyleSheet("color: #505868; font-size: 11px;")
        chips_layout.addWidget(self._chips_label)
        layout.addWidget(chips_group)

        # --- Progreso ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminado
        self._progress.hide()
        layout.addWidget(self._progress)

        # --- Botones ---
        self._btn_start = QPushButton("START ACQUISITION")
        self._btn_start.setObjectName("btn_launch")
        self._btn_start.clicked.connect(self._start_acquisition)
        layout.addWidget(self._btn_start)

        self._btn_abort = QPushButton("ABORT")
        self._btn_abort.setStyleSheet(
            "QPushButton { color: #FF5252; border-color: #FF5252; }"
            "QPushButton:hover { background: #FF5252; color: #1A1D23; }"
        )
        self._btn_abort.setEnabled(False)
        self._btn_abort.clicked.connect(self._abort)
        layout.addWidget(self._btn_abort)
        layout.addWidget(self._build_physics_params_group())
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("ACQUISITION LOG")
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
        self._log.setPlaceholderText("Acquisition output will appear here...")
        layout.addWidget(self._log)

        return panel

    def _build_trajectory_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("PARTICLE TRAJECTORIES")
        title.setObjectName("section_title")
        header.addWidget(title)
        header.addStretch()

        self._btn_show_traj = QPushButton("Show Trajectories")
        self._btn_show_traj.setEnabled(False)
        self._btn_show_traj.clicked.connect(self._show_trajectories)
        header.addWidget(self._btn_show_traj)

        self._btn_save_traj = QPushButton("Save Plot")
        self._btn_save_traj.setEnabled(False)
        self._btn_save_traj.clicked.connect(self._save_trajectories)
        header.addWidget(self._btn_save_traj)

        layout.addLayout(header)

        self._traj_placeholder = QLabel(
            "Particle trajectories will appear here after acquisition."
        )
        self._traj_placeholder.setAlignment(Qt.AlignCenter)
        self._traj_placeholder.setStyleSheet(
            "color: #3A4050; font-size: 13px; border: 1px dashed #2E3340;"
        )
        layout.addWidget(self._traj_placeholder)

        self._traj_container = QScrollArea()
        self._traj_container.setWidgetResizable(True)
        self._traj_container.hide()
        layout.addWidget(self._traj_container)

        return panel

    # ------------------------------------------------------------------
    # Lógica de modo
    # ------------------------------------------------------------------
    def _on_mode_changed(self):
        timed = self._mode_group.checkedId() == 0
        self._scan_time.setEnabled(timed)
        self._lbl_scan_time.setEnabled(timed)

    # ------------------------------------------------------------------
    # Arranque / abort
    # ------------------------------------------------------------------
    def _start_acquisition(self):
        if self._thread and self._thread.isRunning():
            self._log_write("[WARN] Acquisition already running.")
            return
        
        self._log_write(f"[DEBUG] ph2_acf_dir={SystemConfig.get_ph2_acf_dir()}")
        self._log_write(f"[DEBUG] txt_base_dir={SystemConfig.get_txt_base_dir()}")
        chips = SystemConfig.get_active_hw_chips()
        if not chips:
            self._log_write("[ERROR] No active chips. Configure chips in the Config tab.")
            return

        timed = self._mode_group.checkedId() == 0

        if timed:
            self._worker = TimedAcquisitionWorker(
                chips=chips,
                scan_time=self._scan_time.value(),
                triggers=self._spin_triggers.value(),
                vthresh_per_chip={
                    key: spin.value()
                    for key, spin in self._vthresh_spinboxes.items()
                },
            )
        else:
            self._worker = ContinuousAcquisitionWorker(chips=chips)

        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_message.connect(self._log_write)
        self._worker.finished.connect(self._on_finished)

        self._btn_start.setEnabled(False)
        self._btn_abort.setEnabled(True)
        self._btn_show_traj.setEnabled(False)
        self._btn_save_traj.setEnabled(False)
        self._progress.show()

        self._thread.start()

    def _abort(self):
        if self._worker:
            self._worker.abort()
        self._btn_abort.setEnabled(False)
        self._log_write("[ABORTED] Abort requested...")

    def _on_finished(self, success: bool):
        self._progress.hide()
        self._btn_abort.setEnabled(False)
        self._btn_start.setEnabled(True)

        if self._thread:
            self._thread.quit()
            self._thread.wait()

        if not success:
            self._log_write("[DONE] Acquisition ended (no trajectories available).")
            return

        # Solo en modo timed tiene sentido ejecutar análisis automáticamente
        if self._mode_group.checkedId() == 0:
            self._run_analysis()

    def _build_physics_params_group(self) -> QGroupBox:
        from src.chip.detector_geometry import DETECTOR_LAYOUT

        group = QGroupBox("PHYSICS PARAMETERS")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Triggers — global
        trig_row = QHBoxLayout()
        trig_row.addWidget(QLabel("Triggers (global):"))
        self._spin_triggers = QSpinBox()
        self._spin_triggers.setRange(0, 9999)
        self._spin_triggers.setValue(0)
        self._spin_triggers.setToolTip("0 = unlimited triggers per event")
        self._spin_triggers.setMaximumWidth(90)
        trig_row.addWidget(self._spin_triggers)
        trig_row.addStretch()
        layout.addLayout(trig_row)

        # Vthreshold_LIN — por chip activo
        thresh_label = QLabel("Vthreshold_LIN  (per chip):")
        thresh_label.setStyleSheet("font-size: 11px; color: #8A95A5; margin-top: 4px;")
        layout.addWidget(thresh_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(130)
        scroll.setFrameShape(scroll.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        self._vthresh_spinboxes: dict[tuple[int, int], QSpinBox] = {}

        try:
            active_set = set(SystemConfig.get_active_hw_chips())
            for layer in DETECTOR_LAYOUT.values():
                hybrid = layer["hybrid"]
                offset = layer["rd53_offset"]
                for chip_local in layer["chips"]:
                    rd53_hw = chip_local + offset
                    if (hybrid, rd53_hw) not in active_set:
                        continue
                    row = QHBoxLayout()
                    lbl = QLabel(f"  H{hybrid} · Chip {rd53_hw}  ({layer['label']}):")
                    lbl.setStyleSheet("font-size: 11px;")
                    lbl.setMinimumWidth(200)
                    row.addWidget(lbl)
                    spin = QSpinBox()
                    spin.setRange(0, 1000)
                    spin.setValue(350)
                    spin.setMaximumWidth(80)
                    row.addWidget(spin)
                    row.addStretch()
                    inner_layout.addLayout(row)
                    self._vthresh_spinboxes[(hybrid, rd53_hw)] = spin
        except Exception:
            inner_layout.addWidget(QLabel("  Configure chips first."))

        if not self._vthresh_spinboxes:
            inner_layout.addWidget(QLabel("  No active chips — configure in Config tab."))

        scroll.setWidget(inner)
        layout.addWidget(scroll)
        return group

    # ------------------------------------------------------------------
    # Análisis post-scan (modo timed)
    # ------------------------------------------------------------------
    def _run_analysis(self):
        """
        Tras el scan, carga el ROOT más reciente y ejecuta HitAnalysis.
        Habilita los botones de visualización si hay tracks.
        """
        self._log_write("[INFO] Running HitAnalysis on latest ROOT file...")
        try:
            from src.analysis.analysis_hit import HitAnalysis

            root_manager = SystemConfig.create_root_manager()
            root_manager.load()

            self._last_hit_analysis = HitAnalysis(root_manager)
            n = len(self._last_hit_analysis.plot_coord)
            self._log_write(f"[OK]   HitAnalysis complete: {n} tracks reconstructed.")

            if n == 0:
                self._log_write("[WARN] No tracks found in this acquisition.")
                return

            self._btn_show_traj.setEnabled(True)
            self._btn_save_traj.setEnabled(True)
            self._log_write("[DONE] Ready to visualize trajectories.")

        except Exception as e:
            self._log_write(f"[ERROR] Analysis failed: {e}")
            self.logger.exception("HitAnalysis error")

    # ------------------------------------------------------------------
    # Visualización
    # ------------------------------------------------------------------
    def _show_trajectories(self):
        if self._last_hit_analysis is None:
            self._log_write("[WARN] No analysis data available.")
            return
        try:
            from src.plotter.plotter_trajectory import CoincidencePlotter

            self._current_plotter = CoincidencePlotter(
                plot_coord_data=self._last_hit_analysis.plot_coord,
                active_chips=SystemConfig.get_active_chip_keys(),
            )
            self._current_plotter.plot_multiple_events()
            self._log_write(
                f"[INFO] Showing {len(self._last_hit_analysis.plot_coord)} trajectories."
            )
        except Exception as e:
            self._log_write(f"[ERROR] Cannot show trajectories: {e}")

    def _save_trajectories(self):
        if self._current_plotter is None:
            self._log_write("[WARN] Open the trajectory viewer first.")
            return
        try:
            try:
                output_dir = SystemConfig.get_root_path().parent / "plots"
            except Exception:
                output_dir = None
            path = self._current_plotter.save(output_dir)
            self._log_write(f"[OK]   Plot saved: {path}")
        except Exception as e:
            self._log_write(f"[ERROR] Cannot save plot: {e}")

    # ------------------------------------------------------------------
    # API pública — llamada desde MainWindow cuando se aplica config
    # ------------------------------------------------------------------
    def on_config_applied(self):
        """Actualiza el label de chips activos cuando cambia la configuración."""
        try:
            keys = SystemConfig.get_active_chip_keys()
            self._chips_label.setText(f"Active: {keys}")
            self._chips_label.setStyleSheet("color: #69F0AE; font-size: 11px;")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helper log
    # ------------------------------------------------------------------
    def _log_write(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
        self.logger.info(msg)