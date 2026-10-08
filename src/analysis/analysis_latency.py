"""Análisis de un scan de latencia.

Posible mejora futura: indicar cuántos hits se han salido del centro de la
ventana, porque las partículas muy energéticas caen en varios BC.
"""
from __future__ import annotations
from typing import Optional
import numpy as np
import awkward as ak
from src.core.exceptions import LAErrorEmptyData, LAnRootError
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis


class LatencyAnalysis(BaseAnalysis):
    def __init__(self, root_manager: Optional[RootManager] = None, ntrig: int = 10,
                 chip_latency: Optional[dict[str, int]] = None, new_Ntrig: Optional[int] = None):
        """Calcula la posición de los hits dentro de la ventana de nTRIGxEvent BX
        y la latencia que los centra.

        Args:
            root_manager: RootManager con los datos cargados (obligatorio).
            ntrig: nTRIGxEvent con el que se tomó el scan.
            chip_latency: {chip: latencia actual}; se devuelve corregida en
                self.chip_latency.
            new_Ntrig: si se indica, la latencia se recalcula para centrar los
                hits en una ventana de new_Ntrig BX en lugar de ntrig.

        Raises:
            LAnRootError: si no se pasa root_manager.
            LAErrorEmptyData: si el fichero no tiene ningún evento con hits.
        """
        if root_manager is None:
            raise LAnRootError("RootManager instance is required to initialize LatencyAnalysis.")

        self.chip_latency = chip_latency if chip_latency is not None else {}
        self.ntrig = int(ntrig)  # Asegurar que sea int, no string

        # BaseAnalysis carga los datos y calcula clean_data (eventos con hits)
        super().__init__(root_manager=root_manager)

        self._analyzed = False
        self.positions_in_group = self._position_in_group()
        self.group_index = self._group_index()
        self.statistics = self._statistics()
        if not new_Ntrig:
            self.chip_latency = self._mean_ntrig()
        else:
            self.chip_latency = self._custom_ntrig(new_Ntrig)

    def _remove_empty_events(self, data=None):
        clean = super()._remove_empty_events(data)
        if len(clean) == 0:
            raise LAErrorEmptyData("No events with hits in the ROOT file: cannot compute the latency.")
        return clean

    def _position_in_group(self, data=None):
        if data is None:
            data = self.clean_data
        # int64: las reducciones de awkward no tienen kernel para uint32 en todas las plataformas
        events = ak.to_numpy(data.event).astype(np.int64)
        return np.mod(events, self.ntrig)

    def _group_index(self, data=None):
        if data is None:
            data = self.clean_data
        events = ak.to_numpy(data.event).astype(np.int64)
        return np.floor_divide(events, self.ntrig)

    def _statistics(self):
        self._analyzed = True
        positions = self.positions_in_group
        mean = float(np.mean(positions))
        sigma = float(np.std(positions))
        min_pos = int(np.min(positions))
        max_pos = int(np.max(positions))
        statistics = {
            "mean": mean,
            "std": sigma,
            "min_pos": min_pos,
            "max_pos": max_pos
        }
        self.logger.info("Latency statistics calculated: mean=%s, std=%s, min=%s, max=%s",
                         mean, sigma, min_pos, max_pos)
        return statistics

    def _mean_ntrig(self):
        """Calcula nuevos valores de latency para centrar hits en ntrig/2."""
        adjustment = self.statistics["mean"] - self.ntrig // 2

        latency_new = {
            chip_id: round(latency_old - adjustment)
            for chip_id, latency_old in self.chip_latency.items()
        }

        self.logger.info("Latency adjustment calculated: offset=%s", adjustment)
        return latency_new

    def _custom_ntrig(self, ntrig_new: int):
        position_mean = self.statistics["mean"]

        latency_new = {
            chip_id: round(latency_old + position_mean - ntrig_new // 2)
            for chip_id, latency_old in self.chip_latency.items()
        }

        self.logger.info("Latency adjusted for ntrig_new=%s: position_mean=%s", ntrig_new, position_mean)
        return latency_new
