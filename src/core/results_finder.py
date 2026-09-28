"""results_finder.py - Búsqueda de los ficheros más recientes en la carpeta Results.

Sin dependencias de Qt ni de SystemConfig: recibe la carpeta como argumento
para poder testearse de forma aislada.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Extensiones válidas por modo
ROOT_EXT = ".root"
RAW_EXT = ".raw"

# Sufijos de nombre de los ficheros .root que producen los scans de calibración
# (los mismos que usa CalibrationTab._load_plots en pattern_map)
CALIBRATION_NAME_PATTERNS: tuple[str, ...] = (
    "SCurve",
    "ThrEqualization",
    "NoiseScan",
    "PixelAlive",
)

ACQUISITION_NAME_PATTERNS: tuple[str, ...] = (
    "Physics",
)

def latest_files(
    directory: str | Path,
    extensions: Iterable[str],
    name_patterns: Iterable[str] | None = None,
    n: int = 3,
) -> list[Path]:
    """Devuelve los `n` ficheros más recientes (por mtime, del más nuevo al más antiguo).

    Args:
        directory:     carpeta a inspeccionar (no recursivo).
        extensions:    extensiones admitidas, con punto (p.ej. (".root", ".raw")).
        name_patterns: si se indica, el nombre del fichero debe contener alguno
                       de estos textos (sin distinguir mayúsculas).
        n:             número máximo de ficheros a devolver.

    Devuelve lista vacía si la carpeta no existe o no hay coincidencias.
    """
    folder = Path(directory)
    if not folder.is_dir():
        logger.warning("Results directory not found: %s", folder)
        return []

    exts = {e.lower() for e in extensions}
    patterns = [p.lower() for p in name_patterns] if name_patterns else None

    candidates: list[tuple[float, Path]] = []
    for p in folder.iterdir():
        try:
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            if patterns and not any(pat in p.name.lower() for pat in patterns):
                continue
            candidates.append((p.stat().st_mtime, p))
        except OSError as e:  # fichero desaparecido entre iterdir y stat
            logger.debug("Skipping %s: %s", p, e)

    candidates.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in candidates[:n]]