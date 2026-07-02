"""acquisition_tab.py - Tab de adquisición del sistema RD53A."""
from __future__ import annotations
import logging
import time
import threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton,
    QTextEdit, QSpinBox, QRadioButton,
    QButtonGroup, QSpacerItem, QSizePolicy,
    QScrollArea, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject

from src.config.system_config import SystemConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_SIZE_LIMIT_BYTES: int  = 1 * 1024 ** 3   # 1 GB — rotar el fichero .raw
LIVE_REFRESH_MS: int       = 60_000          # ciclo de visualización: cada 60 s
DAQ_POLL_INTERVAL: float   = 2.0             # segundos entre polls del .raw (rotación)
DAQ_MAX_RETRIES: int       = 5               # reintentos si el DAQ no arranca
DAQ_RETRY_DELAY: float     = 8.0             # segundos entre reintentos


# ===========================================================================
# Worker — Timed
# ===========================================================================

class TimedAcquisitionWorker(QObject):
    log_message = pyqtSignal(str)
    finished    = pyqtSignal(bool)

    def __init__(self, chips: list[tuple[int, int]], scan_time: int,
                 triggers: int = 0,
                 vthresh_per_chip: dict[tuple[int, int], int] | None = None):
        super().__init__()
        self._chips            = chips
        self._scan_time        = scan_time
        self._triggers         = triggers
        self._vthresh_per_chip = vthresh_per_chip or {}
        self._scan             = None

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

            if not self._scan.scan_ended:
                self.log_message.emit("[WARN] Scan ended without end-pattern — possible abort.")
                self.finished.emit(False)
                return

            self.log_message.emit("[OK]   Scan completed successfully.")
            self.log_message.emit("[START] Readback (CMSITminiDAQ -b)...")

            _, raw_path = self._scan.run_raw2root(
                xml_path=SystemConfig.get_xml_path(),
                results_dir=SystemConfig.get_root_path(),
                line_callback=lambda line: self.log_message.emit(f"[DAQ] {line}"),
            )
            self.log_message.emit(f"[OK]   Readback saved: {raw_path}")
            self.finished.emit(True)

        except Exception as e:
            self.log_message.emit(f"[ERROR] {e}")
            self.finished.emit(False)

    def abort(self):
        if self._scan is not None:
            self._scan.abort()


# ===========================================================================
# Worker — Raw2Root (una terminal separada, un ciclo)
# ===========================================================================

class Raw2RootWorker(QObject):
    """
    Convierte el .raw de un ciclo completo a .root usando run_raw2root().
    Corre en su propio QThread para no bloquear ni el DAQ ni la GUI.
    """
    log_message = pyqtSignal(str)
    root_ready  = pyqtSignal(str)   # path absoluto al .root generado
    finished    = pyqtSignal()

    def __init__(self, xml_path: Path, results_dir: Path):
        super().__init__()
        self._xml_path    = xml_path
        self._results_dir = results_dir

    def run(self):
        self._dbg("Converting .raw → .root …")
        try:
            from src.acquisition.scans.physics import PhysicsScan

            # Instancia mínima solo para acceder a run_raw2root()
            scan = PhysicsScan.__new__(PhysicsScan)

            _, root_path = scan.run_raw2root(
                xml_path=self._xml_path,
                results_dir=self._results_dir,
                line_callback=lambda line: self.log_message.emit(f"[RAW2ROOT] {line}"),
            )
            self._dbg(f"Done → {root_path.name}")
            self.root_ready.emit(str(root_path))

        except Exception as e:
            self.log_message.emit(f"[RAW2ROOT ERROR] {e}")
        finally:
            self.finished.emit()

    def _dbg(self, msg: str):
        self.log_message.emit(f"[RAW2ROOT] {msg}")


# ===========================================================================
# Worker — Conversión liviana para ciclo de visualización (cada 60 s)
# ===========================================================================

