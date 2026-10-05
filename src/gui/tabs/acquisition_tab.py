"""acquisition_tab.py - Tab de adquisición del sistema RD53A."""
from __future__ import annotations
import logging
import time
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QGroupBox, QLabel, QPushButton,
    QTextEdit, QSpinBox, QRadioButton,
    QButtonGroup,
    QScrollArea, QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject

from src.config.system_config import SystemConfig
from src.config.acquisition_config import AcquisitionConfig
from src.gui.trajectory_view import TrajectoryView

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_SIZE_LIMIT_BYTES: int  = 1 * 1024 ** 3   # 1 GB — rotar el fichero .raw
LIVE_REFRESH_MS: int       = 60_000          # ciclo de visualización: cada 60 s
DAQ_POLL_INTERVAL: float   = 60.0             # segundos entre polls del .raw (rotación)
DAQ_CLOSE_TIMEOUT: float   = 10.0             # espera a que el DAQ cierre el .raw tras el Enter

# Vthreshold_LIN: rango válido del spinbox y valor centinela "sin valor".
# El centinela (-1) se muestra como "—" y bloquea START; NUNCA se envía al XML.
VTHRESH_MIN: int           = 0
VTHRESH_MAX: int           = 1000
VTHRESH_MISSING: int       = -1

# Recuadro de aviso (amarillo señal de tráfico, sutil). Distinto de #FFB300,
# que ya identifica el estado CALIBRATION en la barra de estado.
PHYSICS_BOX_STYLE: str = (
    "QGroupBox#physics_group { "
    "border: 1px solid rgba(255, 214, 0, 140); border-radius: 4px; }"
)
VTHRESH_MISSING_STYLE: str = "QSpinBox { border: 1px solid #FF5252; }"


def _results_dir() -> Path:
    """Directorio donde CMSITminiDAQ deja los .raw y .root (ROOT output directory)."""
    try:
        return SystemConfig.get_root_path()
    except Exception:
        return Path("results")


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

    def end_scan(self):
        if self._scan is not None:
            self._scan.end_scan()

    def abort(self):
        if self._scan is not None:
            self._scan.abort()


# ===========================================================================
# Worker — Raw2Root (una terminal separada, una conversión)
# ===========================================================================

class Raw2RootWorker(QObject):
    """
    Convierte un .raw concreto a .root con run_raw2root().
    Corre en su propio QThread para no bloquear ni el DAQ ni la GUI.
    El .raw puede estar cerrado (rotación o STOP) o activo (snapshot).
    """
    log_message = pyqtSignal(str)
    root_ready  = pyqtSignal(str)   # path al .root generado
    finished    = pyqtSignal(bool)

    def __init__(self, xml_path: Path, results_dir: Path, raw_path: Path,
                 tag: str = "RAW2ROOT"):
        super().__init__()
        self._xml_path    = xml_path
        self._results_dir = results_dir
        self._raw_path    = raw_path
        self._tag         = tag

    def run(self):
        success = False
        self._dbg("Converting .raw → .root …")
        try:
            from src.acquisition.scans.physics import PhysicsScan

            _, root_path = PhysicsScan.run_raw2root(
                xml_path=self._xml_path,
                results_dir=self._results_dir,
                raw_path=self._raw_path,
                line_callback=lambda line: self.log_message.emit(f"[{self._tag}] {line}"),
            )
            self._dbg(f"Done → {root_path.name}")
            self.root_ready.emit(str(root_path))
            success = True

        except Exception as e:
            self.log_message.emit(f"[{self._tag} ERROR] {e}")
        finally:
            self.finished.emit(success)

    def _dbg(self, msg: str):
        self.log_message.emit(f"[{self._tag}] {msg}")


# ===========================================================================
# Worker — HitAnalysis (carga del ROOT y reconstrucción fuera del hilo GUI)
# ===========================================================================

