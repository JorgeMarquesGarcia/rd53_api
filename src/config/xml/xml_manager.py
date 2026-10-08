from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import logging
from xml.etree import ElementTree as ET

from src.core import exceptions
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value
from src.core.decorators import ensure_loaded
from src.config.base_config_manager import BaseConfigManager


class XmlManager(BaseConfigManager):
    """
    Manager for RD53A XML configuration files.

    Note: All set_* methods auto-save changes to disk immediately.
    This ensures configurations are persisted before DAQ commands execute.
    Inside a ``with xml.batch():`` block the writes are grouped and the file
    is saved once when the block ends.
    """
    def __init__(self, path: str | Path | None = None, read_only: bool = False):
        self._path: Path | None = Path(path) if path else None
        self._read_only: bool = read_only

        self._tree : ET.ElementTree | None = None
        self._root : ET.Element | None = None

        self._dirty: bool = False
        self._loaded: bool = False
        self._batch_depth: int = 0

        self._last_loaded: datetime | None = None
        self.logger = logging.getLogger("XmlManager")

    def set_read_only(self, value: bool = True) -> None:
        self._read_only = value

    def is_ready(self) -> bool:
        return self._loaded and not self._dirty

    def can_save(self) -> bool:
        return self._loaded and not self._read_only and self._dirty

    def load(self, path: str | Path | None = None) -> None:
        if path:
            self._path = Path(path)

        if self._path is None:
            raise exceptions.XmlFileNotFoundError()

        if not self._path.exists():
            raise exceptions.XmlFileNotFoundError(str(self._path))

        try:
            self._tree = ET.parse(self._path)
            self._root = self._tree.getroot()
        except ET.ParseError as e:
            raise exceptions.XmlParsingError(f"Error parsing XML file: {e}") from e

        self._dirty = False
        self._loaded = True
        self._last_loaded = datetime.now()
        self.logger.info("XML file loaded from: %s", self._path)

    def reload(self, force: bool = False) -> None:
        if self._dirty and not force:
            raise exceptions.XmlUnsavedChangesError()
        self.load(self._path)

    def reset(self, force: bool = False) -> None:
        if self._dirty and not force:
            raise exceptions.XmlUnsavedChangesError()

        self._tree = None
        self._root = None
        self._dirty = False
        self._loaded = False
        self._last_loaded = None
        self.logger.info("XML manager state has been reset.")

    def is_loaded(self) -> bool:
        """Return True if an XML file is currently loaded."""
        return self._loaded

    def is_dirty(self) -> bool:
        """Return True if there are unsaved changes."""
        return self._dirty

    def is_read_only(self) -> bool:
        """Return True if the manager is in read-only mode."""
        return self._read_only

    def get_path(self) -> Path | None:
        """Return the path of the loaded XML file."""
        return self._path

    def _require_loaded(self) -> None:
        if not self._loaded or self._root is None:
            raise exceptions.XmlNotLoadedError()

    def _require_writable(self) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()

    # ------------------------------------------------------------------
    # Escritura agrupada
    # ------------------------------------------------------------------
    @contextmanager
    def batch(self):
        """Agrupa varios set_* en una única escritura del fichero.

        Los cambios se guardan al salir del bloque, también si dentro se lanza
        una excepción (igual que con el auto-guardado, lo ya modificado no se
        pierde). Los bloques se pueden anidar: guarda el más externo.
        """
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._dirty and not self._read_only:
                self.save()

    # ------------------------------------------------------------------
    # Acceso genérico
    # ------------------------------------------------------------------
    @ensure_loaded
    def root(self) -> ET.Element:
        """Return the root element of the XML tree."""
        return self._root

    @ensure_loaded
    def find(self, path: str) -> ET.Element | None:
        """Find and return the first matching element by path."""
        return self._root.find(path)

    @ensure_loaded
    def findall(self, path: str) -> list[ET.Element]:
        """Find and return all matching elements by path."""
        return self._root.findall(path)

    @ensure_loaded
    def get_text(self, path: str, default: str | None = None) -> str | None:
        """Get the text content of the first matching element by path."""
        element = self.find(path)
        if element is not None and element.text is not None:
            return element.text.strip()
        return default

    @ensure_loaded
    def get_attr(self, path: str, attr: str, default=None):
        element = self.find(path)
        if element is not None:
            return element.get(attr, default)
        return default

    # ------------------------------------------------------------------
    # Settings de calibración (<Settings>)
    # ------------------------------------------------------------------
    @ensure_loaded
    def _get_calibration_settings_node(self) -> ET.Element:
        settings = self._root.find("./Settings")
        if settings is None:
            raise exceptions.XmlStructureError("Calibration <Settings> node not found")
        return settings

    def _get_calibration_setting_node(self, name: str) -> ET.Element:
        node = self._get_calibration_settings_node().find(f"./Setting[@name='{name}']")
        if node is None:
            raise exceptions.UnknownCalibrationSettingError(name)
        return node

    @ensure_loaded
    def get_calibration_setting(self, name: str | CalibrationSettings) -> str:
        name = str(name)
        self.logger.debug("Retrieving calibration setting '%s' as String", name)
        return (self._get_calibration_setting_node(name).text or "").strip()

    @ensure_loaded
    def _compare_calibration_setting(self, setting: str | CalibrationSettings, value: Value) -> bool:
        return str(self.get_calibration_setting(setting)) == str(value)

    @ensure_loaded
    def set_calibration_setting(self, name: str | CalibrationSettings, value: str | int) -> None:
        self._require_writable()
        name = str(name)
        node = self._get_calibration_setting_node(name)

        if (node.text or "").strip() == str(value):
            self.logger.debug("Register %s already set to %s", name, value)
            return

        node.text = str(value)
        self._dirty = True
        self._auto_save()

    # ------------------------------------------------------------------
    # Navegación BeBoard / OpticalGroup / Hybrid / RD53A
    # ------------------------------------------------------------------
    @ensure_loaded
    def _get_be_board(self) -> ET.Element:
        board = self._root.find(".//BeBoard[@Id='0']")
        if board is None:
            raise KeyError("BeBoard with Id='0' not found.")
        return board

    @ensure_loaded
    def _get_optical_group(self) -> ET.Element:
        og = self._get_be_board().find(".//OpticalGroup[@Id='0']")
        if og is None:
            raise KeyError("OpticalGroup with Id='0' not found.")
        return og

    @ensure_loaded
    def _get_hybrid(self, hybrid_id: int) -> ET.Element:
        hybrid = self._get_optical_group().find(f".//Hybrid[@Id='{hybrid_id}']")
        if hybrid is None:
            raise exceptions.UnknownHybridError(hybrid_id)
        return hybrid

    @ensure_loaded
    def _get_rd53(self, hybrid_id: int, rd53_id: int) -> ET.Element:
        try:
            hybrid = self._get_hybrid(hybrid_id)
        except KeyError as e:   # falta BeBoard / OpticalGroup
            raise exceptions.XmlStructureError(str(e)) from e
        rd53 = hybrid.find(f".//RD53A[@Id='{rd53_id}']")
        if rd53 is None:
            raise exceptions.UnknownChipError(rd53_id, hybrid_id)
        return rd53

    @ensure_loaded
    def _get_chip_settings_node(self, hybrid_id: int, rd53_id: int) -> ET.Element:
        settings = self._get_rd53(hybrid_id, rd53_id).find("Settings")
        if settings is None:
            raise exceptions.XmlStructureError(
                f"Settings node not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        return settings

    # ------------------------------------------------------------------
    # Registros de control (user.ctrl_regs)
    # ------------------------------------------------------------------
    @ensure_loaded
    def _get_ctrl_regs_root(self) -> ET.Element:
        root = self._root.find(
            ".//Register[@name='user']/Register[@name='ctrl_regs']"
        )
        if root is None:
            raise KeyError("Control registers root (user.ctrl_regs) not found")
        return root

    @ensure_loaded
    def _get_fast_cmd_reg(self, index: int) -> ET.Element:
        reg = self._get_ctrl_regs_root().find(f"Register[@name='fast_cmd_reg_{index}']")
        if reg is None:
            raise KeyError(f"fast_cmd_reg_{index} not found")
        return reg

    @ensure_loaded
    def _get_by_path(self, path: str) -> ET.Element:
        parts = path.split(".")
        if parts[:2] != ["user", "ctrl_regs"]:
            raise ValueError("Path must start with 'user.ctrl_regs'")

        current = self._get_ctrl_regs_root()
        for p in parts[2:]:
            current = current.find(f"Register[@name='{p}']")
            if current is None:
                raise KeyError(f"Register '{p}' not found in path '{path}'")
        return current

    @ensure_loaded
    def get_register_value(self, reg: str | FastCmdReg) -> str:
        node = self._get_by_path(str(reg))
        return (node.text or "").strip()

    @ensure_loaded
    def set_register_value(self, reg: str | FastCmdReg, value: str | int) -> None:
        """Set a register value by path or FastCmdReg enum"""
        self._require_writable()
        node = self._get_by_path(str(reg))

        if (node.text or "").strip() == str(value):
            self.logger.debug("Register %s already set to %s", reg, value)
            return

        # Se conserva el formato del fichero: valor entre espacios
        node.text = f" {value} "
        self._dirty = True
        self.logger.info("Updated %s", reg)
        self._auto_save()

    @ensure_loaded
    def get_fast_cmd_setting(self, index: int, name: str) -> str:
        value = self._get_fast_cmd_reg(index).attrib.get(name)
        if value is None:
            raise KeyError(f"Attribute '{name}' not found in fast_cmd_reg_{index}")
        return value

    @ensure_loaded
    def _compare_register_value(self, setting: FastCmdReg | str, value: Value) -> bool:
        return str(self.get_register_value(setting)) == str(value)

    @ensure_loaded
    def set_fast_cmd_setting(self, index: int, name: str, value: str) -> None:
        self._require_writable()
        reg = self._get_fast_cmd_reg(index)
        if name not in reg.attrib:
            raise KeyError(f"Attribute '{name}' not found in fast_cmd_reg_{index}")
        reg.attrib[name] = str(value)
        self._dirty = True
        self.logger.info("Updated fast_cmd_reg_%d attribute %s", index, name)
        self._auto_save()

    # ------------------------------------------------------------------
    # Settings de chip (<RD53A><Settings .../>)
    # ------------------------------------------------------------------
    @ensure_loaded
    def get_chip_setting(self, hybrid_id: int, rd53_id: int, name: str | ChipSettings) -> str:
        name = str(name)
        settings = self._get_chip_settings_node(hybrid_id, rd53_id)
        try:
            return settings.attrib[name]
        except KeyError:
            raise exceptions.UnknownChipSettingError(name, rd53_id, hybrid_id) from None

    @ensure_loaded
    def compare_chip_setting(self, hybrid_id: int, rd53_id: int, setting: str | ChipSettings, value: Value) -> bool:
        return str(self.get_chip_setting(hybrid_id, rd53_id, setting)) == str(value)

    @ensure_loaded
    def get_all_chip_settings(self, hybrid_id: int, rd53_id: int) -> dict[str, str]:
        return dict(self._get_chip_settings_node(hybrid_id, rd53_id).attrib)

    @ensure_loaded
    def set_chip_setting(self, hybrid_id: int, rd53_id: int, name: str | ChipSettings, value: str | int) -> None:
        self._require_writable()
        name = str(name)
        settings = self._get_chip_settings_node(hybrid_id, rd53_id)
        if name not in settings.attrib:
            raise exceptions.UnknownChipSettingError(name, rd53_id, hybrid_id)

        if settings.attrib[name] == str(value):
            self.logger.debug("Register %s already set to %s", name, value)
            return

        settings.attrib[name] = str(value)
        self._dirty = True
        self._auto_save()

    @ensure_loaded
    def get_chip_enable(self, hybrid_id: int, rd53_id: int) -> bool:
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        value = rd53.attrib.get("enable")
        if value is None:
            raise exceptions.XmlStructureError(f"'enable' attribute not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        if value not in ("0", "1"):
            raise exceptions.XmlStructureError(f"Invalid 'enable' attribute value '{value}' in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'. Expected '0' or '1'.")
        return value == "1"

    @ensure_loaded
    def set_chip_enable(self, hybrid_id: int, rd53_id: int, enable: bool) -> None:
        self._require_writable()
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        if "enable" not in rd53.attrib:
            raise exceptions.XmlStructureError(f"'enable' attribute not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        new_value = "1" if enable else "0"
        if rd53.attrib["enable"] != new_value:
            rd53.attrib["enable"] = new_value
            self._dirty = True
            self._auto_save()

    @ensure_loaded
    def get_chip_config_file(self, hybrid_id: int, rd53_id: int) -> str:
        return self._get_rd53(hybrid_id, rd53_id).attrib.get("configFile", "")

    @ensure_loaded
    def set_chip_config_file(self, hybrid_id: int, rd53_id: int, file_name: str) -> None:
        self._require_writable()
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        if rd53.attrib.get("configFile") == file_name:
            return
        rd53.attrib["configFile"] = file_name
        self._dirty = True
        self._auto_save()

    # ------------------------------------------------------------------
    # Guardado
    # ------------------------------------------------------------------
    @ensure_loaded
    def save(self, path: str | Path | None = None) -> None:
        self._require_writable()

        target_path = Path(path) if path else self._path
        if target_path is None:
            raise exceptions.XmlFileNotFoundError()

        self._tree.write(
            target_path,
            encoding="utf-8",
            xml_declaration=True
        )

        if path:
            self._path = target_path
        self._dirty = False
        self.logger.info("XML saved to %s", target_path)

    def _auto_save(self) -> None:
        """Guarda en la ruta actual, salvo dentro de batch() (se guarda al final)."""
        if self._batch_depth == 0:
            self.save()

    @ensure_loaded
    def save_as(self, path: str | Path) -> None:
        """Guarda en `path` y pasa a gestionar ese fichero."""
        self.save(path)