class LiveRaw2RootWorker(QObject):
    """
    Convierte el .raw ACTIVO (en plena adquisición) a .root para el ciclo
    de visualización de 60 s.  Es independiente del Raw2RootWorker de rotación:
    ese se lanza al llegar a 1 GB; este se lanza cada minuto sobre lo que haya.
    """
    log_message = pyqtSignal(str)
    root_ready  = pyqtSignal(str)   # path al .root generado
    finished    = pyqtSignal()

    def __init__(self, xml_path: Path, results_dir: Path):
        super().__init__()
        self._xml_path    = xml_path
        self._results_dir = results_dir

    def run(self):
        self.log_message.emit("[LIVE R2R] Converting active .raw snapshot → .root …")
        try:
            from src.acquisition.scans.physics import PhysicsScan

            scan = PhysicsScan.__new__(PhysicsScan)
            _, root_path = scan.run_raw2root(
                xml_path=self._xml_path,
                results_dir=self._results_dir,
                line_callback=lambda line: self.log_message.emit(f"[LIVE R2R] {line}"),
            )
            self.log_message.emit(f"[LIVE R2R] Snapshot ready → {root_path.name}")
            self.root_ready.emit(str(root_path))
        except Exception as e:
            self.log_message.emit(f"[LIVE R2R ERROR] {e}")
        finally:
            self.finished.emit()


# ===========================================================================
# Worker — Visualización interactiva (hilo aparte para no bloquear la GUI)
# ===========================================================================

class TrajectoryAnimationWorker(QObject):
    """
    Ejecuta InteractiveCoincidencePlotter.plot_multiple_events() en un hilo
    separado porque usa time.sleep() internamente y bloquearía la GUI si
    se llamara desde el hilo principal o desde el QTimer.
    """
    log_message = pyqtSignal(str)
    finished    = pyqtSignal()

    def __init__(self, plot_coord_data: list[dict], active_chips: list[tuple],
                 plotter_ref: list):  # plotter_ref = [None] — se rellena aquí
        super().__init__()
        self._plot_coord_data = plot_coord_data
        self._active_chips    = active_chips
        self._plotter_ref     = plotter_ref  # lista de un elemento para pasar por referencia

    def run(self):
        try:
            from src.plotter.trajectory_interactive import InteractiveCoincidencePlotter

            plotter = InteractiveCoincidencePlotter(
                plot_coord_data=self._plot_coord_data,
                active_chips=self._active_chips,
            )
            self._plotter_ref[0] = plotter
            self.log_message.emit(
                f"[LIVE] Animating {len(self._plot_coord_data)} tracks…"
            )
            plotter.plot_multiple_events()
            self.log_message.emit("[LIVE] Animation complete.")
        except Exception as e:
            self.log_message.emit(f"[LIVE ERROR] Animation failed: {e}")
        finally:
            self.finished.emit()


# ===========================================================================
# Worker — Standalone (continuo con rotación de .raw)
# ===========================================================================

