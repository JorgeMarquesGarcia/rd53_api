"""Análisis de hits para archivos ROOT.

Atributos:
- active_chips: lista de chips activos detectados en los datos.
- window_data: un evento por ventana de trigger (los nTRIGxEvent BX que lee cada trigger).
- hits: awkward array con los hits filtrados según trigger, coincidencia y ToT.
- plot_coord: lista con un dict por track {(hybrid_id, chip_lane): (row, col, tot)},
  usando el hit de máximo ToT por plano, en coordenadas globales.

Funciones principales:
- _group_trigger_windows: quita los píxeles ruidosos, une los BX de cada trigger en un
  evento y aplica la coincidencia en BX.
- _extract_hits: aplica el filtro de trigger y valida eventos.
- _detector_filter: selecciona eventos con hits en otros chips.
- _tot_filter: filtra eventos por umbral de ToT.
- _layer_filter: filtra eventos por capas específicas.
- _extract_track_coordinates: obtiene coordenadas de trayectoria usando el hit de máximo ToT por plano
  y escribe en el log los hits de cada track.
"""
from __future__ import annotations
import awkward as ak
import numpy as np

from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis, pixel_keys
from src.core.exceptions import NAErrorNoHits
from src.chip.detector_geometry import to_global

TOT_THRESHOLD = 2   # un evento se descarta si TODOS sus hits tienen ToT < umbral
BX_TOLERANCE = 2    # BX máximos entre un hit y el del plano de trigger en su ventana (None = toda la ventana)


