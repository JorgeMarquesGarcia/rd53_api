from __future__ import annotations
from pathlib import Path

from src.config.system_config import SystemConfig


class AnalysisConfig:
    """
    Helper class for configuring analysis settings.

    NOT a singleton - creates temporary instances to configure
    the global SystemConfig singleton.

    Usage:
        analysis = AnalysisConfig()
        analysis.setup_analysis(root_path)
    """

    @staticmethod
    def setup_analysis(root_path: str | Path) -> None:
        """
        Configure analysis settings in the global SystemConfig.

        Args:
            root_path: Path to the root file
        """
        SystemConfig.set_root_path(root_path)
