from __future__ import annotations
from pathlib import Path
from typing import Union, Optional
from rd53_api.config.xml.xml_manager import XmlManager
from rd53_api.config.system_config import SystemConfig


class AcquisitionConfig:
    """
    Helper class for configuring acquisition settings.
    
    NOT a singleton - creates temporary instances to configure
    the global SystemConfig singleton.
    
    Usage:
        acq = AcquisitionConfig()
        acq.setup_acq(ph2_acf_dir, xml_path)
    """
    
    @staticmethod
    def setup_acq(ph2_acf_dir: Union[str, Path], xml_path: Union[str, Path]) -> None:
        """
        Configure acquisition settings in the global SystemConfig.
        
        Args:
            ph2_acf_dir: Path to Ph2_ACF directory
            xml_path: Path to XML configuration file
        """
        sys_config = SystemConfig()
        sys_config.set_ph2_acf_dir(ph2_acf_dir)
        sys_config.set_xml_path(xml_path)
        sys_config.create_xml_manager()
    
    @staticmethod
    def get_xml_manager() -> XmlManager:
        """Get the configured XmlManager from SystemConfig."""
        sys_config = SystemConfig()
        return sys_config.get_xml_manager()
