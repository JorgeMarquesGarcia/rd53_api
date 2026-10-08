from __future__ import annotations

from pathlib import Path

from src.chip.detector_geometry import rd53_id
from src.config.system_config import SystemConfig
from src.config.txt.txt_manager import SaveMode, TxtManager


ChipKey = tuple[int, int]
Pixel = tuple[int, int]

DEFAULT_SUFFIX = "_noise_masked"


def default_output_name(filename: str, output_suffix: str = DEFAULT_SUFFIX) -> str:
    """Nombre del TXT enmascarado; no repite el sufijo si ya lo lleva."""
    source = Path(filename)
    stem = source.stem
    if output_suffix and stem.endswith(output_suffix):
        stem = stem[:-len(output_suffix)]
    return f"{stem}{output_suffix}{source.suffix}"


class NoiseMaskCalibration:
    """Apply NoiseAnalysis pixels to the TXT mask for each chip.

    Las claves de chip son las de NoiseAnalysis: (hybrid_id, chip_lane).
    El XML y SystemConfig usan (hybrid_id, rd53_id), con rd53_id = lane + offset
    del hybrid (DETECTOR_LAYOUT); la conversión se hace aquí.
    """

    def __init__(self, noisy_pixels: dict[ChipKey, list[Pixel]]):
        self.noisy_pixels = noisy_pixels

    @staticmethod
    def hw_key(chip_key: ChipKey) -> ChipKey:
        """(hybrid_id, chip_lane) -> (hybrid_id, rd53_id) del XML."""
        hybrid_id, lane = chip_key
        return hybrid_id, rd53_id(hybrid_id, lane)

    @classmethod
    def config_file_for(cls, chip_key: ChipKey) -> str | None:
        """configFile de la configuración activa para un chip de NoiseAnalysis."""
        return SystemConfig.get_chip_config_file(*cls.hw_key(chip_key))

    def apply(
        self,
        overwrite: bool = False,
        update_xml: bool = False,
        output_suffix: str = DEFAULT_SUFFIX,
        output_names: dict[ChipKey, str] | None = None,
    ) -> dict[ChipKey, Path]:
        """Apply masks and return the output TXT path for each affected chip.

        By default, each mask is saved as a new ``*_noise_masked.txt`` file.
        Use ``output_suffix`` to select another suffix for the generated file.
        ``output_names`` gives an explicit file name per chip (relative to the
        TXT base dir), overriding the suffix. Set ``overwrite`` to replace the
        source TXT, and ``update_xml`` to point the configured XML file at the
        generated TXT files.
        """
        if not any(self.noisy_pixels.values()):
            return {}

        txt_base_dir = Path(SystemConfig.get_txt_base_dir())
        output_names = output_names or {}
        output_paths: dict[ChipKey, Path] = {}

        for chip_key, pixels in self.noisy_pixels.items():
            if not pixels:
                continue

            hw_hybrid, hw_rd53 = self.hw_key(chip_key)
            filename = SystemConfig.get_chip_config_file(hw_hybrid, hw_rd53)
            if not filename:
                raise ValueError(
                    f"No TXT config file is registered for chip {(hw_hybrid, hw_rd53)} "
                    f"(hybrid, rd53_id)."
                )

            manager = TxtManager(
                base_dir=str(txt_base_dir),
                chip_id=str(hw_rd53),
                filename=filename,
            )
            manager.load()
            manager.mask_pixels(pixels)

            if overwrite:
                manager.save(mode=SaveMode.OVERWRITE)
                output_paths[chip_key] = txt_base_dir / filename
            else:
                output_name = output_names.get(chip_key) or default_output_name(filename, output_suffix)
                manager.save(output_path=output_name, mode=SaveMode.NEWFILE)
                output_paths[chip_key] = txt_base_dir / output_name

        if update_xml and not overwrite and output_paths:
            xml_manager = SystemConfig.create_xml_manager(read_only=False)
            with xml_manager.batch():   # una sola escritura del XML
                for chip_key, output_path in output_paths.items():
                    xml_manager.set_chip_config_file(*self.hw_key(chip_key), output_path.name)
            # Mantener SystemConfig en sincronía con el XML
            config_files = SystemConfig.get_chip_config_files()
            config_files.update({self.hw_key(k): p.name for k, p in output_paths.items()})
            SystemConfig.set_chip_config_files(config_files)

        return output_paths
