from __future__ import annotations
import os
from pathlib import Path
import uproot
import logging
from src.config.base_config_manager import BaseConfigManager
from src.core.exceptions import RootFileNotFoundError
"""Este fichero simplemente tiene que acceder al fichero .root y extraer los los datos ahí guardados, vamos un poco lo que hace el awa.py de src.
creo que los voy a sacar n awkwards y mandarlos luego al de analisis aunque no estou muy seguro de si convertirlos a df o listas. 
Yo creo que simplemente con extraer los datos es suficiente, mandando uno de hits y otro de todos los datos. 
¿Lanzar la terminal con -b iria aqui? ==> NO
"""


class RootManager(BaseConfigManager):
    def __init__(self, root_path: str | Path):
        self._root_path = Path(root_path)
        self.logger = logging.getLogger(__name__)
        self._loaded = False
        self._dirty = False
        self.arrays = None
        self.df = None
        self.logger.debug(f"RootManager initialized with path: {self._root_path}")

    def _open_with_uproot(self):
        self.logger.debug(f"Attempting to open ROOT file with uproot: {self._root_path}")
        return uproot.open(self._root_path)
    
    def _list_root_files(self) -> list[Path]:
        files = sorted(self._root_path.glob("*.root"), key=os.path.getmtime)
        self.logger.info("Found ROOT files: %s", files)
        return files

    def _load_latest_root_file(self):
        files = self._list_root_files()
        if not files:
            raise RootFileNotFoundError(f"No ROOT files found in directory: {self._root_path}")
        newest_file = files[-1]
        self._root_path = newest_file
        self.logger.info(f"Loading latest ROOT file: {newest_file}")
        self._load()
    
    def inspect(self) -> dict:
        """Lista el contenido del fichero ROOT y sus tipos."""
        with uproot.open(self._root_path) as f:
            contents = {key: type(f[key]).__name__ for key in f.keys()}
            self.logger.info("ROOT file contents: %s", contents)
            return contents
    
    def _load_select_root_file(self, file_path: str | Path):
        if not Path(file_path).exists():
            raise RootFileNotFoundError(f"Specified ROOT file not found: {file_path}")
        self._root_path = Path(file_path)
        self.logger.info(f"Loading specified ROOT file: {file_path}") 
        self._load()
    
    # def _load(self):
    #     """Load the ROOT file and read its contents into internal structures."""
    #     if not self._root_path.exists():
    #         raise FileNotFoundError(f"ROOT file not found: {self._root_path}")
    #     root_file = self._open_with_uproot()
    #
    #     try:
    #         ttree = root_file["theTree"] # Replace with actual TTree name if known
    #         if not ttree:
    #             raise ValueError("No TTree found in the ROOT file.")
    #         
    #         self.arrays = ttree.arrays(library="ak")
    #         self._loaded = True
    #         self._dirty = False
    #         self.logger.info(f"ROOT file '{self._root_path}' loaded successfully with uproot.") 
    #         
    #     except Exception as e:
    #         self.logger.error("Error processing ROOT file: %s", e)
    #         raise

    def _load(self):
        if not self._root_path.exists():
            raise FileNotFoundError(f"ROOT file not found: {self._root_path}")
        
        with uproot.open(self._root_path) as root_file:
            keys = root_file.keys()
            self.logger.debug(f"Keys in ROOT file: {keys}")

            # Buscar el primer TTree disponible
            ttree = None
            for key in keys:
                obj = root_file[key]
                if isinstance(obj, uproot.behaviors.TTree.TTree):
                    ttree = obj
                    self.logger.info(f"Found TTree: '{key}'")
                    break
            
            if ttree is None:
                raise ValueError(f"No TTree found in ROOT file. Keys: {keys}")
            
            self.arrays = ttree.arrays(library="ak")
            self._loaded = True
            self._dirty = False
    
    # Implement abstract methods from BaseConfigManager
    def load(self, path: str | Path | None = None) -> None:
        """Load configuration from file."""
        if path is not None:
            self._load_select_root_file(path)
        else:
            self._load_latest_root_file()

    
    def save(self, path: str | Path | None = None) -> None:
        """Save configuration to file. ROOT files are read-only, so this raises NotImplementedError."""
        raise NotImplementedError("ROOT files are read-only and cannot be saved.")
    
    def is_loaded(self) -> bool:
        """Check if configuration is currently loaded."""
        return self._loaded
    
    def is_dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._dirty
    
    def get_path(self) -> Path | None:
        """Get the current file path."""
        return self._root_path

  
    

