"""Análisis base para datos ROOT del detector RD53.

Clase abstracta que proporciona funcionalidades comunes para todos los análisis de datos ROOT.

FILTRADO DE DATOS:
- Extrae automáticamente solo las columnas necesarias desde el RootManager
- Detecta los chips activos (hybrid_id, chip_lane) del XML y los guarda una sola vez
- Elimina eventos vacíos (sin hits en ningún plano)

COLUMNAS MANTENIDAS EN LOS DATOS FILTRADOS (REQUIRED_COLUMNS):
- event: identificador del evento
- FW_bx_counter: BX del trigger; entradas consecutivas forman una ventana de trigger
- FW_frame_event_hybrid_id / FW_frame_event_chip_lane: chip de cada frame
- RD53_frame_event_nhits: número de hits por plano [n_hits_plano0, n_hits_plano1, ...]
- RD53_hit_row: fila del pixel para cada hit
- RD53_hit_col: columna del pixel para cada hit
- RD53_hit_tot: energía (Time over Threshold) para cada hit

Para cargar un .root solo con estas ramas (más rápido y con menos memoria):
    SystemConfig.create_root_manager(path, branches=REQUIRED_COLUMNS)

ATRIBUTOS PRINCIPALES:
- self.active_chips: lista de tuplas (hybrid_id, chip_lane) de los chips activos
- self.raw_data: datos sin filtrar (solo columnas relevantes)
- self.clean_data: datos con eventos vacíos removidos

NOTA: Los hits dentro de cada evento están organizados secuencialmente por plano.
Por ejemplo, si RD53_frame_event_nhits = [2, 3, 0], los primeros 2 valores en
RD53_hit_row/col/tot pertenecen al plano 0, los siguientes 3 al plano 1, etc.
"""
from __future__ import annotations
from abc import ABC
import logging

import awkward as ak
import numpy as np

from src.config.root.root_manager import RootManager
from src.core.exceptions import AnalysisError

REQUIRED_COLUMNS: tuple[str, ...] = (
    'event',
    'FW_bx_counter',
    'FW_frame_event_hybrid_id',
    'FW_frame_event_chip_lane',
    'RD53_frame_event_nhits',
    'RD53_hit_row',
    'RD53_hit_col',
    'RD53_hit_tot',
)


def hits_per_chip(arrays) -> dict[tuple[int, int], int]:
    """Hits totales de cada chip (hybrid_id, chip_lane) en los arrays de un .root.

    Usa el orden de frames del primer evento, que es el mismo en todos.
    """
    if len(arrays) == 0:
        return {}
    chips = list(zip(ak.to_list(arrays.FW_frame_event_hybrid_id[0]),
                     ak.to_list(arrays.FW_frame_event_chip_lane[0])))
    totals = ak.to_list(ak.sum(arrays.RD53_frame_event_nhits, axis=0))
    return {chip: int(n) for chip, n in zip(chips, totals)}


def format_chips(chips) -> str:
    return ", ".join(f"H{h}·{c}" for h, c in chips)


def flat_hits(data, active_chips):
    """Hits de `data` aplanados en arrays numpy, en el orden del fichero.

    Devuelve (plane, rows, cols, tots): plane es el índice del frame (chip, en
    el orden de active_chips) de cada hit. Los hits de un evento van ordenados
    por frame, así que basta con repetir el índice de frame nhits veces.
    """
    nhits = data.RD53_frame_event_nhits
    plane = np.repeat(ak.to_numpy(ak.flatten(ak.local_index(nhits, axis=1))),
                      ak.to_numpy(ak.flatten(nhits)).astype(np.int64))
    rows = ak.to_numpy(ak.flatten(data.RD53_hit_row))
    cols = ak.to_numpy(ak.flatten(data.RD53_hit_col))
    tots = ak.to_numpy(ak.flatten(data.RD53_hit_tot))
    return plane, rows, cols, tots


def pixel_keys(plane, rows, cols) -> np.ndarray:
    """Clave entera única por (plano, fila, columna); filas y columnas caben en 16 bits."""
    return ((plane.astype(np.int64) << 32)
            | (rows.astype(np.int64) << 16)
            | cols.astype(np.int64))


def decode_pixel_keys(keys: np.ndarray):
    """Inversa de pixel_keys: devuelve (plane, rows, cols)."""
    keys = keys.astype(np.int64)
    return keys >> 32, (keys >> 16) & 0xFFFF, keys & 0xFFFF


class BaseAnalysis(ABC):
    """Common utilities shared by analysis classes based on ROOT data."""

    def __init__(self, root_manager: RootManager):
        # Logger del módulo de la subclase (src.analysis.analysis_hit, ...)
        self.logger = logging.getLogger(type(self).__module__)
        self.root_manager = root_manager
        self._validate()
        self.active_chips = None
        self.hybrid_ids = None
        self.chip_lanes = None
        self.raw_data = self._select_required_columns(self.root_manager.arrays)
        self.clean_data = self._remove_empty_events()
        self.logger.info("Active chips detected: %s", self.active_chips)
        self._log_data_summary()

    def _log_data_summary(self) -> None:
        """Resumen de los datos cargados: eventos, frames por evento y hits por chip."""
        nhits = self.raw_data.RD53_frame_event_nhits
        frames = np.unique(ak.to_numpy(ak.num(nhits, axis=1))).tolist()
        self.logger.info("Events in file: %d (frames per event: %s)", len(self.raw_data), frames)
        self.hits_per_chip = hits_per_chip(self.raw_data)
        self.logger.info("Hits per chip: %s", ", ".join(
            f"H{h}·{c}: {n}" for (h, c), n in self.hits_per_chip.items()))
        self.logger.info("Events with hits: %d of %d (%d hits in total)",
                         len(self.clean_data), len(self.raw_data), int(ak.sum(nhits)))
        empty = [chip for chip, n in self.hits_per_chip.items() if n == 0]
        if empty:
            self.logger.warning("No hits in %s in the whole file: check that these chips "
                                "are powered and enabled.", format_chips(empty))

    def _validate(self) -> None:
        if not self.root_manager.is_loaded():
            raise AnalysisError("RootManager no tiene datos cargados. Llama a load() primero.")

        if self.root_manager.arrays is None:
            raise AnalysisError("RootManager no contiene arrays válidos.")

        self.logger.info("RootManager validado correctamente")

    def _remove_empty_events(self, data=None):
        if data is None:
            data = self.raw_data
        return data[ak.sum(data.RD53_frame_event_nhits, axis=1) > 0]

    def _select_required_columns(self, data):
        """Filtra los datos para mantener solo las columnas necesarias para el análisis.

        Extrae los chips activos (una sola vez) y los guarda en self.active_chips.
        Retorna datos con las columnas de REQUIRED_COLUMNS.
        """
        # Extraer los chips únicos (hybrid_id, chip_lane)
        self.hybrid_ids = data.FW_frame_event_hybrid_id[0]
        self.chip_lanes = data.FW_frame_event_chip_lane[0]
        self.active_chips = list(dict.fromkeys(zip(ak.to_list(self.hybrid_ids),
                                                   ak.to_list(self.chip_lanes))))
        return data[list(REQUIRED_COLUMNS)]
