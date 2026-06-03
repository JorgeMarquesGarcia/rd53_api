"""acquisition_tab.py - Tab de adquisición del sistema RD53A."""
from __future__ import annotations
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QLineEdit,
    QFileDialog, QTextEdit, QSpinBox, QRadioButton,
    QButtonGroup, QSpacerItem, QSizePolicy,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from rd53_api.config.system_config import SystemConfig


# ---------------------------------------------------------------------------
# Worker thread para adquisición
# ---------------------------------------------------------------------------
class AcquisitionWorker(QObject):
    log_message = pyqtSignal(str)
    finished    = pyqtSignal(bool)   # success

    def __init__(self, scan_time: int):
        super().__init__()
        self._scan_time = scan_time
        self._abort     = False

    def run(self):
        self.log_message.emit(f"[START] Acquisition started ({self._scan_time}s)...")
        try:
            # TODO: sustituir por llamada real al PhysicsScan
            # scan = PhysicsScan(chips=SystemConfig.get_active_chips(),
            #                    scan_time=self._scan_time)
            # scan.run()
            import time
            for i in range(self._scan_time):
                if self._abort:
                    self.log_message.emit("[ABORTED] Acquisition aborted.")
                    self.finished.emit(False)
                    return
                time.sleep(1)
                self.log_message.emit(f"[INFO]  {i+1}/{self._scan_time}s elapsed...")
            self.log_message.emit("[OK]   Acquisition completed.")
            self.finished.emit(True)
        except Exception as e:
            self.log_message.emit(f"[ERROR] {e}")
            self.finished.emit(False)

    def abort(self):
        self._abort = True


