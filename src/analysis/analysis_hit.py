from __future__ import annotations
import logging
import awkward as ak

from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis
from src.core.exceptions import NAErrorNoHits

SENSOR_ROWS = 192
SENSOR_COLS = 400

OFFSETS = {
    0: (0, 0),
    1: (0, SENSOR_COLS),
    2: (SENSOR_ROWS, SENSOR_COLS),
    3: (SENSOR_ROWS, 0),
}


"""Análisis de hits para archivos ROOT.
Atributos: 
- active_chips: lista de chips activos detectados en los datos.
- hits: awkward array con los hits filtrados según trigger, coincidencia y ToT.
- plot_coord: awkward array con coordenadas X, Y, Z y ToT para cada evento, usando el hit de máximo ToT por plano.

Funciones principales:
- _extract_hits: aplica el filtro de trigger y valida eventos.
- _detector_filter: selecciona eventos con hits en otros chips.
- _tot_filter: filtra eventos por umbral de ToT.
- _layer_filter: filtra eventos por capas específicas.
- _extract_track_coordinates: obtiene coordenadas de trayectoria usando el hit de máximo ToT por plano.

"""


class HitAnalysis(BaseAnalysis):
    """Clase de análisis para datos de hits provenientes de archivos ROOT."""

    def __init__(self, root_manager: RootManager):
        """Inicializa el analizador y prepara los hits filtrados."""
        super().__init__(root_manager)
        self.logger.info("HitAnalysis initialized successfully")
        self.trigger_data = None
        self.hits = None
        self.plot_coord = None
        self._analyzed = False
        self.hits = self._extract_hits()
        self.plot_coord = self._extract_track_coordinates()
    

    def _extract_hits(self):
        """Extrae los hits aplicando el filtro de trigger y luego el detector."""
        self.trigger_data = self._apply_trigger_filter()
        if not self._datacheck():
            raise NAErrorNoHits("No events with hits found after applying trigger filter.")
        self.logger.info(f"Trigger filter applied: {len(self.trigger_data)} events with trigger")

        coincidence_hits = self.coincidence()
        self.logger.info(f"Coincidence filter applied: {len(coincidence_hits)} events with hits in other chips")

        tot_filter = self._tot_filter(coincidence_hits, tot_threshold=2)
        self.logger.info(f"ToT filter applied: {len(tot_filter)} events with ToT >= 2")
        hits = tot_filter
        self._analyzed = True
        return hits

    

    def _apply_trigger_filter(self):
        """Devuelve los eventos marcados como triggered."""
        return self.clean_data[self.clean_data.RD53_frame_event_nhits[:, 0] != 0]
   
    def _datacheck(self):
        """Comprueba si existen eventos tras aplicar el filtro de trigger."""
        if len(self.trigger_data) == 0:
            return False
        return True
    
    def coincidence(self):
        """Filtra eventos con hits en otros chips del detector."""
        self._analyzed = True
        return self._detector_filter()
    
    def _detector_filter(self, data=None):
        """Implementa el filtro de detector."""
        if data is None:
            data = self.trigger_data
        return data[ak.sum(data.RD53_frame_event_nhits[:, 1:], axis=1) >= 1]

    def filter_tot(self, data=None, tot_threshold=3):
        """Filtra eventos cuyo ToT cumple el umbral definido."""
        self._analyzed = True
        return self._tot_filter(data=data, tot_threshold=tot_threshold)
  
    def _tot_filter(self, data=None, tot_threshold=3):
        """Implementa el filtro por ToT."""
        if data is None:
            data = self.trigger_data
        return data[ak.all(data.RD53_hit_tot >= tot_threshold, axis=1)]
    

    def coincidence_filter_layer(self, data=None, layer=[]):
        """Filtra eventos por una o varias capas del detector."""
        self._analyzed = True
        return self._layer_filter(data=data, layer=layer)
    
    def _layer_filter(self, data=None, layer=[]):
        """Implementa el filtro de coincidencia por capa."""
        if data is None:
            data = self.trigger_data
        if not layer:
            return data
        return data[ak.any(data.RD53_frame_event_nhits[:, layer] >= 1, axis=1)]

    def _extract_track_coordinates(self):
        """
        Retorna una lista de len(nevents) donde cada elemento es un dict:
            {(hybrid_id, chip_lane): (row, col)}
        con el hit de máximo ToT por detector, con offsets aplicados.
        Detectores sin hits se omiten del dict.
        """

        plot_data = []

        for event in self.hits:
            event_dict = {}
            hit_index = 0

            for i, (hybrid_id, chip_lane) in enumerate(self.active_chips):
                nhits = int(event.RD53_frame_event_nhits[i])

                if nhits > 0:
                    rows = ak.to_list(event.RD53_hit_row[hit_index:hit_index + nhits])
                    cols = ak.to_list(event.RD53_hit_col[hit_index:hit_index + nhits])
                    tots = ak.to_list(event.RD53_hit_tot[hit_index:hit_index + nhits])

                    max_idx = tots.index(max(tots))
                    row = rows[max_idx]
                    col = cols[max_idx]

                    if hybrid_id == 0:
                        row += SENSOR_ROWS // 2
                        col += SENSOR_COLS // 2
                    else:
                        row_off, col_off = OFFSETS[chip_lane]
                        row += row_off
                        col += col_off

                    event_dict[(hybrid_id, chip_lane)] = (row, col)

                hit_index += nhits

            plot_data.append(event_dict)

        return plot_data