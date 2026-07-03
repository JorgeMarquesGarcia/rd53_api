from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from src.remote.terminal import Terminal
from src.acquisition.maps import AcquisitionMap
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.config.system_config import SystemConfig


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
        self._terminal = None

        line_cb = getattr(self, '_line_callback', None)

        cmd = f"CMSITminiDAQ -f {self.xml.get_path()} -c physics -t {self.scan_time}"

        with Terminal(timeout=self.timeout, line_callback=line_cb) as term:
            self._terminal = term
            output, matched_pattern = term.run_scan(cmd, cwd=self.txt_dir)
            self.last_scan_end_pattern = matched_pattern

        return output
    
    def run_raw2root(self, xml_path: str | Path, results_dir: str | Path,
                      cwd: str | Path | None = None, timeout: int = 60,
                      line_callback=None) -> tuple[str, Path]:
        """
        Ejecuta el volcado binario (-b) del run actual, usando el run number
        de num_manager. No depende de una instancia de Scan (no usa chips ni
        scan_time), así que puede llamarse desde timed, continuous o donde
        haga falta.
        """
        from src.core import num_manager
        from src.remote.terminal import Terminal
        from src.config.system_config import SystemConfig

        if cwd is None:
            cwd = SystemConfig.get_txt_base_dir()

        run_str = str(num_manager.get() - 1).zfill(6)
        binary_path = Path(results_dir) / f"Run{run_str}_Physics_Board000.raw"
        cmd = f"CMSITminiDAQ -f {xml_path} -b {binary_path}"

        with Terminal(timeout=timeout, line_callback=line_callback) as term:
            output, matched_pattern = term.run_scan(cmd, cwd=cwd)

        return output, binary_path

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