class StandaloneAcquisitionWorker(QObject):
    """
    Modo standalone: adquisición continua con rotación automática de .raw.

    Ciclo de vida:
      1. Lanza CMSITminiDAQ -f <xml> -c physics -t -1 en un thread interno.
         Si el comando falla (conexión no levantada, etc.) reintenta hasta
         DAQ_MAX_RETRIES veces con DAQ_RETRY_DELAY segundos de espera.
      2. Hace polling del .raw cada DAQ_POLL_INTERVAL segundos.
         Emite debug por señal en cada poll.
      3. Cuando el .raw ≥ RAW_SIZE_LIMIT_BYTES:
         a. Para el DAQ (scan.abort())
         b. Emite raw_cycle_done(xml_path, results_dir) para que la GUI
            lance Raw2RootWorker en paralelo
         c. Elimina el .raw ya procesado (el .root lo gestiona Raw2RootWorker)
         d. Vuelve al paso 1 (nuevo ciclo — transparente para el usuario)
      4. Si abort_flag se activa, sale limpiamente.
    """

    log_message    = pyqtSignal(str)
    raw_cycle_done = pyqtSignal(Path, Path)   # (xml_path, results_dir)
    finished       = pyqtSignal()

    def __init__(
        self,
        chips: list[tuple[int, int]],
        triggers: int = 0,
        vthresh_per_chip: dict[tuple[int, int], int] | None = None,
        raw_size_limit: int = RAW_SIZE_LIMIT_BYTES,
    ):
        super().__init__()
        self._chips            = chips
        self._triggers         = triggers
        self._vthresh_per_chip = vthresh_per_chip or {}
        self._raw_size_limit   = raw_size_limit
        self._abort_flag       = False
        self._current_scan     = None
        self._cycle            = 0

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def abort(self):
        self._abort_flag = True
        if self._current_scan is not None:
            try:
                self._current_scan.abort()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------

    def run(self):
        self._dbg(
            f"Standalone start | chips={self._chips} "
            f"triggers={self._triggers} vthresh={self._vthresh_per_chip} "
            f"size_limit={self._raw_size_limit // 1024**2} MB"
        )

        while not self._abort_flag:
            self._cycle += 1
            self._dbg(f"━━━ CYCLE {self._cycle} START ━━━")

            success, xml_path, results_dir = self._run_one_cycle()

            if not success:
                if not self._abort_flag:
                    self._dbg("Cycle ended unexpectedly — stopping standalone.")
                break

            self._dbg(f"━━━ CYCLE {self._cycle} END — emitting raw_cycle_done ━━━")
            self.raw_cycle_done.emit(xml_path, results_dir)

        self._dbg("Standalone acquisition stopped.")
        self.finished.emit()

    # ------------------------------------------------------------------
    # Un ciclo de adquisición (con reintentos)
    # ------------------------------------------------------------------

    def _run_one_cycle(self) -> tuple[bool, Path | None, Path | None]:
        """
        Lanza el DAQ con -t -1 (con reintentos si falla el arranque),
        luego espera a que el .raw supere el límite o llegue el abort.

        Returns (success, xml_path, results_dir).
        """
        from src.acquisition.scans.physics import PhysicsScan

        for attempt in range(1, DAQ_MAX_RETRIES + 1):
            if self._abort_flag:
                return False, None, None

            self._dbg(f"DAQ launch attempt {attempt}/{DAQ_MAX_RETRIES}")

            try:
                scan = PhysicsScan(
                    chips=self._chips,
                    scan_time=-1,
                    timeout=None,
                    triggers=self._triggers,
                    vthresh_per_chip=self._vthresh_per_chip,
                )
                self._current_scan = scan
                scan._line_callback = lambda line: self.log_message.emit(f"[DAQ] {line}")

                # Lanzar run() en thread interno para poder hacer polling
                daq_started = threading.Event()
                daq_done    = threading.Event()
                daq_error   = [None]

                def _daq_thread():
                    try:
                        # Señalamos "arrancado" cuando run() empieza
                        # (antes de que termine — run() bloquea hasta que el DAQ para)
                        daq_started.set()
                        scan.run()
                    except Exception as exc:
                        daq_error[0] = exc
                    finally:
                        daq_done.set()

                t = threading.Thread(target=_daq_thread, daemon=True)
                t.start()

                # Esperar a que el thread arranque efectivamente
                daq_started.wait(timeout=5)
                self._dbg(f"DAQ thread running (attempt {attempt})")

                # Polling del .raw hasta que supere el límite o abort/fin de DAQ
                results_dir  = self._resolve_results_dir()
                raw_path     = self._poll_raw(daq_done, results_dir)

                if self._abort_flag:
                    scan.abort()
                    daq_done.wait(timeout=10)
                    return False, None, None

                if raw_path is not None:
                    # .raw llegó al límite → detener el DAQ de este ciclo
                    size_mb = raw_path.stat().st_size // 1024 ** 2
                    self._dbg(f".raw reached {size_mb} MB — rotating (aborting DAQ)")
                    scan.abort()
                    daq_done.wait(timeout=10)

                    xml_path = SystemConfig.get_xml_path()
                    self._dbg(f"Cycle {self._cycle} complete | xml={xml_path} results={results_dir}")
                    return True, xml_path, results_dir

                # Si daq_done se activó sin que raw_path sea válido → DAQ terminó solo
                if daq_done.is_set():
                    if daq_error[0] is not None:
                        self._dbg(f"DAQ thread error: {daq_error[0]}")
                    else:
                        self._dbg("DAQ ended on its own (no .raw limit reached)")
                    # Tratar como fallo de arranque y reintentar
                    self._dbg(f"Retrying in {DAQ_RETRY_DELAY}s …")
                    time.sleep(DAQ_RETRY_DELAY)
                    continue

            except Exception as e:
                self._dbg(f"Exception in cycle attempt {attempt}: {e}")
                self.log_message.emit(f"[STANDALONE ERROR] {e}")

                if attempt < DAQ_MAX_RETRIES:
                    self._dbg(f"Retrying in {DAQ_RETRY_DELAY}s …")
                    time.sleep(DAQ_RETRY_DELAY)

        self._dbg(f"All {DAQ_MAX_RETRIES} attempts failed — giving up.")
        return False, None, None

    # ------------------------------------------------------------------
    # Polling del .raw
    # ------------------------------------------------------------------

    def _poll_raw(self, daq_done: threading.Event, results_dir: Path) -> Path | None:
        """
        Polling en bucle hasta que:
          - el .raw ≥ límite          → devuelve Path
          - abort solicitado           → devuelve None
          - DAQ terminó solo           → devuelve None

        Imprime el tamaño actual en cada iteración (debug).
        """
        poll_n = 0
        while not self._abort_flag and not daq_done.is_set():
            time.sleep(DAQ_POLL_INTERVAL)
            poll_n += 1

            raw_path = self._find_latest_raw(results_dir)
            if raw_path is None:
                self._dbg(f"[poll #{poll_n}] No .raw found yet in {results_dir}")
                continue

            size_b  = raw_path.stat().st_size
            size_mb = size_b / 1024 ** 2
            limit_mb = self._raw_size_limit / 1024 ** 2
            self._dbg(
                f"[poll #{poll_n}] {raw_path.name}  "
                f"{size_mb:.1f} MB / {limit_mb:.0f} MB  "
                f"({100*size_b/self._raw_size_limit:.1f}%)"
            )

            if size_b >= self._raw_size_limit:
                return raw_path

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_results_dir(self) -> Path:
        try:
            return SystemConfig.get_root_path().parent
        except Exception:
            return Path("results")

    @staticmethod
    def _find_latest_raw(results_dir: Path) -> Path | None:
        try:
            raws = sorted(
                results_dir.glob("**/*.raw"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return raws[0] if raws else None
        except Exception:
            return None

    def _cleanup_raw(self, raw_path: Path) -> None:
        """Borra el .raw de ciclo anterior para liberar disco."""
        try:
            if raw_path and raw_path.exists():
                raw_path.unlink()
                self._dbg(f"Deleted {raw_path.name}")
        except Exception as e:
            self._dbg(f"Cleanup warning: {e}")

    def _dbg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[STANDALONE {ts}] {msg}")


# ===========================================================================
# AcquisitionTab
# ===========================================================================

class AcquisitionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("AcquisitionTab")

        # Estado — Timed
        self._worker: QObject | None = None
        self._thread: QThread | None = None
        self._last_hit_analysis      = None
        self._current_plotter        = None

        # Estado — Standalone
        self._standalone_worker: StandaloneAcquisitionWorker | None = None
        self._standalone_thread: QThread | None                     = None
        self._r2r_thread: QThread | None        = None   # rotación 1 GB
        self._live_r2r_thread: QThread | None   = None   # snapshot cada 60 s
        self._anim_thread: QThread | None       = None
        self._latest_root_path: str | None      = None
        self._standalone_track_count: int       = 0
        self._plotter_holder: list              = [None]  # ref al InteractiveCoincidencePlotter

        # Timer de refresco de visualización — independiente del ciclo de rotación
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(LIVE_REFRESH_MS)   # 60 s
        self._refresh_timer.timeout.connect(self._trigger_live_snapshot)

        self._build_ui()
        self.logger.info("AcquisitionTab inicializado.")

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
        left_splitter.setSizes([520, 280])
        left_splitter.setMaximumWidth(420)

        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(self._build_trajectory_panel())
        h_splitter.setSizes([380, 900])

        main.addWidget(h_splitter)

    def _build_control_panel(self) -> QWidget:
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        title = QLabel("ACQUISITION CONTROL")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # --- Modo ---
        mode_group  = QGroupBox("ACQUISITION MODE")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(8)

        self._radio_timed = QRadioButton("Timed  — acquire for N seconds, then plot")
        self._radio_cont  = QRadioButton("Standalone  — continuous acquisition with live trajectories")
        self._radio_timed.setChecked(True)
        self._mode_group = QButtonGroup()
        self._mode_group.addButton(self._radio_timed, 0)
        self._mode_group.addButton(self._radio_cont,  1)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        mode_layout.addWidget(self._radio_timed)
        mode_layout.addWidget(self._radio_cont)
        layout.addWidget(mode_group)

        # --- Parámetros ---
        params_group  = QGroupBox("SCAN PARAMETERS")
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

        # --- Chips activos ---
        chips_group  = QGroupBox("ACTIVE CHIPS")
        chips_layout = QVBoxLayout(chips_group)
        self._chips_label = QLabel("Configure chips in the Config tab.")
        self._chips_label.setStyleSheet("color: #505868; font-size: 11px;")
        chips_layout.addWidget(self._chips_label)
        layout.addWidget(chips_group)

        # --- Status standalone (oculto en modo timed) ---
        self._standalone_status = QLabel("")
        self._standalone_status.setStyleSheet(
            "color: #69F0AE; font-size: 11px; padding: 2px 0;"
        )
        self._standalone_status.hide()
        layout.addWidget(self._standalone_status)

        # --- Progreso ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
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
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header    = QHBoxLayout()
        title     = QLabel("ACQUISITION LOG")
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
        panel  = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title  = QLabel("PARTICLE TRAJECTORIES")
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

    # ==================================================================
    # Modo changed
    # ==================================================================

    def _on_mode_changed(self):
        timed = self._mode_group.checkedId() == 0
        self._scan_time.setEnabled(timed)
        self._lbl_scan_time.setEnabled(timed)
        self._standalone_status.setVisible(not timed)

    # ==================================================================
    # Arranque
    # ==================================================================

    def _start_acquisition(self):
        if self._thread and self._thread.isRunning():
            self._log_write("[WARN] Acquisition already running.")
            return
        if self._standalone_thread and self._standalone_thread.isRunning():
            self._log_write("[WARN] Acquisition already running.")
            return

        self._log_write(f"[DEBUG] ph2_acf_dir={SystemConfig.get_ph2_acf_dir()}")
        self._log_write(f"[DEBUG] txt_base_dir={SystemConfig.get_txt_base_dir()}")

        chips = SystemConfig.get_active_hw_chips()
        if not chips:
            self._log_write("[ERROR] No active chips. Configure chips in the Config tab.")
            return

        if self._mode_group.checkedId() == 0:
            self._start_timed(chips)
        else:
            self._start_standalone(chips)

    # ------------------------------------------------------------------
    # Timed
    # ------------------------------------------------------------------

    def _start_timed(self, chips: list[tuple[int, int]]):
        self._worker = TimedAcquisitionWorker(
            chips=chips,
            scan_time=self._scan_time.value(),
            triggers=self._spin_triggers.value(),
            vthresh_per_chip={k: s.value() for k, s in self._vthresh_spinboxes.items()},
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_message.connect(self._log_write)
        self._worker.finished.connect(self._on_timed_finished)

        self._set_running_ui(True)
        self._thread.start()

    def _on_timed_finished(self, success: bool):
        self._set_running_ui(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        if not success:
            self._log_write("[DONE] Acquisition ended (no trajectories available).")
            return
        self._run_analysis_timed()

    # ------------------------------------------------------------------
    # Standalone
    # ------------------------------------------------------------------

    def _start_standalone(self, chips: list[tuple[int, int]]):
        vthresh = {k: s.value() for k, s in self._vthresh_spinboxes.items()}
        self._standalone_track_count = 0
        self._latest_root_path       = None
        self._last_hit_analysis      = None
        self._plotter_holder         = [None]

        self._standalone_worker = StandaloneAcquisitionWorker(
            chips=chips,
            triggers=self._spin_triggers.value(),
            vthresh_per_chip=vthresh,
        )
        self._standalone_thread = QThread()
        self._standalone_worker.moveToThread(self._standalone_thread)
        self._standalone_thread.started.connect(self._standalone_worker.run)
        self._standalone_worker.log_message.connect(self._log_write)
        self._standalone_worker.raw_cycle_done.connect(self._on_raw_cycle_done)
        self._standalone_worker.finished.connect(self._on_standalone_finished)

        self._set_running_ui(True)
        self._standalone_status.setText("⬤  Acquiring…  |  Tracks: 0")
        self._standalone_status.show()

        self._refresh_timer.start()
        self._standalone_thread.start()

    def _on_raw_cycle_done(self, xml_path: Path, results_dir: Path):
        """
        El .raw del ciclo completado está listo.
        Lanzamos Raw2RootWorker en su propio hilo.
        Si ya hay uno corriendo del ciclo anterior, lo dejamos terminar y
        omitimos este (el DAQ ya está corriendo un nuevo ciclo de todas formas).
        """
        if self._r2r_thread and self._r2r_thread.isRunning():
            self._log_write(
                "[STANDALONE] raw2root from previous cycle still running — "
                "skipping conversion for this cycle."
            )
            return

        worker = Raw2RootWorker(xml_path=xml_path, results_dir=results_dir)
        self._r2r_thread = QThread()
        worker.moveToThread(self._r2r_thread)
        self._r2r_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.root_ready.connect(self._on_root_ready)
        worker.finished.connect(self._r2r_thread.quit)
        self._r2r_thread.start()

    def _on_root_ready(self, root_path: str):
        """
        Callback del ciclo de ROTACIÓN (1 GB).
        Actualiza la referencia al .root más reciente y dispara la visualización.
        """
        self._latest_root_path = root_path
        self._log_write(f"[STANDALONE] Rotation ROOT ready: {Path(root_path).name}")
        self._launch_analysis_and_animation(root_path)

    def _trigger_live_snapshot(self):
        """
        Llamado por el QTimer cada 60 s.
        Lanza LiveRaw2RootWorker sobre el .raw activo para obtener un .root
        con los datos acumulados hasta ese momento, sin esperar a 1 GB.
        """
        if not (self._standalone_thread and self._standalone_thread.isRunning()):
            return

        # Si ya hay una conversión live en curso, esperar al siguiente tick
        if self._live_r2r_thread and self._live_r2r_thread.isRunning():
            self._log_write("[LIVE] Previous snapshot conversion still running — skipping tick.")
            return

        try:
            xml_path    = SystemConfig.get_xml_path()
            results_dir = self._resolve_results_dir()
        except Exception as e:
            self._log_write(f"[LIVE] Cannot start snapshot: {e}")
            return

        self._log_write("[LIVE] 60 s tick — converting .raw snapshot …")
        worker = LiveRaw2RootWorker(xml_path=xml_path, results_dir=results_dir)
        self._live_r2r_thread = QThread()
        worker.moveToThread(self._live_r2r_thread)
        self._live_r2r_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.root_ready.connect(self._on_live_root_ready)
        worker.finished.connect(self._live_r2r_thread.quit)
        self._live_r2r_thread.start()

    def _on_live_root_ready(self, root_path: str):
        """Callback del ciclo de VISUALIZACIÓN (60 s)."""
        self._log_write(f"[LIVE] Snapshot ROOT ready: {Path(root_path).name}")
        self._launch_analysis_and_animation(root_path)

    def _launch_analysis_and_animation(self, root_path: str):
        """
        Punto de entrada común para ambos ciclos (rotación y visualización).
        Ejecuta HitAnalysis sobre el .root indicado y lanza la animación
        en un hilo aparte (InteractiveCoincidencePlotter usa time.sleep y
        bloquearía la GUI si se llamara aquí directamente).
        """
        # No lanzar nueva animación si la anterior sigue corriendo
        if self._anim_thread and self._anim_thread.isRunning():
            self._log_write("[LIVE] Animation still running — skipping this refresh.")
            return

        try:
            from src.analysis.analysis_hit import HitAnalysis

            root_manager = SystemConfig.create_root_manager(path=root_path)
            root_manager.load()

            analysis = HitAnalysis(root_manager)
            n_new    = len(analysis.plot_coord)

            if n_new == 0:
                self._log_write("[LIVE] No tracks in ROOT file.")
                return

            self._last_hit_analysis       = analysis
            self._standalone_track_count += n_new
            self._standalone_status.setText(
                f"⬤  Acquiring…  |  Tracks this session: {self._standalone_track_count}"
            )
            self._btn_save_traj.setEnabled(True)

            anim_worker = TrajectoryAnimationWorker(
                plot_coord_data=analysis.plot_coord,
                active_chips=SystemConfig.get_active_chip_keys(),
                plotter_ref=self._plotter_holder,
            )
            self._anim_thread = QThread()
            anim_worker.moveToThread(self._anim_thread)
            self._anim_thread.started.connect(anim_worker.run)
            anim_worker.log_message.connect(self._log_write)
            anim_worker.finished.connect(self._anim_thread.quit)
            self._anim_thread.start()

            self._log_write(
                f"[LIVE] Launching animation — {n_new} new tracks "
                f"(session total: {self._standalone_track_count})"
            )

        except Exception as e:
            self._log_write(f"[LIVE ERROR] {e}")
            self.logger.exception("Standalone refresh error")

    def _resolve_results_dir(self) -> Path:
        try:
            return SystemConfig.get_root_path().parent
        except Exception:
            return Path("results")

    def _on_standalone_finished(self):
        self._refresh_timer.stop()
        self._set_running_ui(False)
        self._standalone_status.setText("⬤  Stopped")

        if self._standalone_thread:
            self._standalone_thread.quit()
            self._standalone_thread.wait()

        # Último snapshot por si quedaron datos sin visualizar
        if self._latest_root_path and Path(self._latest_root_path).exists():
            self._launch_analysis_and_animation(self._latest_root_path)

        self._log_write(
            f"[STANDALONE] Session ended — {self._standalone_track_count} total tracks."
        )

    # ==================================================================
    # Abort
    # ==================================================================

    def _abort(self):
        if self._worker:
            self._worker.abort()
        if self._standalone_worker:
            self._standalone_worker.abort()
        self._btn_abort.setEnabled(False)
        self._log_write("[ABORTED] Abort requested…")

    # ==================================================================
    # UI helpers
    # ==================================================================

    def _set_running_ui(self, running: bool):
        self._btn_start.setEnabled(not running)
        self._btn_abort.setEnabled(running)
        self._btn_show_traj.setEnabled(False)
        self._btn_save_traj.setEnabled(False)
        if running:
            self._progress.show()
        else:
            self._progress.hide()

    # ==================================================================
    # Physics params group
    # ==================================================================

    def _build_physics_params_group(self) -> QGroupBox:
        group  = QGroupBox("PHYSICS PARAMETERS")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        trig_row = QHBoxLayout()
        trig_row.addWidget(QLabel("Triggers (unlimited = 0):"))
        self._spin_triggers = QSpinBox()
        self._spin_triggers.setRange(0, 9999)
        self._spin_triggers.setValue(0)
        self._spin_triggers.setToolTip("0 = unlimited triggers per event")
        self._spin_triggers.setMaximumWidth(90)
        trig_row.addWidget(self._spin_triggers)
        trig_row.addStretch()
        layout.addLayout(trig_row)

        thresh_label = QLabel("Vthreshold_LIN  (per chip):")
        thresh_label.setStyleSheet("font-size: 11px; color: #8A95A5; margin-top: 4px;")
        layout.addWidget(thresh_label)

        self._vthresh_scroll = QScrollArea()
        self._vthresh_scroll.setWidgetResizable(True)
        self._vthresh_scroll.setMaximumHeight(130)
        self._vthresh_scroll.setFrameShape(self._vthresh_scroll.NoFrame)
        layout.addWidget(self._vthresh_scroll)

        self._vthresh_spinboxes: dict[tuple[int, int], QSpinBox] = {}
        self._refresh_vthresh_spinboxes()
        return group

    def _refresh_vthresh_spinboxes(self) -> None:
        from src.chip.detector_geometry import DETECTOR_LAYOUT

        prev_values = {k: s.value() for k, s in self._vthresh_spinboxes.items()}
        self._vthresh_spinboxes.clear()

        inner        = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(0, 0, 0, 0)

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
                    lbl = QLabel(f"  H{hybrid} . Chip {rd53_hw}  ({layer['label']}):")
                    lbl.setStyleSheet("font-size: 11px;")
                    lbl.setMinimumWidth(200)
                    row.addWidget(lbl)
                    spin = QSpinBox()
                    spin.setRange(0, 1000)
                    spin.setValue(prev_values.get((hybrid, rd53_hw), 350))
                    spin.setMaximumWidth(80)
                    row.addWidget(spin)
                    row.addStretch()
                    inner_layout.addLayout(row)
                    self._vthresh_spinboxes[(hybrid, rd53_hw)] = spin
        except Exception:
            inner_layout.addWidget(QLabel("  Configure chips first."))

        if not self._vthresh_spinboxes:
            inner_layout.addWidget(QLabel("  No active chips — configure in Config tab."))

        self._vthresh_scroll.setWidget(inner)

    # ==================================================================
    # Análisis post-scan (modo timed)
    # ==================================================================

    def _run_analysis_timed(self):
        self._log_write("[INFO] Running HitAnalysis on latest ROOT file...")
        try:
            from src.analysis.analysis_hit import HitAnalysis

            root_manager = SystemConfig.create_root_manager()
            root_manager.load()
            self._last_hit_analysis = HitAnalysis(root_manager)
            n = len(self._last_hit_analysis.plot_coord)
            self._log_write(f"[OK]   HitAnalysis complete: {n} tracks reconstructed.")

            if n == 0:
                self._log_write("[WARN] No tracks found.")
                return

            self._btn_show_traj.setEnabled(True)
            self._btn_save_traj.setEnabled(True)
            self._log_write("[DONE] Ready to visualize trajectories.")

        except Exception as e:
            self._log_write(f"[ERROR] Analysis failed: {e}")
            self.logger.exception("HitAnalysis error")

    # ==================================================================
    # Visualización
    # ==================================================================

    def _show_trajectories(self):
        if self._last_hit_analysis is None:
            self._log_write("[WARN] No analysis data available.")
            return
        try:
            from src.plotter.trajectory_interactive import InteractiveCoincidencePlotter

            self._current_plotter = InteractiveCoincidencePlotter(
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
        # En standalone el plotter vive en self._plotter_holder[0]
        plotter = self._current_plotter or self._plotter_holder[0]
        if plotter is None:
            self._log_write("[WARN] No active plotter — show trajectories first.")
            return
        try:
            try:
                output_dir = SystemConfig.get_root_path().parent / "plots"
            except Exception:
                output_dir = None
            path = plotter.save(output_dir)
            self._log_write(f"[OK]   Plot saved: {path}")
        except Exception as e:
            self._log_write(f"[ERROR] Cannot save plot: {e}")

    # ==================================================================
    # API pública
    # ==================================================================

    def on_config_applied(self):
        try:
            keys = SystemConfig.get_active_hw_chips()
            self._chips_label.setText(f"Active: {keys}")
            self._chips_label.setStyleSheet("color: #69F0AE; font-size: 11px;")
        except Exception:
            pass
        self._refresh_vthresh_spinboxes()

    # ==================================================================
    # Helper log
    # ==================================================================

    def _log_write(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )
        self.logger.info(msg)