# ---------------------------------------------------------------------------
# AcquisitionTab
# ---------------------------------------------------------------------------
class AcquisitionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger  = logging.getLogger("AcquisitionTab")
        self._worker: AcquisitionWorker | None = None
        self._thread: QThread | None = None
        self._last_root_path: str | None = None  # última calibración de sesión
        self._build_ui()
        self.logger.info("AcquisitionTab inicializado.")

    # ------------------------------------------------------------------
    # Construcción UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(12)

        # Columna izquierda: controles arriba + log abajo
        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.addWidget(self._build_control_panel())
        left_splitter.addWidget(self._build_log_panel())
        left_splitter.setSizes([480, 280])
        left_splitter.setMaximumWidth(420)

        # Splitter horizontal: izquierda | trayectorias (todo el flanco derecho)
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

        # --- Calibración previa ---
        calib_group = QGroupBox("CALIBRATION SOURCE")
        calib_layout = QVBoxLayout(calib_group)
        calib_layout.setSpacing(8)

        # Radio buttons
        self._radio_last    = QRadioButton("Use last session calibration")
        self._radio_file    = QRadioButton("Load calibration file (.root)")
        self._radio_last.setChecked(True)
        self._btn_group     = QButtonGroup()
        self._btn_group.addButton(self._radio_last, 0)
        self._btn_group.addButton(self._radio_file, 1)
        self._btn_group.buttonClicked.connect(self._on_radio_changed)

        calib_layout.addWidget(self._radio_last)
        calib_layout.addWidget(self._radio_file)

        # File picker (oculto por defecto)
        file_row = QHBoxLayout()
        self._calib_edit = QLineEdit()
        self._calib_edit.setPlaceholderText("Select calibration .root file...")
        self._calib_edit.setEnabled(False)
        self._calib_browse = QPushButton("...")
        self._calib_browse.setMaximumWidth(70)
        self._calib_browse.setEnabled(False)
        self._calib_browse.clicked.connect(self._browse_calib)
        file_row.addWidget(self._calib_edit)
        file_row.addWidget(self._calib_browse)
        calib_layout.addLayout(file_row)

        # Estado de calibración cargada
        self._calib_status = QLabel("No calibration loaded.")
        self._calib_status.setStyleSheet("color: #FF5252; font-size: 10px;")
        calib_layout.addWidget(self._calib_status)

        layout.addWidget(calib_group)

        # --- Parámetros de adquisición ---
        params_group = QGroupBox("ACQUISITION PARAMETERS")
        params_layout = QHBoxLayout(params_group)
        params_layout.setSpacing(12)

        params_layout.addWidget(QLabel("Scan time (s):"))
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

        # --- Botones ---
        self._btn_load_calib = QPushButton("LOAD CALIBRATION")
        self._btn_load_calib.clicked.connect(self._load_calibration)
        layout.addWidget(self._btn_load_calib)

        self._btn_start = QPushButton("START ACQUISITION")
        self._btn_start.setObjectName("btn_launch")
        self._btn_start.setEnabled(False)
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

        # Placeholder hasta que haya datos
        self._traj_placeholder = QLabel(
            "Particle trajectories will appear here after acquisition."
        )
        self._traj_placeholder.setAlignment(Qt.AlignCenter)
        self._traj_placeholder.setStyleSheet(
            "color: #3A4050; font-size: 13px; border: 1px dashed #2E3340;"
        )
        layout.addWidget(self._traj_placeholder)

        # Contenedor para el canvas matplotlib (se añade tras adquisición)
        self._traj_container = QScrollArea()
        self._traj_container.setWidgetResizable(True)
        self._traj_container.hide()
        layout.addWidget(self._traj_container)

        return panel

    # ------------------------------------------------------------------
    # Lógica
    # ------------------------------------------------------------------
    def _on_radio_changed(self, btn):
        use_file = self._btn_group.checkedId() == 1
        self._calib_edit.setEnabled(use_file)
        self._calib_browse.setEnabled(use_file)

    def _browse_calib(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select calibration ROOT file", "", "ROOT files (*.root)"
        )
        if path:
            self._calib_edit.setText(path)

    def _load_calibration(self):
        """Carga la calibración seleccionada en SystemConfig."""
        use_file = self._btn_group.checkedId() == 1

        if use_file:
            path = self._calib_edit.text().strip()
            if not path or not Path(path).exists():
                self._log_write("[ERROR] Calibration file not found.")
                self._calib_status.setText("File not found.")
                self._calib_status.setStyleSheet("color: #FF5252; font-size: 10px;")
                return
            self._last_root_path = path
        else:
            # Usar última calibración de la sesión
            try:
                self._last_root_path = str(SystemConfig.get_root_path())
            except Exception:
                self._log_write("[ERROR] No session calibration available. "
                                "Run a calibration first or load a file.")
                self._calib_status.setText("No session calibration available.")
                self._calib_status.setStyleSheet("color: #FF5252; font-size: 10px;")
                return

        try:
            SystemConfig.set_root_path(self._last_root_path)
        except Exception as e:
            self._log_write(f"[ERROR] {e}")
            return

        # Actualizar UI
        fname = Path(self._last_root_path).name
        self._calib_status.setText(f"Loaded: {fname}")
        self._calib_status.setStyleSheet("color: #69F0AE; font-size: 10px;")
        self._log_write(f"[OK]   Calibration loaded: {fname}")

        # Actualizar chips activos
        try:
            active = SystemConfig.get_active_hybrids()
            chips  = SystemConfig.get_active_chips()
            self._chips_label.setText(
                f"Hybrids: {active}  |  Chips: {chips}"
            )
            self._chips_label.setStyleSheet("color: #69F0AE; font-size: 11px;")
        except Exception:
            pass

        self._btn_start.setEnabled(True)

    def _start_acquisition(self):
        if self._thread and self._thread.isRunning():
            self._log_write("[WARN] Acquisition already running.")
            return

        scan_time = self._scan_time.value()
        self._log_write(f"[INFO] Starting acquisition ({scan_time}s)...")
        self._btn_start.setEnabled(False)
        self._btn_abort.setEnabled(True)
        self._btn_show_traj.setEnabled(False)
        self._btn_save_traj.setEnabled(False)

        self._worker = AcquisitionWorker(scan_time)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.log_message.connect(self._log_write)
        self._worker.finished.connect(self._on_finished)

        self._thread.start()

    def _abort(self):
        if self._worker:
            self._worker.abort()
            self._btn_abort.setEnabled(False)
            self._log_write("[ABORTED] Abort requested...")

    def _on_finished(self, success: bool):
        self._btn_abort.setEnabled(False)
        self._btn_start.setEnabled(True)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        if success:
            self._btn_show_traj.setEnabled(True)
            self._btn_save_traj.setEnabled(True)
            self._log_write("[DONE] Ready to visualize trajectories.")

    def _show_trajectories(self):
        """Lanza el CoincidencePlotter con los datos de la última adquisición."""
        try:
            from rd53_api.plotter.plotter_trajectory import CoincidencePlotter
            # TODO: sustituir plot_data por los datos reales del análisis
            # result = AnalysisRunner.run(...)
            # plotter = CoincidencePlotter(result.plot_coord_data,
            #                             result.active_chips)
            active_chips = [
                (h, c)
                for h in SystemConfig.get_active_hybrids()
                for c in SystemConfig.get_active_chips()
            ]
            plotter = CoincidencePlotter([], active_chips)
            self._log_write("[INFO] Trajectory viewer opened.")
            self._current_plotter = plotter  # mantener referencia
        except Exception as e:
            self._log_write(f"[ERROR] Cannot show trajectories: {e}")

    def _save_trajectories(self):
        """Guarda el plot de trayectorias."""
        try:
            if not hasattr(self, "_current_plotter"):
                self._log_write("[WARN] No trajectory plot to save.")
                return
            output_dir = None
            try:
                output_dir = SystemConfig.get_root_path().parent / "plots"
            except Exception:
                pass
            path = self._current_plotter.save(output_dir)
            self._log_write(f"[OK]   Plot saved: {path}")
        except Exception as e:
            self._log_write(f"[ERROR] Cannot save plot: {e}")

    # ------------------------------------------------------------------
    # API pública — llamada desde MainWindow cuando se aplica config
    # ------------------------------------------------------------------
    def on_config_applied(self):
        try:
            active = SystemConfig.get_active_hybrids()
            chips  = SystemConfig.get_active_chips()
            self._chips_label.setText(f"Hybrids: {active}  |  Chips: {chips}")
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