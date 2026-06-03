from __future__ import annotations
from abc import ABC, abstractmethod
from src.remote.terminal import Terminal
from src.calibration.maps import CalibrationMap
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.config.system_config import SystemConfig


class CalibrationScan(ABC):
    def __init__(self, hybrid_id: int = 0, rd53_id: int = 0, timeout: int = 600):
        self.hybrid_id = hybrid_id
        self.rd53_id = rd53_id
        self.timeout = timeout
        self.last_scan_end_pattern = None

        sys_config = SystemConfig()
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
            self.xml.set_chip_setting(self.hybrid_id, self.rd53_id, setting, value)
        elif isinstance(setting, FastCmdReg):
            self.xml.set_register_value(setting, value)
        else:
            raise ValueError(f"Unsupported setting type: {type(setting)}")

    def _cal_setup_xml(self):
        cal_map = CalibrationMap()
        for key, value in cal_map.to_dict().items():
            try:
                self._apply_setting(key, value)
            except Exception as e:
                self.xml.logger.warning(f"Failed to set calibration setting '{key}' to '{value}': {str(e)}")

        self.xml.set_chip_enable(self.hybrid_id, self.rd53_id, True)
        self.xml.save()

    def _setup_xml(self):
        self._cal_setup_xml()
        for key, value in self.get_map().to_dict().items():
            try:
                self._apply_setting(key, value)
            except Exception as e:
                self.xml.logger.warning(f"Failed to set chip setting '{key}' to '{value}': {str(e)}")
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