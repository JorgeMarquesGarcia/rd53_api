from __future__ import annotations
import logging
import shlex
from abc import ABC, abstractmethod
from typing import Callable

from src.remote.terminal import Terminal
from src.calibration.maps import CalibrationMap
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.config.system_config import SystemConfig

logger = logging.getLogger(__name__)


class CalibrationScan(ABC):
    def __init__(self, chips: list[tuple[int, int]] | None = None, timeout: int = 600):
        """
        Args:
            chips: lista de (hybrid_id, rd53_id) a calibrar. Si es None se usan
                   los chips activos de SystemConfig (los marcados en APPLY CONFIG).
            timeout: espera máxima (s) a que el DAQ termine tras cerrar su salida
                     (ver Terminal.run_scan).
        """
        self.chips = list(chips) if chips is not None else SystemConfig.get_active_hw_chips()
        if not self.chips:
            raise ValueError("No active chips configured for calibration.")
        self.timeout = timeout
        self.last_scan_end_pattern = None
        # Mensajes para el log de la GUI sobre lo que el scan ha cambiado (p. ej. el XML)
        self.report: list[str] = []

        self.ph2_acf_dir = str(SystemConfig.get_ph2_acf_dir())
        self.xml = SystemConfig.create_xml_manager()
        self.txt_dir = str(SystemConfig.get_txt_base_dir())

        # Callback opcional con cada línea del DAQ (lo asigna la GUI)
        self._line_callback: Callable[[str], None] | None = None
        self._terminal: Terminal | None = None

    @property
    @abstractmethod
    def calibration_name(self) -> str:
        pass

    @abstractmethod
    def get_map(self):
        pass

    def _apply_setting(self, setting: ChipSettings | CalibrationSettings | FastCmdReg, value: Value):
        if isinstance(setting, CalibrationSettings):
            self.xml.set_calibration_setting(setting, value)
        elif isinstance(setting, ChipSettings):
            # ChipSettings → aplicar a todos los chips a calibrar
            for hybrid_id, rd53_id in self.chips:
                self.xml.set_chip_setting(hybrid_id, rd53_id, setting, value)
        elif isinstance(setting, FastCmdReg):
            self.xml.set_register_value(setting, value)
        else:
            raise ValueError(f"Unsupported setting type: {type(setting)}")

    def _apply_map(self, settings: dict):
        for key, value in settings.items():
            try:
                self._apply_setting(key, value)
            except Exception as e:
                self.xml.logger.warning("Failed to set '%s' to '%s': %s", key, value, e)

    def _cal_setup_xml(self):
        self._apply_map(CalibrationMap().to_dict())
        for hybrid_id, rd53_id in self.chips:
            self.xml.set_chip_enable(hybrid_id, rd53_id, True)

    def _setup_xml(self):
        # Todos los cambios del scan en una única escritura del XML
        with self.xml.batch():
            self._cal_setup_xml()
            self._apply_map(self.get_map().to_dict())

    def _build_command(self) -> str:
        return (f"CMSITminiDAQ -f {shlex.quote(str(self.xml.get_path()))} "
                f"-c {self.calibration_name}")

    def run(self):
        self._setup_xml()
        self.last_scan_end_pattern = None
        self._terminal = None
        self.report = []

        cmd = self._build_command()
        logger.info("Calibration '%s': %s (cwd=%s)", self.calibration_name, cmd, self.txt_dir)

        with Terminal(timeout=self.timeout, line_callback=self._line_callback) as term:
            self._terminal = term
            output, matched_pattern = term.run_scan(cmd, cwd=self.txt_dir)
            self.last_scan_end_pattern = matched_pattern

        return output

    @property
    def scan_ended(self) -> bool:
        """True si el scan terminó con uno de los patrones de fin esperados."""
        return self.last_scan_end_pattern is not None

    def abort(self):
        if self._terminal is not None:
            self._terminal.kill()
