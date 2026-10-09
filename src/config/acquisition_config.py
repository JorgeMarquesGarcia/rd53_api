from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Iterable
from src.acquisition.maps.acquisition_map import (
    DEFAULT_LATENCY, LATENCY_MAX, DEFAULT_NTRIGGERS, NTRIGGERS_MAX,
)
from src.chip.register_map import ChipSettings
from src.config.xml.xml_manager import XmlManager
from src.config.system_config import SystemConfig

logger = logging.getLogger(__name__)

# LATENCY_CONFIG y nTRIGxEvent de las adquisiciones, guardados entre sesiones.
# No viven en el XML: cada calibración escribe allí los suyos (CalibrationMap).
ACQ_SETTINGS_FILE = Path.home() / ".rd53a_acquisition_settings.json"


def _read_settings() -> dict:
    try:
        settings = json.loads(ACQ_SETTINGS_FILE.read_text(encoding="utf-8"))
        return settings if isinstance(settings, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("Cannot read the acquisition settings from %s: %s", ACQ_SETTINGS_FILE, e)
        return {}


def _get_setting(key: str, default: int, minimum: int, maximum: int) -> int:
    value = _read_settings().get(key, default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        logger.warning("Saved acquisition %s is not an integer: %r", key, value)
        return default
    if not minimum <= value <= maximum:
        logger.warning("Saved acquisition %s out of range (%d-%d): %s", key, minimum, maximum, value)
        return default
    return value


def _save_setting(key: str, value: int) -> None:
    """Guarda una clave sin perder las demás."""
    settings = _read_settings()
    settings[key] = int(value)
    try:
        ACQ_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Cannot save the acquisition %s to %s: %s", key, ACQ_SETTINGS_FILE, e)


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
    def setup_acq(ph2_acf_dir: str | Path, xml_path: str | Path) -> None:
        """
        Configure acquisition settings in the global SystemConfig.

        Args:
            ph2_acf_dir: Path to Ph2_ACF directory
            xml_path: Path to XML configuration file
        """
        SystemConfig.set_ph2_acf_dir(ph2_acf_dir)
        SystemConfig.set_xml_path(xml_path)
        SystemConfig.create_xml_manager()   # valida que el XML se puede cargar

    @staticmethod
    def get_latency() -> int:
        """LATENCY_CONFIG de las adquisiciones: la guardada con save_latency o DEFAULT_LATENCY."""
        return _get_setting("latency", DEFAULT_LATENCY, 0, LATENCY_MAX)

    @staticmethod
    def save_latency(latency: int) -> None:
        """Guarda la LATENCY_CONFIG de las adquisiciones para las próximas sesiones."""
        _save_setting("latency", latency)

    @staticmethod
    def get_ntriggers() -> int:
        """nTRIGxEvent de las adquisiciones: el guardado con save_ntriggers o DEFAULT_NTRIGGERS."""
        return _get_setting("ntriggers", DEFAULT_NTRIGGERS, 1, NTRIGGERS_MAX)

    @staticmethod
    def save_ntriggers(ntriggers: int) -> None:
        """Guarda el nTRIGxEvent de las adquisiciones para las próximas sesiones."""
        _save_setting("ntriggers", ntriggers)

    @staticmethod
    def get_xml_manager() -> XmlManager:
        """Create and load an XmlManager for the XML configured in SystemConfig."""
        return SystemConfig.create_xml_manager()

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
        xml = SystemConfig.create_xml_manager(read_only=True)
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

    @staticmethod
    def set_chip_latency(chips: Iterable[tuple[int, int]], latency: int) -> dict[tuple[int, int], str]:
        """
        Write LATENCY_CONFIG = latency in the configured XML for each chip.

        All chips are written in a single save of the XML.

        Args:
            chips: iterable of (hybrid_id, rd53_id).
            latency: new LATENCY_CONFIG value.

        Returns:
            {(hybrid_id, rd53_id): error} for the chips that could not be
            written (chip missing in the XML, ...); empty if all were written.

        Raises:
            SystemNotConfiguredError: if no XML path is configured.
        """
        xml = SystemConfig.create_xml_manager(read_only=False)
        failed: dict[tuple[int, int], str] = {}
        with xml.batch():   # una sola escritura del XML
            for hybrid_id, rd53_id in chips:
                try:
                    xml.set_chip_setting(hybrid_id, rd53_id, ChipSettings.LATENCY, int(latency))
                except Exception as e:
                    logger.warning("Cannot set LATENCY_CONFIG for Hybrid %s / RD53A %s: %s",
                                   hybrid_id, rd53_id, e)
                    failed[(hybrid_id, rd53_id)] = str(e)
        return failed
