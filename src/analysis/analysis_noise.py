from __future__ import annotations
import logging
import awkward as ak
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis
from src.analysis.analysis_hit import TOT_THRESHOLD
from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS

class NoiseAnalysis(BaseAnalysis):
    """Detecta píxeles ruidosos en un .root.

    Evento ruidoso: algún chip con más de 1 hit y TODOS los hits del evento
    con ToT < tot_threshold (el mismo umbral que usa HitAnalysis para
    quedarse con los eventos buenos).

    Atributos tras construir:
        noisy_events:       eventos ruidosos (awkward, con toda la información).
        noisy_pixel_counts: {(hybrid, lane): {(row, col): nº de eventos ruidosos}}.
        noisy_pixels:       {(hybrid, lane): [(row, col), ...]} (sin repetir).
        stats:              n_noisy_pixels, total_pixels, noise_percentage.
    """

    def __init__(self, root_manager: RootManager, tot_threshold: int = TOT_THRESHOLD):
        super().__init__(root_manager)
        self.logger = logging.getLogger(__name__)
        self.tot_threshold = tot_threshold

        self.noisy_events = self.extract_noisy_events()
        self.noisy_pixel_counts = self._count_pixels(self.noisy_events)
        self.noisy_pixels = {k: list(v) for k, v in self.noisy_pixel_counts.items()}
        self.stats = self._noise_stats()



    
    def extract_noisy_events(self):
        noisy_events = self._noise_filter()
        self.logger.info(f"Filtro de ruido aplicado: {len(noisy_events)} eventos ruidosos detectados")
        return noisy_events
    
    
    def _multiple_hits(self, data=None):
        if data is None:
            data = self.clean_data
        return data[ak.any(data.RD53_frame_event_nhits > 1, axis=1)] #puede que me interese quitar esto, por los que llegan cruzados
    
    
    def _noise_filter(self, data=None):
        if data is None:
            data = self.clean_data
        suspects = self._multiple_hits(data)
        return suspects[ak.all(suspects.RD53_hit_tot < self.tot_threshold, axis=1)]

    def _count_pixels(self, noisy_events) -> dict[tuple[int, int], dict[tuple[int, int], int]]:
        pixels_by_chip: dict[tuple[int, int], dict[tuple[int, int], int]] = {}

        for event in noisy_events:
            n_hits_by_chip = ak.to_list(event.RD53_frame_event_nhits)
            rows = ak.to_list(event.RD53_hit_row)
            cols = ak.to_list(event.RD53_hit_col)
            hit_offset = 0

            for chip_key, n_hits in zip(self.active_chips, n_hits_by_chip):
                n_hits = int(n_hits)
                chip_pixels = pixels_by_chip.setdefault(chip_key, {})
                for row, col in zip(rows[hit_offset:hit_offset + n_hits],
                                    cols[hit_offset:hit_offset + n_hits]):
                    pixel = (int(row), int(col))
                    chip_pixels[pixel] = chip_pixels.get(pixel, 0) + 1
                hit_offset += n_hits

        return pixels_by_chip

    def _noise_stats(self) -> dict[str, float | int]:
        n_noisy_pixels = sum(
            len(pixels) for pixels in self.noisy_pixels.values()
        )
        total_pixels = SENSOR_ROWS * SENSOR_COLS * len(self.active_chips)
        noise_percentage = (
            n_noisy_pixels / total_pixels * 100
            if total_pixels
            else 0.0
        )

        return {
            "n_noisy_pixels": n_noisy_pixels,
            "total_pixels": total_pixels,
            "noise_percentage": noise_percentage,
        }