from __future__ import annotations
from pathlib import Path

_run_number_path: Path | None = None


def configure(path: str | Path) -> None:
    """Configura la ruta al fichero RunNumber.txt. Llamar una vez al inicio."""
    global _run_number_path
    _run_number_path = Path(path)


def _read_run_number() -> int:
    """Lee el run number del fichero."""
    if _run_number_path is None:
        raise RuntimeError("RunNumberManager no configurado. Llama a configure(path) primero.")
    if not _run_number_path.exists():
        raise FileNotFoundError(f"No se encuentra el fichero: {_run_number_path}")
    
    with open(_run_number_path, "r") as f:
        return int(f.read().strip())


def get() -> int:
    """Obtiene el run number actual."""
    return _read_run_number()


def get_formatted(width: int = 6) -> str:
    """Obtiene el run number con padding de ceros (ej: '000572')."""
    return str(_read_run_number()).zfill(width)


def __getattr__(name: str):
    """Permite acceder a RUN_NUMBER como variable global que lee el fichero."""
    if name == "RUN_NUMBER":
        return _read_run_number()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")