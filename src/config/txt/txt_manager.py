from __future__ import annotations
from pathlib import Path
import logging
from enum import Enum, auto
from datetime import datetime

from src.core.decorators import ensure_loaded
from src.core.mask import Mask
from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS
from src.core import exceptions
from src.config.base_config_manager import BaseConfigManager

# Prefijos de las líneas de la sección de máscara del TXT
_COL_FIRST = 'COL                  000'
_COL_PREFIX = 'COL                  '
_MASK_PREFIXES = (
    ('ENABLE ', 'enable'),   # startswith: no confundir con registros que contienen ENABLE
    ('HITBUS ', 'hitBUS'),
    ('INJEN  ', 'injEN'),
    ('TDAC   ', 'TDAC'),
)
MAX_INVALID_PIXELS = 10   # píxeles fuera de rango tolerados por llamada a mask_pixels()


class SaveMode(Enum):
    TIMESTAMP = auto()
    OVERWRITE = auto()
    NEWFILE   = auto()


class TxtManager(BaseConfigManager):
    def __init__(self, base_dir: str | Path, chip_id: str, filename: str | None = None):
        self._base_dir = Path(base_dir)
        self._txt_name = filename or f"CMSIT_RD53A_{chip_id}.txt"
        self._filepath = self._build_path(self._txt_name)
        self.logger = logging.getLogger(__name__)
        self._loaded = False

        # Internal data structures
        self.registers_lines: list[str] = []
        self._mask: Mask | None = None
        self._mask_modified = False
        self._invalid_pixel_count = 0

        # Dimensions
        self._nrows = SENSOR_ROWS
        self._ncols = SENSOR_COLS

    def load(self, path: str | Path | None = None) -> None:
        """Load the TXT file and read its contents into internal structures."""
        if path is not None:
            self._filepath = Path(path)
        if not self._filepath.exists():
            raise exceptions.TxtFileNotFoundError(str(self._filepath))

        self._read_cfg_file()
        self._mask_modified = False
        self._loaded = True
        self.logger.info("TXT file '%s' loaded successfully.", self._filepath)

    @ensure_loaded
    def mask_pixels(self, noisy_pixels) -> None:
        if self._mask_modified:
            self.logger.warning("Mask has been modified since last load; overwriting previous changes.")
        self._invalid_pixel_count = 0
        for row, col in self._extract_pixels(noisy_pixels):
            self._disable_pixel(row, col)
        self._mask_modified = True

    @ensure_loaded
    def save(self, output_path: str | Path | None = None, mode: SaveMode = SaveMode.TIMESTAMP) -> None:
        path = self._resolve_save_path(mode, output_path)
        self._write_cfg_file(path)
        self.logger.info("TXT file saved using %s mode: '%s'.", mode.name, path)
        self._mask_modified = False

    def _read_cfg_file(self):
        self.registers_lines = []
        self._mask = mask = Mask()
        found_mask = False

        with open(self._filepath, encoding="utf-8") as fin:
            for line in fin:
                if line.startswith(_COL_FIRST):
                    found_mask = True
                    continue
                if found_mask and line.startswith(_COL_PREFIX):
                    continue
                for prefix, attr in _MASK_PREFIXES:
                    if line.startswith(prefix):
                        values = line[len(prefix):].split(',')
                        getattr(mask, attr).append([v.strip() for v in values])
                        break
                else:
                    # Solo las líneas anteriores a la sección de máscara son registros
                    if not found_mask:
                        self.registers_lines.append(line)

    @ensure_loaded
    def _disable_pixel(self, row: int, col: int) -> None:
        if not self._valid_pixel(row, col):
            self._invalid_pixel_count += 1
            self.logger.error("Invalid pixel coordinates: row=%d, col=%d", row, col)
            if self._invalid_pixel_count > MAX_INVALID_PIXELS:
                raise exceptions.TxtInvalidPixelError(row, col)
            return
        self._mask.enable[col][row] = "0"

    @ensure_loaded
    def _enable_pixel(self, row: int, col: int) -> None:
        if not self._valid_pixel(row, col):
            raise exceptions.TxtInvalidPixelError(row, col)
        self._mask.enable[col][row] = "1"

    def _valid_pixel(self, row: int, col: int) -> bool:
        return 0 <= row < self._nrows and 0 <= col < self._ncols

    @staticmethod
    def _extract_pixels(noisy_pixels) -> list[tuple[int, int]]:
        try:
            return [(int(pixel[0]), int(pixel[1])) for pixel in noisy_pixels]
        except Exception as e:
            raise exceptions.TxtInvalidNoisyPixelError(str(e)) from e

    def _write_cfg_file(self, output_path: str | Path | None = None) -> None:
        path = Path(output_path) if output_path else self._filepath
        mask = self._mask

        chunks = list(self.registers_lines)
        for col in range(len(mask.enable)):
            chunks.append(
                f"COL                  {col:03}\n"
                f"ENABLE {','.join(mask.enable[col])}\n"
                f"HITBUS {','.join(mask.hitBUS[col])}\n"
                f"INJEN  {','.join(mask.injEN[col])}\n"
                f"TDAC   {','.join(mask.TDAC[col])}\n\n"
            )

        with path.open("w", encoding="utf-8") as fout:
            fout.write("".join(chunks))
        self.logger.info("TXT file saved to '%s'.", path)

    def _build_path(self, txt_name: str) -> Path:
        return self._base_dir / txt_name

    def is_loaded(self) -> bool:
        """Return True if TXT file is currently loaded."""
        return self._loaded

    def is_dirty(self) -> bool:
        """Return True if mask has been modified."""
        return self._mask_modified

    def get_path(self) -> Path | None:
        """Return the path of the TXT file."""
        return self._filepath

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise exceptions.TxtNotLoadedError()

    def _resolve_save_path(self, mode: SaveMode, name: str | Path | None) -> Path:
        if mode is SaveMode.NEWFILE:
            if name is None:
                raise exceptions.TxtSaveNameRequiredError()
            return self._base_dir / Path(name)
        if mode is SaveMode.OVERWRITE:
            return self._filepath
        if mode is SaveMode.TIMESTAMP:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{self._filepath.stem}_{timestamp}{self._filepath.suffix}"
            return self._base_dir / new_name
        raise ValueError(f"Unsupported save mode: {mode}")
