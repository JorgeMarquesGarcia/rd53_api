from __future__ import annotations

from pathlib import Path

from src.config.system_config import SystemConfig
from src.config.txt.txt_manager import SaveMode, TxtManager


ChipKey = tuple[int, int]
Pixel = tuple[int, int]


class NoiseMaskCalibration:
	"""Apply NoiseAnalysis pixels to the TXT mask for each chip."""

	def __init__(self, noisy_pixels: dict[ChipKey, list[Pixel]]):
		self.noisy_pixels = noisy_pixels

	def apply(
		self,
		overwrite: bool = False,
		update_xml: bool = False,
		output_suffix: str = "_noise_masked",
	) -> dict[ChipKey, Path]:
		"""Apply masks and return the output TXT path for each affected chip.

		By default, each mask is saved as a new ``*_noise_masked.txt`` file.
		Use ``output_suffix`` to select another suffix for the generated file.
		Set ``overwrite`` to replace the source TXT, and ``update_xml`` to
		point the configured XML file at the generated TXT files.
		"""
		if not any(self.noisy_pixels.values()):
			return {}

		txt_base_dir = SystemConfig.get_txt_base_dir()
		output_paths: dict[ChipKey, Path] = {}

		for chip_key, pixels in self.noisy_pixels.items():
			if not pixels:
				continue

			filename = SystemConfig.get_chip_config_file(*chip_key)
			if not filename:
				raise ValueError(
					f"No TXT config file is registered for chip {chip_key}."
				)

			manager = TxtManager(
				base_dir=str(txt_base_dir),
				chip_id=str(chip_key[1]),
				filename=filename,
			)
			manager.load()
			manager.mask_pixels(pixels)

			source_path = Path(txt_base_dir) / filename
			if overwrite:
				manager.save(mode=SaveMode.OVERWRITE)
				output_paths[chip_key] = source_path
			else:
				output_name = f"{source_path.stem}{output_suffix}{source_path.suffix}"
				manager.save(output_path=output_name, mode=SaveMode.NEWFILE)
				output_paths[chip_key] = Path(txt_base_dir) / output_name

		if update_xml and not overwrite and output_paths:
			xml_manager = SystemConfig.create_xml_manager(read_only=False)
			for chip_key, output_path in output_paths.items():
				xml_manager.set_chip_config_file(
					*chip_key,
					output_path.name,
				)

		return output_paths
