from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class BaseConfigManager(ABC):
    """Abstract base class for configuration file managers (XML, TXT, etc.)."""
    
    @abstractmethod
    def load(self, path: str | Path | None = None) -> None:
        """
        Load configuration from file.
        
        Args:
            path: Optional path to load from. If None, uses stored path.
        """
        pass
    
    @abstractmethod
    def save(self, path: str | Path | None = None) -> None:
        """
        Save configuration to file.
        
        Args:
            path: Optional path to save to. If None, uses original path.
        """
        pass
    
    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if configuration is currently loaded.
        
        Returns:
            True if configuration is loaded, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_dirty(self) -> bool:
        """
        Check if there are unsaved changes.
        
        Returns:
            True if there are unsaved changes, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_path(self) -> Path | None:
        """
        Get the current file path.
        
        Returns:
            Path to the configuration file, or None if not set.
        """
        pass
