"""Acceso a los ficheros .root de datos del detector.

Abre el fichero con uproot y extrae el TTree de hits como arrays de awkward;
los análisis (src.analysis) trabajan sobre esos arrays.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable

import uproot

from src.config.base_config_manager import BaseConfigManager
from src.core.exceptions import RootFileNotFoundError

_TREE_CLASSNAMES = ("TTree", "TNtuple", "TNtupleD")


class RootManager(BaseConfigManager):
    """Carga el primer TTree de un fichero .root.

    root_path puede ser un fichero .root o una carpeta: con una carpeta, load()
    sin argumentos carga el .root más reciente que contenga.

    branches: ramas a leer (None = todas). Leer solo las que usa el análisis
    es varias veces más rápido y ocupa mucha menos memoria.
    """

    def __init__(self, root_path: str | Path, branches: Iterable[str] | None = None):
        self._root_path = Path(root_path)
        self._branches: list[str] | None = list(branches) if branches is not None else None
        self.logger = logging.getLogger(__name__)
        self._loaded = False
        self._dirty = False
        self.arrays = None
        self.df = None
        self.logger.debug("RootManager initialized with path: %s", self._root_path)

    def _open_with_uproot(self):
        self.logger.debug("Attempting to open ROOT file with uproot: %s", self._root_path)
        return uproot.open(self._root_path)

    def _list_root_files(self) -> list[Path]:
        files = sorted(self._root_path.glob("*.root"), key=lambda p: p.stat().st_mtime)
        self.logger.info("Found ROOT files: %s", files)
        return files

    def _load_latest_root_file(self):
        files = self._list_root_files()
        if not files:
            raise RootFileNotFoundError(f"No ROOT files found in directory: {self._root_path}")
        newest_file = files[-1]
        self._root_path = newest_file
        self.logger.info("Loading latest ROOT file: %s", newest_file)
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
        self.logger.info("Loading specified ROOT file: %s", file_path)
        self._load()

    @staticmethod
    def _find_tree(root_file):
        """Devuelve (clave, TTree) del primer TTree del fichero.

        classnames() solo lee las cabeceras de las claves, así no se
        deserializa cada objeto del fichero para encontrar el árbol.
        """
        for key, classname in root_file.classnames().items():
            if classname in _TREE_CLASSNAMES:
                obj = root_file[key]
                if isinstance(obj, uproot.behaviors.TTree.TTree):
                    return key, obj
        # Respaldo: clases derivadas de TTree con otro nombre
        for key in root_file.keys():
            obj = root_file[key]
            if isinstance(obj, uproot.behaviors.TTree.TTree):
                return key, obj
        return None, None

    def _load(self):
        if not self._root_path.exists():
            raise FileNotFoundError(f"ROOT file not found: {self._root_path}")

        with uproot.open(self._root_path) as root_file:
            key, ttree = self._find_tree(root_file)
            if ttree is None:
                raise ValueError(f"No TTree found in ROOT file. Keys: {root_file.keys()}")
            self.logger.info("Found TTree: '%s'", key)

            if self._branches is None:
                self.arrays = ttree.arrays(library="ak")
            else:
                self.arrays = ttree.arrays(filter_name=self._branches, library="ak")
            self._loaded = True
            self._dirty = False

    # Implement abstract methods from BaseConfigManager
    def load(self, path: str | Path | None = None) -> None:
        """Carga `path`; sin argumento, el fichero configurado o el .root más reciente de la carpeta."""
        if path is not None:
            self._load_select_root_file(path)
        elif self._root_path.is_file():
            self._load_select_root_file(self._root_path)
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
