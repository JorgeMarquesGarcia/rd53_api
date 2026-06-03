from __future__ import annotations
from pathlib import Path
import logging
from src.core.decorators import ensure_loaded
from src.core.mask import Mask, NROWS, NCOLS
from enum import Enum, auto
from datetime import datetime

from src.core import exceptions
from src.config.base_config_manager import BaseConfigManager

class SaveMode(Enum):
    TIMESTAMP = auto()
    OVERWRITE = auto()
    NEWFILE   = auto()

class TxtManager(BaseConfigManager):
    def __init__(self, base_dir: str, chip_id: str):
        self._base_dir = Path(base_dir)
        self._txt_name = f"CMSIT_RD53A_{chip_id}.txt" #Remember to save chip_id as F7, H4, F5. {Chip_identifier}{Position_identifier}
        self._filepath = self._build_path(self._txt_name)
        self.logger = logging.getLogger(__name__)
        self._loaded = False

        #Internal data structures
        self.registers_lines: list[str] = []
        self._mask = None
        self._mask_modified = False
        self._invalid_pixel_count = 0

        #Dimensions
        self._nrows = NROWS
        self._ncols = NCOLS


    def load(self) -> None:
        """Load the TXT file and read its contents into internal structures."""
        if not self._filepath.exists():
            raise exceptions.TxtFileNotFoundError(str(self._filepath))
        
        self._read_cfg_file()
        self._loaded = True
        self.logger.info(f"TXT file '{self._filepath}' loaded successfully.")

        
    @ensure_loaded
    def mask_pixels(self, noisy_pixels) -> None:
        if self._mask_modified is True:
            self.logger.warning("Mask has been modified since last load; overwriting previous changes.")
        pixel_list = self._extract_pixels(noisy_pixels)
        for row, col in pixel_list:
            self._disable_pixel(row, col)
        self._mask_modified = True
        
    
    @ensure_loaded
    def save(self, output_path: str| Path | None = None, mode: SaveMode = SaveMode.TIMESTAMP) -> None:
        path = self._resolve_save_path(mode, output_path)
        self._write_cfg_file(path)
        self.logger.info("TXT file saved using %s mode: '%s'.", mode.name, path)
        self._mask_modified = False

    def _read_cfg_file(self):
        self.registers_lines.clear()
        self._mask = Mask()
        with open(self._filepath) as fin:
            lines     = fin.readlines()
            col       = 0
            foundMask = False

            for it, line in enumerate(lines):
                if line.startswith('COL                  000'):
                    col += 1
                    foundMask = True
                elif foundMask and line.startswith('COL                  '):
                    col += 1
                elif line.startswith('ENABLE '):  ## startswith must be used to not take some registers with ENABLE
                    lines[it] = lines[it].replace('ENABLE ', '')
                    enableLine = [ele.strip() for ele in lines[it].split(',')]
                    self._mask.enable.append(enableLine)
                elif line.startswith('HITBUS '):
                    lines[it] = lines[it].replace('HITBUS ', '')
                    hitBUSLine = [ele.strip() for ele in lines[it].split(',')]
                    self._mask.hitBUS.append(hitBUSLine)
                elif line.startswith('INJEN  '):
                    lines[it] = lines[it].replace('INJEN  ', '')
                    injENLine = [ele.strip() for ele in lines[it].split(',')]
                    self._mask.injEN.append(injENLine)
                elif line.startswith('TDAC   '):
                    lines[it] = lines[it].replace('TDAC   ', '')
                    TDACLine = [ele.strip() for ele in lines[it].split(',')]
                    self._mask.TDAC.append(TDACLine)
                else:
                    # Only append lines to registers before finding the pixel mask section
                    if not foundMask:
                        self.registers_lines.append(line)

    
    @ensure_loaded
    def _disable_pixel(self, row: int, col: int) -> None: 
        if not self._valid_pixel(row,col):
            self._invalid_pixel_count += 1
            self.logger.error("Invalid pixel coordinates: row=%d, col=%d", row, col)
            if self._invalid_pixel_count > 10:
                raise exceptions.TxtInvalidPixelError(row, col)
            return
         
        self._mask.enable[col][row] = "0"
    
    @ensure_loaded
    def _enable_pixel(self, row: int, col: int) -> None:
        if not self._valid_pixel(row,col):
            raise exceptions.TxtInvalidPixelError(row, col)
        
        self._mask.enable[col][row] = "1"

    def _valid_pixel(self, row: int, col: int) -> bool:
        return 0 <= row < self._nrows and 0 <= col < self._ncols


    def _extract_pixels(self, noisy_pixels) -> list[tuple[int, int]]:
        pixel_list = []
        try:
            for pixel in noisy_pixels:
                row, col = int(pixel[0]), int(pixel[1])
                pixel_list.append((row, col))
        except Exception:
                raise exceptions.TxtInvalidNoisyPixelError()

        return pixel_list
    



    def _write_cfg_file(self, output_path: str | Path | None = None) -> None:
        path = Path(output_path) if output_path else self._filepath

        with path.open("w", encoding="utf-8") as fout:
            for line in self.registers_lines:
                fout.write(line)
            
            for col in range(len(self._mask.enable)):
                fout.write(f"COL                  {col:03}\n")
                fout.write("ENABLE " + ",".join(self._mask.enable[col]) + "\n")
                fout.write("HITBUS " + ",".join(self._mask.hitBUS[col]) + "\n")
                fout.write("INJEN  " + ",".join(self._mask.injEN[col]) + "\n")
                fout.write("TDAC   " + ",".join(self._mask.TDAC[col]) + "\n\n")
        
        self.logger.info(f"TXT file saved to '{path}'.")
    
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
            return self._base_dir / Path(new_name)
