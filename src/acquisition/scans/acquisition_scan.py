from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import re
import shlex
from src.remote.terminal import Terminal
from src.acquisition.maps import AcquisitionMap
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.config.system_config import SystemConfig
import logging
logger = logging.getLogger(__name__)

# Línea con la que CMSITminiDAQ anuncia el .raw que está escribiendo,
# p. ej. "Saving binary data into: Results/Run000298_Physics_Board000.raw"
RAW_FILE_PATTERN = re.compile(r"Saving binary data into:\s*(\S+\.raw)")
# Códigos de color ANSI que Ph2_ACF mete en sus logs (p. ej. "\033[1m\033[33m")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


class AcquisitionScan(ABC):
    def __init__(self, chips: list[tuple], timeout: int = 60, scan_time: int = 60):
        """
        Args:
            chips: lista de (hybrid_id, rd53_id) a habilitar.
            timeout: timeout global del proceso DAQ.
            scan_time: duración del scan en segundos (-1 sin límite).
        """
        self.chips = chips
        self.timeout = timeout
        self.scan_time = scan_time
        self.last_scan_end_pattern = None
        self.raw_path: Path | None = None   # .raw que escribe el DAQ (leído de su salida)

        sys_config = SystemConfig()
        self.ph2_acf_dir = str(sys_config.get_ph2_acf_dir())
        self.xml = sys_config.create_xml_manager()
        self.txt_dir = str(sys_config.get_txt_base_dir())
        from src.core import num_manager
        num_manager.configure(Path(self.txt_dir) / "RunNumber.txt")


    @abstractmethod
    def get_map(self):
        pass

    def _apply_setting(self, setting: ChipSettings | CalibrationSettings | FastCmdReg, value: Value,
                       hybrid_id: int | None = None, rd53_id: int | None = None):
        if isinstance(setting, CalibrationSettings):
            self.xml.set_calibration_setting(setting, value)
        elif isinstance(setting, ChipSettings):
            if hybrid_id is None or rd53_id is None:
                raise ValueError("ChipSettings require hybrid_id and rd53_id")
            self.xml.set_chip_setting(hybrid_id, rd53_id, setting, value)
        elif isinstance(setting, FastCmdReg):
            self.xml.set_register_value(setting, value)
        else:
            raise ValueError(f"Unsupported setting type: {type(setting)}")

    def _acq_setup_xml(self):
        acp_map = AcquisitionMap()
        self._apply_map(acp_map.to_dict())
        
        for hybrid_id, rd53_id in self.chips:
            self.xml.set_chip_enable(hybrid_id, rd53_id, True)
        self.xml.save()

    
    def _setup_xml(self):
        self._acq_setup_xml()
        self._apply_map(self.get_map().to_dict())
        self.xml.save()

    def _apply_map(self, settings: dict, hybrid_id: int | None = None, rd53_id: int | None = None):
        """Aplica un diccionario de settings al XML, manejando los tres tipos."""
        for key, value in settings.items():
            try:
                if isinstance(key, CalibrationSettings):
                    self._apply_setting(key, value)
                elif isinstance(key, FastCmdReg):
                    self._apply_setting(key, value)
                elif isinstance(key, ChipSettings):
                    if hybrid_id is not None and rd53_id is not None:
                        self._apply_setting(key, value, hybrid_id, rd53_id)
                    else:
                        # ChipSettings sin chip especificado → aplicar a todos los chips activos
                        for h, r in self.chips:
                            self._apply_setting(key, value, h, r)
            except Exception as e:
                self.xml.logger.warning(
                    f"Failed to set '{key}' to '{value}': {str(e)}"
                )
                
    def run(self):
        self._setup_xml()
        self.last_scan_end_pattern = None
        self.raw_path = None
        self._terminal = None

        line_cb = getattr(self, '_line_callback', None)
        raw_file_cb = getattr(self, '_raw_file_callback', None)

        def _on_line(line: str):
            if self.raw_path is None:
                # Sin quitar los colores, la ruta capturada arrastra el "\033[...m"
                match = RAW_FILE_PATTERN.search(ANSI_ESCAPE_PATTERN.sub("", line))
                if match:
                    # La ruta que imprime el DAQ es relativa a su cwd (txt_dir)
                    self.raw_path = Path(self.txt_dir) / match.group(1)
                    if raw_file_cb:
                        raw_file_cb(self.raw_path)
            if line_cb:
                line_cb(line)

        cmd = f"CMSITminiDAQ -f {self.xml.get_path()} -c physics -t {self.scan_time}"

        with Terminal(timeout=self.timeout, line_callback=_on_line) as term:
            self._terminal = term
            output, matched_pattern = term.run_scan(cmd, cwd=self.txt_dir)
            self.last_scan_end_pattern = matched_pattern

        return output
    
    @staticmethod
    def run_raw2root(xml_path, results_dir, cwd=None, timeout: int = 180,
                     line_callback=None, raw_path=None) -> tuple[str, Path]:
        from src.core import num_manager

        cwd = Path(cwd) if cwd is not None else SystemConfig.get_txt_base_dir()

        if raw_path is None:
            run_str = str(num_manager.get() - 1).zfill(6)
            binary_path = Path(results_dir) / f"Run{run_str}_Physics_Board000.raw"
        else:
            binary_path = Path(raw_path)

        # CMSITminiDAQ no avisa si el .raw no existe: lee basura y acaba en std::bad_alloc
        if not binary_path.is_file():
            raise FileNotFoundError(f"raw2root: .raw not found: {binary_path}")

        # El .raw se pasa relativo a txt_base_dir (p. ej. Results/RunXXX.raw)
        try:
            raw_arg = str(binary_path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            logger.warning("%s is outside %s; using absolute path.", binary_path, cwd)
            raw_arg = str(binary_path.resolve())

        cmd = f"CMSITminiDAQ -f {shlex.quote(str(xml_path))} -b {shlex.quote(raw_arg)}"
        logger.info("raw2root: %s  (cwd=%s)", cmd, cwd)

        with Terminal(timeout=timeout, line_callback=line_callback) as term:
            output, matched = term.run_scan(cmd, cwd=str(cwd))

        if matched is None:
            logger.error("raw2root did not finish cleanly for %s (no end pattern found).", binary_path.name)
            raise RuntimeError(f"raw2root failed for {binary_path.name}: no end pattern found")

        root_path = binary_path.with_suffix(".root")
        if not root_path.exists():
            logger.error("raw2root finished but %s was not created.", root_path.name)
            raise RuntimeError(f"raw2root finished but {root_path.name} was not created")

        logger.info("raw2root finished: %s", root_path.name)
        return output, root_path

    @property
    def scan_ended(self) -> bool:
        """True si el scan terminó con uno de los patrones de fin esperados."""
        return self.last_scan_end_pattern is not None

    def end_scan(self):
        """
        Para el DAQ de forma limpia enviando Enter al stdin del proceso.

        CMSITminiDAQ en modo -t -1 cierra el .raw correctamente al recibir
        un Enter, lo que garantiza que el fichero queda íntegro para raw2root.
        Si send_enter() falla (proceso ya muerto, stdin no disponible) cae
        a SIGINT como último recurso.
        """
        if hasattr(self, '_terminal') and self._terminal:
            sent = self._terminal.send_enter()
            if not sent:
                self._terminal.kill()

    def abort(self):
        if hasattr(self, '_terminal') and self._terminal:
            self._terminal.kill()