class HitAnalysisWorker(QObject):
    """
    Carga un .root y ejecuta HitAnalysis. Solo calcula: el dibujado lo hace
    la GUI con los datos emitidos en analysed.
    """
    log_message = pyqtSignal(str)
    analysed    = pyqtSignal(str, list, list)   # (root_path, plot_coord, active_chips)
    finished    = pyqtSignal()

    # Avisar en el log si algún chip no tiene ningún hit en el fichero
    # (en el modo standalone esto se repite en cada snapshot del poll).
    warn_empty_chips = True

    def __init__(self, root_path: str):
        super().__init__()
        self._root_path = root_path

    def run(self):
        try:
            from src.analysis.analysis_hit import HitAnalysis
            from src.analysis.analysis_base import hits_per_chip, format_chips
            from src.core.exceptions import NAErrorNoHits

            root_manager = SystemConfig.create_root_manager(path=self._root_path)
            root_manager.load(self._root_path)
            if self.warn_empty_chips:
                empty = [c for c, n in hits_per_chip(root_manager.arrays).items() if n == 0]
                if empty:
                    self.log_message.emit(
                        f"[WARN] No hits in {format_chips(empty)} in "
                        f"{Path(self._root_path).name}: check that these chips are powered and enabled."
                    )
            try:
                analysis = HitAnalysis(root_manager)
                plot_coord, active_chips = analysis.plot_coord, analysis.active_chips
            except NAErrorNoHits:
                plot_coord, active_chips = [], []
            self.analysed.emit(self._root_path, list(plot_coord), list(active_chips))
        except Exception as e:
            self.log_message.emit(f"[ANALYSIS ERROR] {Path(self._root_path).name}: {e}")
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
          Si el comando falla, se detiene y deja el reinicio al usuario.
         Cuando el DAQ anuncia el .raw que escribe, emite raw_file_started(raw_path).
      2. Hace polling del .raw cada DAQ_POLL_INTERVAL segundos.
         Emite debug por señal en cada poll.
      3. Cuando el .raw ≥ RAW_SIZE_LIMIT_BYTES:
         a. Para el DAQ limpiamente (scan.end_scan())
         b. Emite raw_cycle_done(raw_path) para que la GUI convierta ese .raw
         c. Vuelve al paso 1 (nuevo ciclo — transparente para el usuario)
      4. STOP (end_scan): espera a que el DAQ cierre el .raw, emite
         raw_cycle_done(raw_path) con el último tramo y sale.
      5. ABORT (abort): mata el DAQ y sale sin emitir nada.
    """

    log_message      = pyqtSignal(str)
    raw_file_started = pyqtSignal(Path)   # .raw que el DAQ está escribiendo ahora
    raw_cycle_done   = pyqtSignal(Path)   # .raw cerrado, listo para convertir
    finished         = pyqtSignal()

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
        self._stop_flag        = False   # STOP: parada limpia, se convierte el último tramo
        self._abort_flag       = False   # ABORT: parada inmediata, no se convierte nada
        self._current_scan     = None
        self._cycle            = 0

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def end_scan(self):
        self._stop_flag = True
        if self._current_scan is not None:
            try:
                self._current_scan.end_scan()
            except Exception:
                pass

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

        while not self._exit_requested():
            self._cycle += 1
            self._dbg(f"━━━ CYCLE {self._cycle} START ━━━")

            raw_path = self._run_one_cycle()

            if raw_path is None:
                if not self._exit_requested():
                    self._dbg("Cycle ended unexpectedly — stopping standalone.")
                break

            self._dbg(f"━━━ CYCLE {self._cycle} END — emitting raw_cycle_done ━━━")
            self.raw_cycle_done.emit(raw_path)

        self._dbg("Standalone acquisition stopped.")
        self.finished.emit()

    def _exit_requested(self) -> bool:
        return self._stop_flag or self._abort_flag

    # ------------------------------------------------------------------
    # Un ciclo de adquisición
    # ------------------------------------------------------------------

    def _run_one_cycle(self) -> Path | None:
        """
        Lanza el DAQ con -t -1 una sola vez y luego espera a que el .raw
        supere el límite, llegue STOP o llegue ABORT.

        Returns el .raw cerrado que hay que convertir (rotación o STOP),
        o None si no hay nada que convertir (ABORT o fallo).
        """
        from src.acquisition.scans.physics import PhysicsScan

        if self._exit_requested():
            return None

        self._dbg("DAQ launch attempt 1/1")

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
            scan._raw_file_callback = self.raw_file_started.emit

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
            self._dbg("DAQ thread running (attempt 1)")

            # Polling del .raw hasta que supere el límite o STOP/ABORT/fin de DAQ
            results_dir  = _results_dir()
            raw_path     = self._poll_raw(daq_done, results_dir)

            if self._abort_flag:
                scan.abort()
                daq_done.wait(timeout=10)
                return None

            if self._stop_flag:
                # end_scan() ya envió el Enter: esperar a que el DAQ cierre el .raw
                if not daq_done.wait(timeout=DAQ_CLOSE_TIMEOUT):
                    self._dbg("DAQ did not close after Enter — sending SIGINT.")
                    scan.abort()
                    daq_done.wait(timeout=10)
                last_raw = self._find_latest_raw(results_dir)
                if last_raw is not None:
                    self._dbg(f"Stopped — last .raw: {last_raw.name}")
                return last_raw

            if raw_path is not None:
                # .raw llegó al límite → detener el DAQ de este ciclo
                size_mb = raw_path.stat().st_size // 1024 ** 2
                self._dbg(f".raw reached {size_mb} MB — rotating (ending scan cleanly)")
                scan.end_scan()
                daq_done.wait(timeout=DAQ_CLOSE_TIMEOUT)

                self._dbg(f"Cycle {self._cycle} complete | raw={raw_path.name}")
                return raw_path

            # Si daq_done se activó sin que raw_path sea válido → DAQ terminó solo
            if daq_done.is_set() and daq_error[0] is not None:
                self._dbg(f"DAQ thread error: {daq_error[0]}")

        except Exception as e:
            self._dbg(f"Exception in cycle attempt 1: {e}")
            self.log_message.emit(f"[STANDALONE ERROR] {e}")

        self._dbg("Standalone acquisition did not start cleanly — stopping without retry.")
        return None

    # ------------------------------------------------------------------
    # Polling del .raw
    # ------------------------------------------------------------------

    def _poll_raw(self, daq_done: threading.Event, results_dir: Path) -> Path | None:
        """
        Polling en bucle hasta que:
          - el .raw ≥ límite           → devuelve Path
          - STOP/ABORT solicitado      → devuelve None
          - DAQ terminó solo           → devuelve None

        Imprime el tamaño actual en cada iteración (debug).
        """
        poll_n = 0
        while not self._exit_requested() and not daq_done.is_set():
            if daq_done.wait(timeout=DAQ_POLL_INTERVAL):
                break

            poll_n += 1

            raw_path = self._find_latest_raw(results_dir)
            if raw_path is None:
                self._dbg(f"[poll #{poll_n}] No .raw found yet in {results_dir}")
                continue

            size_b = raw_path.stat().st_size
            size_mb = size_b / 1024 ** 2
            limit_mb = self._raw_size_limit / 1024 ** 2
            self._dbg(
                f"[poll #{poll_n}] {raw_path.name}  "
                f"{size_mb:.1f} MB / {limit_mb:.0f} MB  "
                f"({100 * size_b / self._raw_size_limit:.1f}%)"
            )

            if size_b >= self._raw_size_limit:
                return raw_path

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

        # Estado — UI (se consulta durante _build_ui, debe existir antes)
        self._running: bool = False

        # Estado — Timed
        self._worker: QObject | None = None
        self._thread: QThread | None = None
        self._last_hit_analysis      = None

        # Estado — Standalone
        self._standalone_worker: StandaloneAcquisitionWorker | None = None
        self._standalone_thread: QThread | None                     = None

        # Procesado (conversión .raw → .root + HitAnalysis), de uno en uno.
        # Los .raw cerrados (rotación / STOP) se encolan y nunca se descartan;
        # el snapshot live solo se lanza si no hay nada en curso ni pendiente.
        self._closed_raws: deque[Path]          = deque()
        self._active_raw: Path | None           = None    # .raw que el DAQ escribe ahora
        self._job_active: bool                  = False
        self._job_closed: bool                  = False   # el job en curso es de un .raw cerrado
        self._r2r_worker: Raw2RootWorker | None = None
        self._r2r_thread: QThread | None        = None
        self._hit_worker: HitAnalysisWorker | None = None
        self._hit_thread: QThread | None        = None

        # Panel de trayectorias: fichero mostrado y cuántos de sus tracks ya se dibujaron
        self._shown_root: str | None = None
        self._shown_tracks: int      = 0

        # Contador de sesión = tracks de ficheros cerrados + tracks del fichero abierto
        self._closed_tracks: int = 0
        self._open_tracks: int   = 0

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
        left_splitter.setSizes([710, 90])
        left_splitter.setStretchFactor(0, 1)   # el panel de control absorbe el espacio libre al redimensionar
        left_splitter.setStretchFactor(1, 0)   # el log NO crece solo al redimensionar la ventana
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

        title = QLabel("ACQUISITION CONFIG")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # --- Modo + Scan time (matriz 2x2) ---
        mode_group = QGroupBox("ACQUISITION MODE")
        mode_grid  = QGridLayout(mode_group)
        mode_grid.setHorizontalSpacing(16)
        mode_grid.setVerticalSpacing(8)

        self._radio_timed = QRadioButton("Timed")
        self._radio_cont  = QRadioButton("StandAlone")
        self._radio_timed.setChecked(True)
        self._mode_group = QButtonGroup()
        self._mode_group.addButton(self._radio_timed, 0)
        self._mode_group.addButton(self._radio_cont,  1)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        # Columna 0: radios (Fila 0 = Timed, Fila 1 = Standalone)
        mode_grid.addWidget(self._radio_timed, 0, 0)
        mode_grid.addWidget(self._radio_cont,  1, 0)

        # Columna 1, fila 0: Scan time (label + spinbox en horizontal)
        scan_time_row = QHBoxLayout()
        scan_time_row.setSpacing(6)
        self._lbl_scan_time = QLabel("Scan time (s):")
        scan_time_row.addWidget(self._lbl_scan_time)
        self._scan_time = QSpinBox()
        self._scan_time.setRange(1, 3600)
        self._scan_time.setValue(30)
        self._scan_time.setMaximumWidth(80)
        scan_time_row.addWidget(self._scan_time)
        scan_time_row.addStretch()
        mode_grid.addLayout(scan_time_row, 0, 1)
        # Fila 1, columna 1: vacío (deliberado)

        mode_grid.setColumnStretch(0, 0)
        mode_grid.setColumnStretch(1, 1)

        layout.addWidget(mode_group)

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

        abort_row = QHBoxLayout()

        self._btn_abort = QPushButton("ABORT")
        self._btn_abort.setStyleSheet(
            "QPushButton { color: #FF5252; border-color: #FF5252; }"
            "QPushButton:hover { background: #FF5252; color: #1A1D23; }"
        )
        self._btn_abort.setEnabled(False)
        self._btn_abort.clicked.connect(self._abort)
        abort_row.addWidget(self._btn_abort)

        self._btn_stop_acq = QPushButton("STOP ACQ")
        self._btn_stop_acq.setStyleSheet(
            "QPushButton { color: #69F0AE; border-color: #69F0AE; }"
            "QPushButton:hover { background: #69F0AE; color: #1A1D23; }"
        )
        self._btn_stop_acq.setEnabled(False)
        self._btn_stop_acq.clicked.connect(self._stop_acq)
        abort_row.addWidget(self._btn_stop_acq)

        layout.addLayout(abort_row)

        layout.addWidget(self._build_physics_params_group(), 1)
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

        self._trajectory_view = TrajectoryView()
        self._trajectory_view.hide()
        layout.addWidget(self._trajectory_view)

        return panel

    # ==================================================================
    # Modo changed
    # ==================================================================

    def _on_mode_changed(self):
        timed = self._mode_group.checkedId() == 0
        self._scan_time.setEnabled(timed)
        self._lbl_scan_time.setEnabled(timed)
        if timed:
            self._standalone_status.hide()   # nunca visible en Timed, ni con texto residual
        # En Standalone NO se muestra aquí: permanece oculto hasta START
        # (lo muestra _start_standalone(), línea ~781-782)
        self._btn_stop_acq.setEnabled(False)   # STOP ACQ no aplica en modo Timed
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
        if self._job_active or self._closed_raws:
            self._log_write("[WARN] Previous session still converting .raw files — wait for it to finish.")
            return

        self._log_write(f"[DEBUG] ph2_acf_dir={SystemConfig.get_ph2_acf_dir()}")
        self._log_write(f"[DEBUG] txt_base_dir={SystemConfig.get_txt_base_dir()}")

        chips = SystemConfig.get_active_hw_chips()
        if not chips:
            self._log_write("[ERROR] No active chips. Configure chips in the Config tab.")
            return

        # El XML manda salvo en los chips cuyo valor el usuario ha editado a mano.
        self._sync_vthresh_from_xml()
        missing = self._missing_vthresh_chips()
        if missing:
            self._log_write(
                f"[ERROR] Vthreshold_LIN not available for {missing}. "
                "Check the XML selected in Config or set the value manually."
            )
            self._update_start_enabled()
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
        self._last_hit_analysis = None
        self._shown_root        = None
        self._shown_tracks      = 0
        self._closed_tracks     = 0
        self._open_tracks       = 0
        self._active_raw        = None

        self._standalone_worker = StandaloneAcquisitionWorker(
            chips=chips,
            triggers=self._spin_triggers.value(),
            vthresh_per_chip=vthresh,
        )
        self._standalone_thread = QThread()
        self._standalone_worker.moveToThread(self._standalone_thread)
        self._standalone_thread.started.connect(self._standalone_worker.run)
        self._standalone_worker.log_message.connect(self._log_write)
        self._standalone_worker.raw_file_started.connect(self._on_raw_file_started)
        self._standalone_worker.raw_cycle_done.connect(self._on_raw_cycle_done)
        self._standalone_worker.finished.connect(self._on_standalone_finished)

        self._set_running_ui(True)
        self._update_standalone_status()
        self._standalone_status.show()

        self._refresh_timer.start()
        self._standalone_thread.start()

    def _on_raw_file_started(self, raw_path: Path):
        """El DAQ ha anunciado el .raw que está escribiendo: será el del snapshot."""
        self._active_raw = raw_path
        self._log_write(f"[STANDALONE] Active .raw: {raw_path.name}")

    def _on_raw_cycle_done(self, raw_path: Path):
        """Un .raw se ha cerrado (rotación o STOP): se encola para convertirlo."""
        if self._active_raw == raw_path:
            self._active_raw = None
        self._log_write(f"[STANDALONE] Closed .raw queued for conversion: {raw_path.name}")
        self._closed_raws.append(raw_path)
        self._run_next_job()

    def _trigger_live_snapshot(self):
        """
        Llamado por el QTimer cada LIVE_REFRESH_MS.
        Convierte el .raw activo para ver los tracks acumulados sin esperar a 1 GB.
        Se salta si hay otro procesado en curso o pendiente.
        """
        if not (self._standalone_thread and self._standalone_thread.isRunning()):
            return

        if self._job_active or self._closed_raws:
            self._log_write("[LIVE] Previous conversion still running — skipping tick.")
            return

        if self._active_raw is None:
            self._log_write("[LIVE] Active .raw not announced by the DAQ yet — skipping tick.")
            return

        self._log_write(f"[LIVE] Snapshot tick — converting {self._active_raw.name} …")
        self._start_job(self._active_raw, closed=False)

    # ------------------------------------------------------------------
    # Procesado: .raw → .root → HitAnalysis (un job cada vez)
    # ------------------------------------------------------------------

    def _run_next_job(self):
        if self._job_active or not self._closed_raws:
            return
        self._start_job(self._closed_raws.popleft(), closed=True)

    def _start_job(self, raw_path: Path, closed: bool):
        """closed=True → .raw cerrado (rotación/STOP); False → snapshot del .raw activo."""
        try:
            xml_path = SystemConfig.get_xml_path()
        except Exception as e:
            self._log_write(f"[STANDALONE] Cannot start conversion: {e}")
            return

        self._job_active = True
        self._job_closed = closed

        worker = Raw2RootWorker(
            xml_path=xml_path,
            results_dir=_results_dir(),
            raw_path=raw_path,
            tag="RAW2ROOT" if self._job_closed else "LIVE R2R",
        )
        self._retire_thread(self._r2r_thread)
        self._r2r_worker = worker
        self._r2r_thread = QThread()
        worker.moveToThread(self._r2r_thread)
        self._r2r_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.root_ready.connect(self._on_job_root_ready)
        worker.finished.connect(self._on_job_converted)
        worker.finished.connect(self._r2r_thread.quit)
        self._r2r_thread.start()

    @staticmethod
    def _retire_thread(thread: QThread | None):
        """Cierra el hilo del job anterior antes de soltar su referencia."""
        if thread is not None:
            thread.quit()
            thread.wait()

    def _on_job_converted(self, success: bool):
        # Si la conversión falló no habrá análisis: el job termina aquí
        if not success:
            self._end_job()

    def _on_job_root_ready(self, root_path: str):
        worker = HitAnalysisWorker(root_path)
        self._retire_thread(self._hit_thread)
        self._hit_worker = worker
        self._hit_thread = QThread()
        worker.moveToThread(self._hit_thread)
        self._hit_thread.started.connect(worker.run)
        worker.log_message.connect(self._log_write)
        worker.analysed.connect(self._on_job_analysed)
        worker.finished.connect(self._end_job)
        worker.finished.connect(self._hit_thread.quit)
        self._hit_thread.start()

    def _on_job_analysed(self, root_path: str, plot_coord: list, active_chips: list):
        n = len(plot_coord)
        self._log_write(f"[LIVE] {Path(root_path).name}: {n} tracks")

        self._show_file_tracks(root_path, plot_coord, active_chips)

        if self._job_closed:
            self._closed_tracks += n
            self._open_tracks    = 0
        else:
            self._open_tracks = n
        self._update_standalone_status()

    def _end_job(self):
        self._job_active = False
        self._run_next_job()
        if not self._job_active and not self._is_standalone_running():
            self._log_write(
                f"[STANDALONE] Session ended — {self._session_tracks()} total tracks."
            )

    # ------------------------------------------------------------------
    # Panel de trayectorias y contador
    # ------------------------------------------------------------------

    def _show_file_tracks(self, root_path: str, plot_coord: list, active_chips: list):
        """
        Muestra todos los tracks del fichero analizado. Si es el mismo fichero
        que ya está en el panel, solo se animan los que no se habían dibujado.
        """
        if root_path != self._shown_root:
            self._shown_root   = root_path
            self._shown_tracks = 0
            self._trajectory_view.reset(active_chips)
            self._show_trajectory_view()

        new_tracks = plot_coord[self._shown_tracks:]
        if new_tracks:
            self._trajectory_view.animate(new_tracks)
            self._btn_save_traj.setEnabled(True)
        self._shown_tracks = max(self._shown_tracks, len(plot_coord))

    def _show_trajectory_view(self):
        self._traj_placeholder.hide()
        self._trajectory_view.show()

    def _session_tracks(self) -> int:
        return self._closed_tracks + self._open_tracks

    def _update_standalone_status(self):
        state = "Acquiring…" if self._running else "Stopped"
        self._standalone_status.setText(
            f"⬤  {state}  |  Tracks this session: {self._session_tracks()}"
        )

    def _is_standalone_running(self) -> bool:
        return bool(self._standalone_thread and self._standalone_thread.isRunning())

    def _on_standalone_finished(self):
        self._refresh_timer.stop()
        self._set_running_ui(False)

        if self._standalone_thread:
            self._standalone_thread.quit()
            self._standalone_thread.wait()

        self._update_standalone_status()
        # Con tracks ya dibujados, Save Plot sigue disponible tras parar
        self._btn_save_traj.setEnabled(self._shown_tracks > 0)

        if self._job_active or self._closed_raws:
            self._log_write("[STANDALONE] Acquisition stopped — finishing pending conversions …")
        else:
            self._log_write(
                f"[STANDALONE] Session ended — {self._session_tracks()} total tracks."
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
        self._btn_stop_acq.setEnabled(False)
        self._log_write("[ABORTED] Abort requested…")

    def _stop_acq(self):
        if self._worker:
            self._worker.end_scan()
        if self._standalone_worker:
            self._standalone_worker.end_scan()
        self._btn_abort.setEnabled(False)
        self._btn_stop_acq.setEnabled(False)
        self._log_write("[STOP] Controlled stop requested…")

    # ==================================================================
    # UI helpers
    # ==================================================================

    def _set_running_ui(self, running: bool):
        is_standalone = self._mode_group.checkedId() == 1
        self._running = running
        self._update_start_enabled()
        self._btn_abort.setEnabled(running)
        self._btn_stop_acq.setEnabled(running and is_standalone)
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
        # Recuadro amarillo sutil: el selector por objectName evita que el
        # estilo se propague a los widgets hijos.
        group.setObjectName("physics_group")
        group.setStyleSheet(PHYSICS_BOX_STYLE)
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

        thresh_label = QLabel("AFE Linear Threshold")
        thresh_label.setStyleSheet(
            "font-size: 11px; color: #4FA3B0; letter-spacing: 1px; margin-top: 4px;"
        )
        layout.addWidget(thresh_label)

        self._vthresh_scroll = QScrollArea()
        self._vthresh_scroll.setWidgetResizable(True)
        self._vthresh_scroll.setFrameShape(self._vthresh_scroll.NoFrame)
        layout.addWidget(self._vthresh_scroll)

        self._vthresh_spinboxes: dict[tuple[int, int], QSpinBox] = {}
        # Chips cuyo threshold ha sido editado a mano por el usuario: el refresco
        # previo al START no los pisa con el valor del XML.
        self._vthresh_manual: set[tuple[int, int]] = set()
        self._refresh_vthresh_spinboxes()
        return group

    # ------------------------------------------------------------------
    # Vthreshold_LIN: origen único = XML seleccionado en Config
    # ------------------------------------------------------------------

    def _read_xml_thresholds(
        self, chips: list[tuple[int, int]]
    ) -> dict[tuple[int, int], int]:
        """Lee Vthreshold_LIN del XML. Solo devuelve los chips que se pudieron leer."""
        try:
            return AcquisitionConfig.get_chip_thresholds(chips)
        except Exception as e:
            self.logger.warning("Cannot read Vthreshold_LIN from XML: %s", e)
            return {}

    def _refresh_vthresh_spinboxes(self) -> None:
        """Reconstruye los spinboxes y los rellena desde el XML.

        Se llama al aplicar la configuración: descarta cualquier edición manual
        previa (decisión acordada: el XML es la fuente de verdad).
        """
        from src.chip.detector_geometry import DETECTOR_LAYOUT

        self._vthresh_spinboxes.clear()
        self._vthresh_manual.clear()

        inner        = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        try:
            active_set = set(SystemConfig.get_active_hw_chips())
            xml_values = self._read_xml_thresholds(sorted(active_set))
            for layer in DETECTOR_LAYOUT.values():
                hybrid = layer["hybrid"]
                offset = layer["rd53_offset"]
                for chip_local in layer["chips"]:
                    rd53_hw = chip_local + offset
                    key = (hybrid, rd53_hw)
                    if key not in active_set:
                        continue
                    row = QHBoxLayout()
                    lbl = QLabel(f"  H{hybrid} . Chip {rd53_hw}  ({layer['label']}):")
                    lbl.setStyleSheet("font-size: 11px;")
                    lbl.setMinimumWidth(200)
                    row.addWidget(lbl)
                    spin = QSpinBox()
                    # El mínimo es el centinela: se muestra como "—" (sin valor).
                    spin.setRange(VTHRESH_MISSING, VTHRESH_MAX)
                    spin.setSpecialValueText("—")
                    spin.setMaximumWidth(80)
                    self._set_vthresh_value(spin, key, xml_values.get(key))
                    spin.valueChanged.connect(
                        lambda _v, k=key: self._on_vthresh_edited(k)
                    )
                    row.addWidget(spin)
                    row.addStretch()
                    inner_layout.addLayout(row)
                    self._vthresh_spinboxes[key] = spin
        except Exception:
            inner_layout.addWidget(QLabel("  Configure chips first."))

        if not self._vthresh_spinboxes:
            inner_layout.addWidget(QLabel("  No active chips — configure in Config tab."))

        self._vthresh_scroll.setWidget(inner)
        self._update_start_enabled()

    def _sync_vthresh_from_xml(self) -> None:
        """Relee el XML justo antes de lanzar (p. ej. si una calibración lo cambió).

        Solo actualiza los chips que el usuario NO ha editado a mano.
        """
        xml_values = self._read_xml_thresholds(list(self._vthresh_spinboxes))
        for key, spin in self._vthresh_spinboxes.items():
            if key in self._vthresh_manual:
                continue
            self._set_vthresh_value(spin, key, xml_values.get(key))
        self._update_start_enabled()

    def _set_vthresh_value(self, spin: QSpinBox, key: tuple[int, int], value: int | None) -> None:
        """Asigna un valor leído del XML sin marcarlo como edición manual."""
        if value is not None and not (VTHRESH_MIN <= value <= VTHRESH_MAX):
            self.logger.warning(
                "Vthreshold_LIN=%s out of range for chip %s — treated as missing.", value, key
            )
            value = None
        spin.blockSignals(True)
        spin.setValue(VTHRESH_MISSING if value is None else value)
        spin.blockSignals(False)
        self._style_vthresh_spin(spin)

    def _style_vthresh_spin(self, spin: QSpinBox) -> None:
        if spin.value() == VTHRESH_MISSING:
            spin.setStyleSheet(VTHRESH_MISSING_STYLE)
            spin.setToolTip("Vthreshold_LIN not found in the XML — set it manually.")
        else:
            spin.setStyleSheet("")
            spin.setToolTip(
                "Loaded from the XML selected in Config. If you edit it, the new "
                "value is written to the XML when the acquisition starts."
            )

    def _on_vthresh_edited(self, key: tuple[int, int]) -> None:
        self._vthresh_manual.add(key)
        spin = self._vthresh_spinboxes.get(key)
        if spin is not None:
            self._style_vthresh_spin(spin)
        self._update_start_enabled()

    def _missing_vthresh_chips(self) -> list[tuple[int, int]]:
        return [k for k, s in self._vthresh_spinboxes.items() if s.value() == VTHRESH_MISSING]

    def _update_start_enabled(self) -> None:
        """START solo está activo si no hay adquisición en curso y todos los
        chips activos tienen un Vthreshold_LIN válido."""
        missing = self._missing_vthresh_chips()
        self._btn_start.setEnabled(not self._running and not missing)
        self._btn_start.setToolTip(
            f"Vthreshold_LIN missing for: {missing}" if missing else ""
        )

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
        plot_coord = self._last_hit_analysis.plot_coord
        self._shown_root   = None
        self._shown_tracks = len(plot_coord)
        self._trajectory_view.reset(self._last_hit_analysis.active_chips)
        self._show_trajectory_view()
        self._trajectory_view.animate(plot_coord)
        self._btn_save_traj.setEnabled(True)
        self._log_write(f"[INFO] Showing {len(plot_coord)} trajectories.")

    def _save_trajectories(self):
        try:
            try:
                output_dir = SystemConfig.get_root_path().parent / "plots"
            except Exception:
                output_dir = None
            path = self._trajectory_view.save(output_dir)
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