from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Union
from src.chip.register_map import CalibrationSettings, ChipSettings, FastCmdReg, Value


# Type alias para el diccionario de settings
SettingsDict = dict[Union[ChipSettings, CalibrationSettings, FastCmdReg], Value]


class BaseMap(ABC):
    """
    Base class for all configuration maps (calibration & acquisition).
    
    A Map defines a preset configuration for a specific operation.
    All maps must implement to_dict() which returns the settings to apply.
    
    Usage:
        class MyCalibrationMap(BaseMap):
            def __init__(self):
                self._n_events = 100
                self._threshold = 350
            
            def to_dict(self) -> SettingsDict:
                return {
                    CalibrationSettings.N_EVENTS: self._n_events,
                    ChipSettings.VTHRESHOLD_LIN: self._threshold,
                }
    """
    
    @abstractmethod
    def to_dict(self) -> SettingsDict:
        """
        Convert map settings to dictionary.
        
        Returns:
            Dictionary mapping settings (ChipSettings, CalibrationSettings, 
            or FastCmdReg) to their values.
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"
