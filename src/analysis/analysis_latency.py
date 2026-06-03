from __future__ import annotations
import logging
from typing import Union, Optional
import numpy as np
import awkward as ak
from src.core.exceptions import LAnRootArraysError, LAErrorEmptyData, LAnRootError
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis
"""Podría ser interesante para el futuro, añadir alguna forma para que me diga cuantos hits se han salido del centro, porque las particulas muy energéticas caen en varios BC"""
class LatencyAnalysis(BaseAnalysis):
    def __init__(self, root_manager: Optional[RootManager] = None, ntrig: int = 10, chip_latency: Optional[dict[str, int]] = None, new_Ntrig: Optional[int] = None):
        """_summary_

        Args:
            root_manager (RootManager | None, optional): _description_. Defaults to None.
            ntrig (int, optional): _description_. Defaults to 10.
            chip_latency (dict[str, int] | None, optional): _description_. Defaults to None.
            new_Ntrig (int | None, optional): _description_. Defaults to None.

        Raises:
            LAnRootError: _description_
        """
        self.logger = logging.getLogger(__name__)
        self.root_manager = root_manager
        self.chip_latency = chip_latency if chip_latency is not None else {}
        self.ntrig = int(ntrig)  # Asegurar que sea int, no string

        if self.root_manager: 
            super().__init__(root_manager=self.root_manager)
        else:
            raise LAnRootError("RootManager instance is required to initialize LatencyAnalysis.")

        self._analyzed = False
        self.clean_data = None
        self.positions_in_group = None
        self.group_index = None
        self.statistics = None

        self.clean_data = self._remove_empty_events()

        self.positions_in_group = self._position_in_group()
        self.group_index = self._group_index()
        self.statistics = self._statistics()
        if not new_Ntrig:
            self.chip_latency = self._mean_ntrig()
        else:
            self.chip_latency = self._custom_ntrig(new_Ntrig)


    def _remove_empty_events(self, data=None):
        self._validate_root_manager(LAnRootError, LAnRootArraysError)
        return super()._remove_empty_events(LAErrorEmptyData, data=data)
    
    def _position_in_group(self, data=None):
        if data is None:
            data = self.clean_data
        # Convertir a numpy array y forzar tipo int para operación módulo
        #events = ak.to_numpy(data.event).astype(np.int64)
        #position = np.mod(events, self.ntrig)
        position = data.event % self.ntrig
        return position
   
    def _group_index(self, data=None):
        if data is None:
            data = self.clean_data
        # Convertir a numpy array y forzar tipo int para división entera
        events = ak.to_numpy(data.event).astype(np.int64)
        group_index = np.floor_divide(events, self.ntrig)

        return group_index

    def _statistics(self):
        self._analyzed = True
        mean = ak.mean(self.positions_in_group)
        sigma = ak.std(self.positions_in_group)
        min_pos = ak.min(self.positions_in_group)
        max_pos = ak.max(self.positions_in_group)
        statistics = {
            "mean": mean,
            "std": sigma,
            "min_pos": min_pos,
            "max_pos": max_pos
        }
        self.logger.info(f"Latency statistics calculated: mean={mean}, std={sigma}, min={min_pos}, max={max_pos}")
        return statistics
    
    def _mean_ntrig(self):
        """Calcula nuevos valores de latency para centrar hits en ntrig/2."""
        adjustment = self.statistics["mean"] - self.ntrig // 2
        
        latency_new = {
            chip_id: round(latency_old - adjustment)
            for chip_id, latency_old in self.chip_latency.items()
        }
        
        self.logger.info(f"Latency adjustment calculated: offset={adjustment}")
        return latency_new
    
    def _custom_ntrig(self, ntrig_new: int):

        position_mean = self.statistics["mean"]
        
        latency_new = {
            chip_id: round(latency_old + position_mean - ntrig_new // 2)
            for chip_id, latency_old in self.chip_latency.items()
        }
        
        self.logger.info(f"Latency adjusted for ntrig_new={ntrig_new}: position_mean={position_mean}")
        return latency_new