from __future__ import annotations
from pathlib import Path

from src.config.txt.txt_manager import TxtManager
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
    def setup_calibration(base_dir: str | Path, chip_id: str) -> TxtManager:
        """
        Configure calibration settings in the global SystemConfig.

        Args:
            base_dir: Base directory for calibration data (TXT files)
            chip_id: Chip identifier

        Returns:
            The loaded TxtManager of the chip (validates that its TXT exists).
        """
        SystemConfig.set_txt_base_dir(base_dir)
        return SystemConfig.create_txt_manager(chip_id)

    @staticmethod
    def create_txt_manager(base_dir: str | Path, chip_id: str) -> TxtManager:
        """Create and load a TxtManager instance for `chip_id` in `base_dir`."""
        txt_manager = TxtManager(str(base_dir), chip_id)
        txt_manager.load()
        return txt_manager
