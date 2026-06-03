from __future__ import annotations
from pathlib import Path
from typing import Union, Optional
from rd53_api.config.xml.xml_manager import XmlManager
from rd53_api.config.system_config import SystemConfig


class AnalysisConfig:
    """
    Helper class for configuring analysis settings.
    
    NOT a singleton - creates temporary instances to configure
    the global SystemConfig singleton.
    
    Usage:
        analysis = AnalysisConfig()
        analysis.setup_analysis(ph2_acf_dir, xml_path)
    """
    
    @staticmethod
    def setup_analysis(root_path):
        """
        Configure analysis settings in the global SystemConfig.
        
        Args:
            root_path: Path to the root file
        """
        sys_config = SystemConfig()
        sys_config.set_root_path(root_path)

