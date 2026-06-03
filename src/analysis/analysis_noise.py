from __future__ import annotations
import logging
import awkward as ak
from rd53_api.config.root.root_manager import RootManager
from rd53_api.analysis.analysis_base import BaseAnalysis

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
        """List of (row, col) tuples of noisy pixels"""
        self.noisy_pixels = self._extract_pixels(self.noisy_events) 



    
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
        rows = ak.flatten(noisy_events.RD53_hit_row)
        cols = ak.flatten(noisy_events.RD53_hit_col)
        return list(zip(ak.to_list(rows), ak.to_list(cols)))