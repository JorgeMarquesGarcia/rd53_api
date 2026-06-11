from __future__ import annotations
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
    """
    def __init__(self, path: str | None = None, read_only: bool = False):
        self._path: Path | None = Path(path) if path else None
        self._read_only: bool = read_only

        self._tree : ET.ElementTree | None = None
        self._root : ET.Element | None = None

        self._dirty: bool = False
        self._loaded: bool = False
        
        self._last_loaded: datetime | None = None
        self.logger = logging.getLogger("XmlManager")

    def set_read_only(self, value: bool = True) -> None:
        self._read_only = value

    def is_ready(self) -> bool:
        return self._loaded and not self._dirty
    
    def can_save(self) -> bool:
        return self._loaded and not self._read_only and self._dirty


    def load(self, path: str | None = None) -> None:
        if path:
            self._path = Path(path)

        if self._path is None:
            raise exceptions.XmlFileNotFoundError()
        
        if not self._path.exists():
            raise exceptions.XmlFileNotFoundError(self._path)
        
        try: 
            self._tree = ET.parse(self._path)
            self._root = self._tree.getroot()
        except ET.ParseError as e:
            raise exceptions.XmlParsingError(f"Error parsing XML file: {e}") from e
        
        self._dirty = False
        self._loaded = True
        self._last_loaded = datetime.now()
        self.logger.info(f"XML file loaded from: {self._path}")

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
    
    @ensure_loaded
    def root(self) -> ET.Element:
        """Return the root element of the XML tree."""
        assert self._root is not None  # for type checker
        return self._root

    @ensure_loaded
    def find(self, path: str) -> ET.Element | None:
        """Find and return the first matching element by path."""
        assert self._root is not None  # for type checker
        return self._root.find(path)
    
    @ensure_loaded
    def findall(self, path: str) -> list[ET.Element]:
        """Find and return all matching elements by path."""
        assert self._root is not None  # for type checker
        return self._root.findall(path)
    
    @ensure_loaded
    def get_text(self, path: str, default: str | None = None) -> str | None:
        """Get the text content of the first matching element by path."""
        element = self.find(path)
        if element is not None and element.text is not None:
            return element.text.strip()
        return default
    
    @ensure_loaded
    def get_attr(self,path: str, attr: str, default=None):
        element = self.find(path)
        if element is not None:
            return element.get(attr, default)
        return default
    
    @ensure_loaded
    def _get_calibration_settings_node(self) -> ET.Element:
        settings = self._root.find("./Settings")
        if settings is None:
            raise exceptions.XmlStructureError("Calibration <Settings> node not found")
        return settings
    
    @ensure_loaded
    def get_calibration_setting(self, name: str | CalibrationSettings) -> str:
        self.logger.info("Retrieving calibration setting '%s' as String", name)
        if isinstance(name, CalibrationSettings):
            name = str(name)
        cal_settings = self._get_calibration_settings_node()
        node = cal_settings.find(f"./Setting[@name='{name}']")
        if node is None:
            raise exceptions.UnknownCalibrationSettingError(name)
        return (node.text or "").strip()
    
    @ensure_loaded
    def _compare_calibration_setting(self, setting: str | CalibrationSettings, value: Value) -> bool:
        return str(self.get_calibration_setting(setting)) == str(value)

    @ensure_loaded
    def set_calibration_setting(self, name: str | CalibrationSettings, value: str | int) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()
        
        if self._compare_calibration_setting(name, value):
            self.logger.debug("Register %s already set to %s", name, value)
            return

        if isinstance(name, CalibrationSettings):
            name = str(name)

        cal_settings = self._get_calibration_settings_node()
        node = cal_settings.find(f"./Setting[@name='{name}']")
        if node is None:
            raise exceptions.UnknownCalibrationSettingError(name)

        node.text = str(value)
        self._dirty = True
        self._auto_save()
    
    @ensure_loaded
    def _get_be_board(self) -> ET.Element | None:
        board = self._root.find(".//BeBoard[@Id='0']")
        if board is None:
            raise KeyError("BeBoard with Id='0' not found.")
        return board
    
    @ensure_loaded
    def _get_optical_group(self) -> ET.Element | None:
        board = self._get_be_board()
        og = board.find(".//OpticalGroup[@Id='0']")
        if og is None:
            raise KeyError("OpticalGroup with Id='0' not found.")
        return og
    
    @ensure_loaded
    def _get_hybrid(self, hybrid_id: int) -> ET.Element | None:
        og = self._get_optical_group()
        hybrid = og.find(f".//Hybrid[@Id='{hybrid_id}']") 
        if hybrid is None: 
            raise exceptions.UnknownHybridError(hybrid_id)
        return hybrid
    
    @ensure_loaded
    def _get_rd53(self,hybrid_id: int, rd53_id: int) -> ET.Element | None:
        hybrid_id = self._get_hybrid(hybrid_id)
        rd53 = hybrid_id.find(f".//RD53A[@Id='{rd53_id}']") 
        if rd53 is None:
            raise exceptions.UnknownChipError(rd53_id, hybrid_id)
        return rd53
    
    @ensure_loaded
    def _get_chip_settings_node(self, hybrid_id: int, rd53_id: int) -> ET.Element | None:
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        settings = rd53.find("Settings") 
        if settings is None:
            raise KeyError(f"Settings node not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        return settings
        
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
        ctrl = self._get_ctrl_regs_root()
        reg = ctrl.find(f"Register[@name='fast_cmd_reg_{index}']")
        if reg is None:
            raise KeyError(f"fast_cmd_reg_{index} not found")
        return reg



    @ensure_loaded
    def _get_by_path(self, path: str) -> ET.Element | None: 
        parts =path.split(".")
        if parts[:2] != ["user", "ctrl_regs"]:
            raise ValueError("Path must start with 'user.ctrl_regs'")
        
        current = self._get_ctrl_regs_root()
        for p in parts[2:]:
            current = current.find(f"Register[@name='{p}']")
            if current is None:
                raise KeyError(f"Register '{p}' not found in path '{path}'")
        return current

    @ensure_loaded
    def get_register_value(self, reg: str | FastCmdReg) -> str | None:
        """Get a register value by path or FastCmdReg enum"""
        if isinstance(reg, FastCmdReg):
            path = str(reg)
        else:
            path = reg
        
        node = self._get_by_path(path)
        if isinstance(node, KeyError):
            raise node
        return node.attrib.get("value", None)
    
    @ensure_loaded
    def set_register_value(self, reg: str | FastCmdReg, value: str | int) -> None:
        """Set a register value by path or FastCmdReg enum"""
        if self._read_only:
            raise PermissionError("XML manager is in read-only mode; cannot modify registers.")
        
        if self._compare_register_value(reg, value):
            self.logger.debug("Register %s already set to %s", reg, value)
            return
        
        if isinstance(reg, FastCmdReg):
            path = str(reg)
        else:
            path = reg
        
        node = self._get_by_path(path)
        if isinstance(node, KeyError):
            raise node
        
        node.text = f" {str(value)} "
        self._dirty = True
        self.logger.info("Updated %s", reg)
        self._auto_save()
    
    @ensure_loaded
    def get_fast_cmd_setting(self, index: int, name: str) -> str:
        reg = self._get_fast_cmd_reg(index)
        value = reg.attrib.get(name)
        if value is None:
            raise KeyError(f"Attribute '{name}' not found in fast_cmd_reg_{index}")
        return value
    
    @ensure_loaded
    def _compare_register_value(self, setting: FastCmdReg | str, value: Value) -> bool:
        return str(self.get_register_value(setting)) == str(value)
    
    @ensure_loaded
    def set_fast_cmd_setting(self, index: int, name: str, value: str) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()
        reg = self._get_fast_cmd_reg(index)
        if name not in reg.attrib:
            raise KeyError(f"Attribute '{name}' not found in fast_cmd_reg_{index}")
        reg.attrib[name] = str(value)
        self._dirty = True
        self.logger.info("Updated fast_cmd_reg_%d attribute %s", index, name)
        self._auto_save()

    @ensure_loaded
    def get_chip_setting(self, hybrid_id: int, rd53_id: int, name: str | ChipSettings) -> str | None:
        if isinstance(name, ChipSettings):
            name = str(name)
        
        try:
            settings = self._get_chip_settings_node(hybrid_id, rd53_id)
        except KeyError as e:
            raise exceptions.XmlStructureError(str(e)) from e
        
        return settings.attrib[name]
    
    @ensure_loaded
    def compare_chip_setting(self, hybrid_id: int, rd53_id: int, setting: str | ChipSettings, value: Value) -> bool:
        return str(self.get_chip_setting(hybrid_id, rd53_id, setting)) == str(value)
    
    @ensure_loaded
    def get_all_chip_settings(self, hybrid_id: int, rd53_id: int) -> dict[str, str]:
        try:
            settings = self._get_chip_settings_node(hybrid_id, rd53_id)
        except KeyError as e:
            raise exceptions.XmlStructureError(str(e)) from e
        return dict(settings.attrib)

    @ensure_loaded
    def set_chip_setting(self, hybrid_id: int, rd53_id: int, name: str | ChipSettings, value: str | int) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()
        
        if self.compare_chip_setting(hybrid_id, rd53_id, name, value):
            self.logger.debug("Register %s already set to %s", name, value)
            return

        if isinstance(name, ChipSettings):
            name = str(name)   
    
        try:
            settings = self._get_chip_settings_node(hybrid_id, rd53_id)
        except KeyError as e:
            raise exceptions.XmlStructureError(str(e)) from e
        
        if name not in settings.attrib:
            raise exceptions.UnknownChipSettingError(name, rd53_id, hybrid_id)
        
        settings.attrib[name] = str(value)
        self._dirty = True
        self._auto_save()

    @ensure_loaded
    def get_chip_enable(self, hybrid_id: int, rd53_id: int) -> bool:
        try:
            rd53 = self._get_rd53(hybrid_id, rd53_id)
        except KeyError as e:
            raise exceptions.XmlStructureError(str(e)) from e
        
        if "enable" not in rd53.attrib:
            raise exceptions.XmlStructureError(f"'enable' attribute not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        
        value = rd53.attrib["enable"]

        if value not in ("0","1"):
            raise exceptions.XmlStructureError(f"Invalid 'enable' attribute value '{value}' in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'. Expected '0' or '1'.")
        
        return value == "1"

    @ensure_loaded
    def set_chip_enable(self, hybrid_id: int, rd53_id: int, enable: bool) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()
        try:
            rd53 = self._get_rd53(hybrid_id, rd53_id)
        except KeyError as e:
            raise exceptions.XmlStructureError(str(e)) from e
        if "enable" not in rd53.attrib:
            raise exceptions.XmlStructureError(f"'enable' attribute not found in RD53A '{rd53_id}' of Hybrid '{hybrid_id}'.")
        new_value = "1" if enable else "0"
        if rd53.attrib["enable"] != new_value:
            rd53.attrib["enable"] = new_value
            self._dirty = True
            self._auto_save()

    @ensure_loaded
    def get_chip_config_file(self, hybrid_id: int, rd53_id: int) -> str | None: 
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        return rd53.attrib.get("configFile", "")
    
    @ensure_loaded
    def set_chip_config_file(self, hybrid_id: int, rd53_id: int, file_name: str) -> None:
        if self._read_only:
            raise exceptions.XmlPermissionError()
        rd53 = self._get_rd53(hybrid_id, rd53_id)
        rd53.attrib["configFile"] = file_name
        self._dirty = True
        self._auto_save()

    @ensure_loaded
    def save(self, path: str | Path | None = None) -> None:
        if self._read_only:
            raise PermissionError()

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
        self.logger.info(f"XML saved to {target_path}")
    
    def _auto_save(self) -> None:
        """Internal auto-save method that saves to current path."""
        self.save()
    
    @ensure_loaded
    def save_as(self, path: str | Path) -> None:
        if self._read_only:
            raise PermissionError()

        target = Path(path)

        self._tree.write(
            target,
            encoding="utf-8",
            xml_declaration=True
        )

        self._directory = target
        self._dirty = False
        self.logger.info(f"XML saved as {target}")



















