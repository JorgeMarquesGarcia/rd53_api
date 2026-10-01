from __future__ import annotations
import logging
import awkward as ak
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis

SENSOR_ROWS = 192
SENSOR_COLS = 400

class NoiseAnalysis(BaseAnalysis):
    def __init__(self, root_manager: RootManager):
        """
        Docstring for __init__
        
        :param self: Description
        :param root_manager: Description
        :type root_manager: RootManager | None
        """
        self.logger = logging.getLogger(__name__)
        super().__init__(root_manager)

        self._analyzed = False
        self.noisy_events = None
        self.noisy_pixels = None
        
  
        """Complete Noise Events (with all information per hit)"""
        self.noisy_events = self.extract_noisy_events()
        """Noisy pixels grouped by (hybrid_id, chip_lane)."""
        self.noisy_pixels = self._extract_pixels(self.noisy_events) 
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
        return suspects[ak.all(suspects.RD53_hit_tot <= 3, axis=1)]
    
    def _extract_pixels(self, noisy_events):
        pixels_by_chip: dict[tuple[int, int], dict[tuple[int, int], None]] = {}

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
                    chip_pixels.setdefault((int(row), int(col)), None)
                hit_offset += n_hits

        return {k: list(v) for k, v in pixels_by_chip.items()}

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