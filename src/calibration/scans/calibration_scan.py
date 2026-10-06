from __future__ import annotations
from abc import ABC, abstractmethod
from src.remote.terminal import Terminal
from src.calibration.maps import CalibrationMap
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.config.system_config import SystemConfig


class CalibrationScan(ABC):
    def __init__(self, chips: list[tuple[int, int]] | None = None, timeout: int = 600):
        """
        Args:
            chips: lista de (hybrid_id, rd53_id) a calibrar. Si es None se usan
                   los chips activos de SystemConfig (los marcados en APPLY CONFIG).
            timeout: timeout global del proceso DAQ.
        """
        sys_config = SystemConfig()
        self.chips = list(chips) if chips is not None else sys_config.get_active_hw_chips()
        if not self.chips:
            raise ValueError("No active chips configured for calibration.")
        self.timeout = timeout
        self.last_scan_end_pattern = None

        self.ph2_acf_dir = str(sys_config.get_ph2_acf_dir())
        self.xml = sys_config.create_xml_manager()
        self.txt_dir = str(sys_config.get_txt_base_dir())

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
                self.xml.logger.warning(f"Failed to set '{key}' to '{value}': {str(e)}")

    def _cal_setup_xml(self):
        self._apply_map(CalibrationMap().to_dict())

        for hybrid_id, rd53_id in self.chips:
            self.xml.set_chip_enable(hybrid_id, rd53_id, True)
        self.xml.save()

    def _setup_xml(self):
        self._cal_setup_xml()
        self._apply_map(self.get_map().to_dict())
        self.xml.save()

    def run(self):
        self._setup_xml()
        self.last_scan_end_pattern = None
        self._terminal = None

        line_cb = getattr(self, '_line_callback', None)

        cmd = f"CMSITminiDAQ -f {self.xml.get_path()} -c {self.calibration_name}"

        with Terminal(timeout=self.timeout, line_callback=line_cb) as term:
            self._terminal = term
            output, matched_pattern = term.run_scan(cmd, cwd=self.txt_dir)
            self.last_scan_end_pattern = matched_pattern

        return output

    @property
    def scan_ended(self) -> bool:
        """True si el scan terminó con uno de los patrones de fin esperados."""
        return self.last_scan_end_pattern is not None

    def abort(self):
        if hasattr(self, '_terminal') and self._terminal:
            self._terminal.kill()