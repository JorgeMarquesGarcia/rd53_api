from __future__ import annotations
from abc import ABC, abstractmethod
from rd53_api.remote.terminal import Terminal
from rd53_api.acquisition.maps import AcquisitionMap
from rd53_api.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from rd53_api.config.system_config import SystemConfig


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
        for key, value in acp_map.to_dict().items():
            try:
                if isinstance(key, CalibrationSettings):
                    self._apply_setting(key, value)
            except Exception as e:
                self.xml.logger.warning(f"Failed to set acquisition setting '{key}' to '{value}': {str(e)}")

        for hybrid_id, rd53_id in self.chips:
            self.xml.set_chip_enable(hybrid_id, rd53_id, True)
        self.xml.save()

    def _setup_xml(self):
        self._acq_setup_xml()

        acquisition_map = self.get_map()

        for key, value in acquisition_map.to_dict().items():
            try:
                if isinstance(key, CalibrationSettings):
                    self._apply_setting(key, value)
            except Exception as e:
                self.xml.logger.warning(f"Failed to set acquisition setting '{key}' to '{value}': {str(e)}")

        for hybrid_id, rd53_id in self.chips:
            for key, value in acquisition_map.to_dict().items():
                try:
                    if isinstance(key, ChipSettings):
                        self._apply_setting(key, value, hybrid_id, rd53_id)
                except Exception as e:
                    self.xml.logger.warning(
                        f"Failed to set chip setting '{key}' to '{value}' "
                        f"for chip (hybrid={hybrid_id}, rd53={rd53_id}): {str(e)}"
                    )

        self.xml.save()

    def run(self):
        self._setup_xml()
        self.last_scan_end_pattern = None
        self._terminal = None

        line_cb = getattr(self, '_line_callback', None)

        cmd = f"CMSITminiDAQ -f {self.xml.get_path()} -c physics -t {self.scan_time}"

        with Terminal(timeout=self.timeout, line_callback=line_cb) as term:
            self._terminal = term
            output, matched_pattern = term.run_scan(cmd, cwd=self.ph2_acf_dir)
            self.last_scan_end_pattern = matched_pattern

        return output

    @property
    def scan_ended(self) -> bool:
        """True si el scan terminó con uno de los patrones de fin esperados."""
        return self.last_scan_end_pattern is not None

    def abort(self):
        if hasattr(self, '_terminal') and self._terminal:
            self._terminal.kill()