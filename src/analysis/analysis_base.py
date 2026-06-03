from __future__ import annotations
from abc import ABC
import logging
import awkward as ak
from rd53_api.config.root.root_manager import RootManager
from rd53_api.core.exceptions import AnalysisError


"""Análisis base para datos ROOT del detector RD53.

Clase abstracta que proporciona funcionalidades comunes para todos los análisis de datos ROOT.

FILTRADO DE DATOS:
- Extrae automáticamente solo las columnas necesarias desde el RootManager
- Detecta los chips activos (hybrid_id, chip_lane) del XML y los guarda una sola vez
- Elimina eventos vacíos (sin hits en ningún plano)

COLUMNAS MANTENIDAS EN LOS DATOS FILTRADOS:
- event: identificador del evento
- RD53_frame_event_nhits: número de hits por plano [n_hits_plano0, n_hits_plano1, ...]
- RD53_hit_row: fila del pixel para cada hit
- RD53_hit_col: columna del pixel para cada hit
- RD53_hit_tot: energía (Time over Threshold) para cada hit

ATRIBUTOS PRINCIPALES:
- self.active_chips: lista de tuplas (hybrid_id, chip_lane) de los chips activos
- self.raw_data: datos sin filtrar (solo columnas relevantes)
- self.clean_data: datos con eventos vacíos removidos

NOTA: Los hits dentro de cada evento están organizados secuencialmente por plano.
Por ejemplo, si RD53_frame_event_nhits = [2, 3, 0], los primeros 2 valores en
RD53_hit_row/col/tot pertenecen al plano 0, los siguientes 3 al plano 1, etc.
"""


class BaseAnalysis(ABC):
	"""Common utilities shared by analysis classes based on ROOT data."""

	def __init__(self, root_manager: RootManager):
		self.logger = logging.getLogger(__name__)
		# Configurar el logger si no tiene handlers
		if not self.logger.handlers:
			handler = logging.StreamHandler()
			formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
			handler.setFormatter(formatter)
			self.logger.addHandler(handler)
			self.logger.setLevel(logging.INFO)
		self.root_manager = root_manager
		self._validate()
		self.active_chips = None
		self.hybrid_ids = None
		self.chip_lanes = None
		self.raw_data = self._select_required_columns(self.root_manager.arrays)
		self.clean_data = self._remove_empty_events()
		self.logger.info(f"Active chips detected: {self.active_chips}")

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
		Retorna datos con: event, RD53_frame_event_nhits, RD53_hit_row, RD53_hit_col, RD53_hit_tot
		"""
		# Extraer los chips únicos (hybrid_id, chip_lane)
		self.hybrid_ids = data.FW_frame_event_hybrid_id[0]
		self.chip_lanes = data.FW_frame_event_chip_lane[0]
		self.active_chips = list(dict.fromkeys(zip(ak.to_list(self.hybrid_ids), ak.to_list(self.chip_lanes))))		
		# Seleccionar solo las columnas necesarias
		required_columns = [
			'event',
			'RD53_frame_event_nhits',
			'RD53_hit_row',
			'RD53_hit_col',
			'RD53_hit_tot'
		]
		return data[required_columns]