class HitAnalysis(BaseAnalysis):
    """Clase de análisis para datos de hits provenientes de archivos ROOT."""

    def __init__(self, root_manager: RootManager, tot_threshold: int = TOT_THRESHOLD,
                 bx_tolerance: int | None = BX_TOLERANCE,
                 noisy_pixels: dict[tuple[int, int], list[tuple[int, int]]] | None = None):
        """Inicializa el analizador y prepara los hits filtrados.

        noisy_pixels: {(hybrid, lane): [(row, col), ...]} (NoiseAnalysis.noisy_pixels).
        Sus hits se descartan antes de buscar coincidencias.
        """
        super().__init__(root_manager)
        self.logger.info("HitAnalysis initialized successfully")
        self.tot_threshold = tot_threshold
        self.bx_tolerance = bx_tolerance
        self.noisy_pixels = noisy_pixels or {}
        self.window_data = None
        self.trigger_data = None
        self.hits = None
        self.plot_coord = None
        self._analyzed = False
        self.hits = self._extract_hits()
        self.plot_coord = self._extract_track_coordinates()

    def _extract_hits(self):
        """Extrae los hits aplicando el filtro de trigger y luego el detector."""
        self.window_data = self._group_trigger_windows()
        self.trigger_data = self._apply_trigger_filter()
        if not self._datacheck():
            raise NAErrorNoHits("No events with hits found after applying trigger filter.")
        self.logger.info("Trigger filter applied: %d trigger windows with hits in the trigger plane",
                         len(self.trigger_data))

        coincidence_hits = self.coincidence()
        self.logger.info("Coincidence filter applied: %d windows with hits in other chips",
                         len(coincidence_hits))

        hits = self._tot_filter(coincidence_hits, tot_threshold=self.tot_threshold)
        self.logger.info("ToT filter applied: %d windows with some hit ToT >= %s",
                         len(hits), self.tot_threshold)
        self._analyzed = True
        return hits

    def _group_trigger_windows(self):
        """Une en un solo evento las entradas de cada ventana de trigger.

        Cada trigger lee nTRIGxEvent BX consecutivos y Ph2_ACF guarda cada BX como
        una entrada distinta del TTree, así que los hits de una misma partícula
        pueden quedar repartidos en entradas contiguas. Las entradas de una ventana
        tienen FW_bx_counter consecutivo: la ventana se detecta en los datos y no
        depende del nTRIGxEvent con que se tomó el run.

        Antes de nada se descartan los hits de los píxeles ruidosos (noisy_pixels).

        Con bx_tolerance solo se conservan los hits a esa distancia en BX, o menos,
        del hit de máximo ToT del plano de trigger (plano 0): el ruido de los demás
        BX de la ventana no forma coincidencias. Las ventanas sin hits en el plano
        de trigger no se recortan (las descarta después el filtro de trigger).

        Devuelve un evento por ventana con hits, con la estructura de clean_data
        (hits ordenados por plano) más RD53_hit_bx: posición del BX de cada hit
        dentro de su ventana.
        """
        data = self.raw_data
        bx_counter = ak.to_numpy(data.FW_bx_counter).astype(np.int64)
        starts = np.ones(len(bx_counter), dtype=bool)
        starts[1:] = np.diff(bx_counter) != 1
        window = np.cumsum(starts) - 1                     # ventana de cada entrada
        first = np.flatnonzero(starts)                     # primera entrada de cada ventana
        position = np.arange(len(bx_counter)) - first[window]

        sizes, n_windows = np.unique(np.diff(np.append(first, len(bx_counter))), return_counts=True)
        self.logger.info("Trigger windows: %s", ", ".join(
            f"{n} of {size} BX" for size, n in zip(sizes, n_windows)))

        # Un elemento por hit: entrada, plano y ventana a la que pertenece
        nhits = ak.to_numpy(data.RD53_frame_event_nhits).astype(np.int64)  # (entradas, planos)
        n_planes = nhits.shape[1]
        hit_entry = np.repeat(np.arange(len(nhits)), nhits.sum(axis=1))
        hit_plane = np.repeat(np.tile(np.arange(n_planes), len(nhits)), nhits.ravel())
        hit_window = window[hit_entry]
        hit_bx = position[hit_entry]
        rows = ak.to_numpy(ak.flatten(data.RD53_hit_row))
        cols = ak.to_numpy(ak.flatten(data.RD53_hit_col))
        tots = ak.to_numpy(ak.flatten(data.RD53_hit_tot))

        keep = ~self._noisy_hits(hit_plane, rows, cols)
        if self.bx_tolerance is not None:
            # BX de referencia: el del hit de máximo ToT del plano de trigger
            trig = np.flatnonzero((hit_plane == 0) & keep)
            trig = trig[np.lexsort((-tots[trig].astype(np.int64), hit_window[trig]))]
            ref_windows, ref_idx = np.unique(hit_window[trig], return_index=True)
            ref_bx = np.full(len(first), -1, dtype=np.int64)
            ref_bx[ref_windows] = hit_bx[trig[ref_idx]]
            hit_ref = ref_bx[hit_window]
            keep &= (hit_ref < 0) | (np.abs(hit_bx - hit_ref) <= self.bx_tolerance)

        # Agrupar por ventana y, dentro de cada una, por plano (orden estable: por BX)
        sel = np.flatnonzero(keep)
        sel = sel[np.lexsort((hit_plane[sel], hit_window[sel]))]
        windows, w_idx = np.unique(hit_window[sel], return_inverse=True)
        w_idx = w_idx.reshape(-1)
        counts = np.zeros((len(windows), n_planes), dtype=np.int64)
        np.add.at(counts, (w_idx, hit_plane[sel]), 1)
        per_window = counts.sum(axis=1)

        return ak.zip({
            "event": ak.to_numpy(data.event)[first[windows]],
            "RD53_frame_event_nhits": counts,
            "RD53_hit_row": ak.unflatten(rows[sel], per_window),
            "RD53_hit_col": ak.unflatten(cols[sel], per_window),
            "RD53_hit_tot": ak.unflatten(tots[sel], per_window),
            "RD53_hit_bx": ak.unflatten(hit_bx[sel], per_window),
        }, depth_limit=1)

    def _noisy_hits(self, hit_plane, rows, cols) -> np.ndarray:
        """Máscara de los hits que caen en un píxel ruidoso de su plano."""
        if not self.noisy_pixels:
            return np.zeros(len(hit_plane), dtype=bool)
        noisy = [
            (plane, row, col)
            for plane, chip in enumerate(self.active_chips)
            for row, col in self.noisy_pixels.get(chip, ())
        ]
        if noisy:
            n_planes, n_rows, n_cols = (np.array(v, dtype=np.int64) for v in zip(*noisy))
            noisy_keys = pixel_keys(n_planes, n_rows, n_cols)
        else:
            noisy_keys = np.zeros(0, dtype=np.int64)
        is_noisy = np.isin(pixel_keys(hit_plane, rows, cols), noisy_keys)
        self.logger.info("Noisy pixels: %d hit(s) removed (%d noisy pixel(s) masked)",
                         int(is_noisy.sum()), len(noisy))
        return is_noisy

    def _apply_trigger_filter(self):
        """Devuelve las ventanas con hits en el plano de trigger (plano 0)."""
        return self.window_data[self.window_data.RD53_frame_event_nhits[:, 0] != 0]

    def _datacheck(self):
        """Comprueba si existen eventos tras aplicar el filtro de trigger."""
        return len(self.trigger_data) != 0

    def coincidence(self):
        """Filtra eventos con hits en otros chips del detector."""
        self._analyzed = True
        return self._detector_filter()

    def _detector_filter(self, data=None):
        """Implementa el filtro de detector."""
        if data is None:
            data = self.trigger_data
        return data[ak.sum(data.RD53_frame_event_nhits[:, 1:], axis=1) >= 1]

    def filter_tot(self, data=None, tot_threshold=TOT_THRESHOLD):
        """Filtra eventos cuyo ToT cumple el umbral definido."""
        self._analyzed = True
        return self._tot_filter(data=data, tot_threshold=tot_threshold)

    def _tot_filter(self, data=None, tot_threshold=TOT_THRESHOLD):
        """Descarta el evento entero solo si TODOS sus hits tienen ToT < umbral."""
        if data is None:
            data = self.trigger_data
        return data[ak.any(data.RD53_hit_tot >= tot_threshold, axis=1)]

    def coincidence_filter_layer(self, data=None, layer=None):
        """Filtra eventos por una o varias capas del detector."""
        self._analyzed = True
        return self._layer_filter(data=data, layer=layer)

    def _layer_filter(self, data=None, layer=None):
        """Implementa el filtro de coincidencia por capa."""
        if data is None:
            data = self.trigger_data
        if not layer:
            return data
        return data[ak.any(data.RD53_frame_event_nhits[:, layer] >= 1, axis=1)]

    def _extract_track_coordinates(self):
        """
        Retorna una lista de len(nevents) donde cada elemento es un dict:
            {(hybrid_id, chip_lane): (row, col, tot)}
        con el hit de máximo ToT por detector, en coordenadas globales
        (offsets de detector_geometry aplicados), y su ToT.
        Detectores sin hits se omiten del dict.

        Escribe en el log una línea por track con todos sus hits: coordenadas
        locales del chip (columna, fila), ToT y BX dentro de la ventana.
        """
        hits = self.hits
        # Conversión en bloque a listas de Python: acceder a awkward evento a
        # evento es órdenes de magnitud más lento con muchos tracks.
        events = ak.to_list(hits.event)
        nhits_per_event = ak.to_list(hits.RD53_frame_event_nhits)
        rows_per_event = ak.to_list(hits.RD53_hit_row)
        cols_per_event = ak.to_list(hits.RD53_hit_col)
        tots_per_event = ak.to_list(hits.RD53_hit_tot)
        bxs_per_event = ak.to_list(hits.RD53_hit_bx)

        log_track = self.logger.info
        plot_data = []
        for n_track, (event, nhits_by_chip, ev_rows, ev_cols, ev_tots, ev_bxs) in enumerate(
                zip(events, nhits_per_event, rows_per_event, cols_per_event,
                    tots_per_event, bxs_per_event), start=1):
            event_dict = {}
            hit_index = 0
            log_parts = []

            for (hybrid_id, chip_lane), nhits in zip(self.active_chips, nhits_by_chip):
                if nhits > 0:
                    end = hit_index + nhits
                    rows = ev_rows[hit_index:end]
                    cols = ev_cols[hit_index:end]
                    tots = ev_tots[hit_index:end]
                    bxs = ev_bxs[hit_index:end]
                    log_parts.append(f"H{hybrid_id}·{chip_lane} " + ", ".join(
                        f"({c}, {r}) ToT {t} BX {b}" for r, c, t, b in zip(rows, cols, tots, bxs)))

                    max_idx = tots.index(max(tots))
                    row, col = to_global(hybrid_id, chip_lane, rows[max_idx], cols[max_idx])
                    event_dict[(hybrid_id, chip_lane)] = (row, col, int(tots[max_idx]))

                hit_index += nhits

            log_track("Track %d (event %d): %s", n_track, event, " | ".join(log_parts))
            plot_data.append(event_dict)

        return plot_data
