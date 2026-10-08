"""results_finder.py - Búsqueda de ficheros en la carpeta Results y deducción
del tipo de análisis a partir del nombre.

Sin dependencias de Qt, ROOT ni SystemConfig: recibe las rutas como argumento
para poder testearse de forma aislada.
"""
from __future__ import annotations
import heapq
import logging
import os
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Extensiones válidas por modo
ROOT_EXT = ".root"
RAW_EXT = ".raw"

# Fuente única: clave de análisis -> sufijo en el nombre del .root
# (Run000193_SCurve.root, Run000192_NoiseScan.root, ...)
ANALYSIS_FILE_SUFFIX: dict[str, str] = {
    "scurve":     "SCurve",
    "threqu":     "ThrEqualization",
    "noise":      "NoiseScan",
    "pixelalive": "PixelAlive",
    "gainopt":    "GainOptimization",
    "gain":       "Gain",
}

# Ficheros .root de calibración
CALIBRATION_NAME_PATTERNS: tuple[str, ...] = tuple(ANALYSIS_FILE_SUFFIX.values())

# Ficheros de adquisición: Run000XXX_Physics_Board000.raw / .root
ACQUISITION_NAME_PATTERNS: tuple[str, ...] = ("_Physics_Board",)


def detect_analysis(path: str | Path) -> str | None:
    """Deduce la clave de análisis ('scurve', 'threqu', ...) a partir del nombre.

    Devuelve None si el nombre no corresponde a ningún análisis de calibración.
    """
    name = Path(path).name.lower()
    # Sufijo más largo primero: "GainOptimization" también contiene "Gain"
    for key, suffix in sorted(ANALYSIS_FILE_SUFFIX.items(), key=lambda kv: -len(kv[1])):
        if suffix.lower() in name:
            return key
    return None


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
    # scandir: el filtrado por nombre no toca el disco y stat() solo se hace
    # para los ficheros que pasan el filtro
    with os.scandir(folder) as entries:
        for entry in entries:
            name = entry.name.lower()
            if os.path.splitext(name)[1] not in exts:
                continue
            if patterns and not any(pat in name for pat in patterns):
                continue
            try:
                if not entry.is_file():
                    continue
                candidates.append((entry.stat().st_mtime, Path(entry.path)))
            except OSError as e:  # fichero desaparecido entre scandir y stat
                logger.debug("Skipping %s: %s", entry.path, e)

    # nlargest equivale a sorted(..., reverse=True)[:n], sin ordenar toda la lista
    return [p for _, p in heapq.nlargest(n, candidates, key=lambda t: t[0])]