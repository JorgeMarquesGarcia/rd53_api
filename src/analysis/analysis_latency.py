"""Análisis de un scan de latencia.

Posición de los hits dentro de la ventana de nTRIGxEvent BX que lee cada
trigger y LATENCY_CONFIG que los centra. Bajar LATENCY_CONFIG en 1 adelanta
los hits 1 BX en la ventana (comprobado con los runs 384 → 385: 33 → 31 lleva
los hits del BX4 al BX2).

Posible mejora futura: indicar cuántos hits se han salido del centro de la
ventana, porque las partículas muy energéticas caen en varios BC.
"""
from __future__ import annotations
from collections import Counter
from typing import Optional
import numpy as np
import awkward as ak
from src.core.exceptions import LAErrorEmptyData, LAnRootError
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis, trigger_windows


def window_sizes(arrays) -> Counter:
    """{tamaño en BX: nº de ventanas} de las ventanas de trigger de un .root."""
    window, first = trigger_windows(ak.to_numpy(arrays.FW_bx_counter))
    return Counter(np.diff(np.append(first, len(window))).tolist())


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
                hits en una ventana de new_Ntrig BX en lugar de ntrig (p. ej. la
                de las adquisiciones, si el run se tomó con otro nTRIGxEvent).

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
        self._check_windows()
        self.positions_in_group = self._position_in_group()
        self.group_index = self._group_index()
        self.statistics = self._statistics()
        # Desglose por chip: {(hybrid, lane): posición de cada hit} y sus estadísticas
        self.chip_positions = self._chip_positions()
        self.chip_statistics = self._chip_statistics()
        # Posición que se centra al proponer la latencia (ver _reference_position)
        self.reference_chip, self.reference_position = self._reference_position()
        if not new_Ntrig:
            self.chip_latency = self._mean_ntrig()
        else:
            self.chip_latency = self._custom_ntrig(new_Ntrig)

    def _check_windows(self) -> None:
        """Avisa si las ventanas de los datos no miden ntrig BX."""
        sizes = window_sizes(self.raw_data)
        self.logger.info("Trigger windows: %s", ", ".join(
            f"{n} of {size} BX" for size, n in sorted(sizes.items())))
        if set(sizes) != {self.ntrig}:
            self.logger.warning("Trigger windows in the data are not of nTRIGxEvent = %d BX: "
                                "the positions in the window are not reliable", self.ntrig)

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

    def _chip_positions(self) -> dict[tuple[int, int], np.ndarray]:
        """Posición en la ventana de cada hit, por chip (orden de active_chips)."""
        nhits = ak.to_numpy(self.clean_data.RD53_frame_event_nhits).astype(np.int64)  # (entradas, chips)
        return {chip: np.repeat(self.positions_in_group, nhits[:, i])
                for i, chip in enumerate(self.active_chips)}

    def _chip_statistics(self) -> dict[tuple[int, int], dict]:
        """Por chip: nº de hits y mediana, media, sigma, mínimo y máximo de su posición."""
        statistics = {}
        for chip, positions in self.chip_positions.items():
            if len(positions) == 0:
                statistics[chip] = {"n_hits": 0, "median": None, "mean": None, "std": None,
                                    "min_pos": None, "max_pos": None}
                continue
            median = float(np.median(positions))
            statistics[chip] = {
                "n_hits": int(len(positions)),
                "median": median,
                "mean": float(np.mean(positions)),
                "std": float(np.std(positions)),
                "min_pos": int(np.min(positions)),
                "max_pos": int(np.max(positions)),
            }
            self.logger.info("H%d·%d: %d hits, median position %.1f, mean %.2f, std %.2f, range %d-%d",
                             chip[0], chip[1], len(positions), median, statistics[chip]["mean"],
                             statistics[chip]["std"], statistics[chip]["min_pos"],
                             statistics[chip]["max_pos"])
        return statistics

    def _reference_position(self) -> tuple[tuple[int, int] | None, float]:
        """(chip, posición) que se lleva al centro de la ventana al proponer la latencia.

        La mediana de los hits del plano de trigger (plano 0, el mismo que usa
        HitAnalysis): con el trigger por HitOr sus hits caen siempre en el mismo
        BX, mientras que el ruido de los demás planos, repartido por toda la
        ventana, arrastra la media de todas las entradas hacia el centro
        (Run000385: BX3.0 con todas las entradas, BX2 en el plano 0). Sin hits
        en el plano 0, la mediana de todas las entradas con hits.
        """
        trigger_chip = self.active_chips[0]
        if self.chip_statistics[trigger_chip]["n_hits"]:
            position = self.chip_statistics[trigger_chip]["median"]
            self.logger.info("Reference: trigger plane H%d·%d, median position %.1f",
                             trigger_chip[0], trigger_chip[1], position)
            return trigger_chip, position
        position = float(np.median(self.positions_in_group))
        self.logger.warning("No hits in the trigger plane H%d·%d: reference = median position "
                            "%.1f of all entries with hits", trigger_chip[0], trigger_chip[1], position)
        return None, position

    def _mean_ntrig(self):
        """Calcula nuevos valores de latency para centrar hits en ntrig/2.

        Centra reference_position (mediana del plano de trigger), no la media de
        todas las entradas, que el ruido de los otros planos desplaza.
        """
        adjustment = self.reference_position - self.ntrig // 2

        latency_new = {
            chip_id: round(latency_old - adjustment)
            for chip_id, latency_old in self.chip_latency.items()
        }

        self.logger.info("Latency adjustment calculated: offset=%s", adjustment)
        return latency_new

    def _custom_ntrig(self, ntrig_new: int):
        """Latencia que centra reference_position en una ventana de ntrig_new BX.

        La posición de un hit en la ventana es LATENCY_CONFIG menos un retardo
        fijo, sea cual sea nTRIGxEvent (Run000384 con 33 y 5 BX: BX4; Run000385
        con 31 y 10 BX: BX2), así que para llevarlo a ntrig_new // 2 hay que
        restar a la latencia (posición - ntrig_new // 2).
        """
        adjustment = self.reference_position - ntrig_new // 2

        latency_new = {
            chip_id: round(latency_old - adjustment)
            for chip_id, latency_old in self.chip_latency.items()
        }

        self.logger.info("Latency adjusted for ntrig_new=%s: reference position=%s, offset=%s",
                         ntrig_new, self.reference_position, adjustment)
        return latency_new
