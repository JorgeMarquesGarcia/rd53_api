from __future__ import annotations
from pathlib import Path
from typing import Union, Optional
from src.config.txt.txt_manager import TxtManager
from src.config.xml.xml_manager import XmlManager
from src.config.system_config import SystemConfig


class CalibrationConfig:
    """
    Helper class for configuring calibration settings.
    
    NOT a singleton - creates temporary instances to configure
    the global SystemConfig singleton.
    
    Usage:
        cal = CalibrationConfig()
        cal.setup_calibration(base_dir, chip_id)
    """
    
    @staticmethod
    def setup_calibration(base_dir: str, chip_id: str) -> None:
        """
        Configure calibration settings in the global SystemConfig.
        
        Args:
            base_dir: Base directory for calibration data
            chip_id: Chip identifier
        """
        sys_config = SystemConfig()
        sys_config.set_txt_base_dir(base_dir)
        sys_config.create_txt_manager()
    
    @staticmethod
    def create_txt_manager(base_dir: str, chip_id: str) -> TxtManager:
        """Create and load a TxtManager instance with the configured Ph2_ACF directory."""
        sys_config = SystemConfig()
        ph2_acf_dir = sys_config.get_ph2_acf_dir()
        txt_manager = TxtManager(str(ph2_acf_dir), chip_id)
        txt_manager.load()
        return txt_manager
