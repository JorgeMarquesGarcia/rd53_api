from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable, Union, Optional
from src.chip.register_map import ChipSettings
from src.config.xml.xml_manager import XmlManager
from src.config.system_config import SystemConfig

logger = logging.getLogger(__name__)


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

    @staticmethod
    def get_chip_thresholds(
        chips: Iterable[tuple[int, int]],
    ) -> dict[tuple[int, int], int]:
        """
        Read Vthreshold_LIN from the configured XML for each chip.

        The XML is opened read-only, so nothing is modified on disk.
        Chips whose value cannot be read (chip missing in the XML, attribute
        missing, non-integer value) are NOT included in the result and a
        warning is logged: no default value is ever invented.

        Args:
            chips: iterable of (hybrid_id, rd53_id).

        Returns:
            {(hybrid_id, rd53_id): Vthreshold_LIN} only for the chips read.

        Raises:
            SystemNotConfiguredError: if no XML path is configured.
        """
        xml = SystemConfig().create_xml_manager(read_only=True)
        thresholds: dict[tuple[int, int], int] = {}
        for hybrid_id, rd53_id in chips:
            try:
                raw = xml.get_chip_setting(hybrid_id, rd53_id, ChipSettings.VTHRESHOLD_LIN)
                thresholds[(hybrid_id, rd53_id)] = int(str(raw).strip())
            except Exception as e:
                logger.warning(
                    "Cannot read Vthreshold_LIN for Hybrid %s / RD53A %s: %s",
                    hybrid_id, rd53_id, e,
                )
        return thresholds