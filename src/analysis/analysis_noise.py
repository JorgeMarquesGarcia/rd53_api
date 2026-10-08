from __future__ import annotations
import heapq
import logging
from collections import Counter
import awkward as ak
import numpy as np
from src.config.root.root_manager import RootManager
from src.analysis.analysis_base import BaseAnalysis, flat_hits, pixel_keys, decode_pixel_keys
from src.analysis.analysis_hit import TOT_THRESHOLD
from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS, TOT_MAX

MIN_REPEATS = 10   # criterio B: píxel con >= N hits de ToT sospechoso en el fichero
TOT_SATURATED = TOT_MAX   # los píxeles calientes suelen dar siempre el ToT máximo

ChipKey = tuple[int, int]
Pixel = tuple[int, int]


def _unique_in_order(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Claves distintas en orden de primera aparición y cuántas veces sale cada una."""
    if len(keys) == 0:
        return keys, np.zeros(0, dtype=np.int64)
    uniq, first, counts = np.unique(keys, return_index=True, return_counts=True)
    order = np.argsort(first, kind="stable")
    return uniq[order], counts[order]


class NoiseAnalysis(BaseAnalysis):
    """Detecta píxeles ruidosos en un .root con dos criterios, que se suman:

    A. Múltiples hits: eventos con algún chip con más de 1 hit y TODOS los hits
       con ToT < tot_threshold. Todos los píxeles de esos eventos son ruidosos.
    B. Repeticiones: píxeles que se disparan min_repeats veces o más con ToT
       sospechoso en todo el fichero: ToT < tot_threshold o saturado
       (TOT_SATURATED). Cubre el ruido de píxeles que se disparan solos (1 hit
       por evento), que A no puede ver, incluidos los píxeles calientes que
       siempre dan el ToT máximo.

    tot_threshold es el mismo umbral que usa HitAnalysis para los eventos buenos.

    Atributos tras construir:
        noisy_events:       eventos ruidosos del criterio A (awkward).
        multi_hit_pixels:   {(hybrid, lane): {(row, col), ...}} del criterio A.
        repeated_pixels:    {(hybrid, lane): {(row, col), ...}} del criterio B.
        noisy_pixel_counts: {(hybrid, lane): {(row, col): nº de hits con ToT sospechoso}} (A ∪ B).
        noisy_pixels:       {(hybrid, lane): [(row, col), ...]} (A ∪ B, sin repetir).
        stats:              n_noisy_pixels, total_pixels, noise_percentage.
    """

    def __init__(self, root_manager: RootManager, tot_threshold: int = TOT_THRESHOLD,
                 min_repeats: int = MIN_REPEATS):
        super().__init__(root_manager)
        self.logger = logging.getLogger(__name__)
        self.tot_threshold = tot_threshold
        self.min_repeats = min_repeats

        self.logger.info("NoiseAnalysis: A) some chip with >1 hit and all hits with ToT < %d; "
                         "B) pixel with >= %d hits with ToT < %d or ToT = %d",
                         self.tot_threshold, self.min_repeats, self.tot_threshold, TOT_SATURATED)
        self._all_counts, self._suspect_tot_counts = self._count_hits_per_pixel()
        self._log_frequent_pixels()

        # Criterio A: múltiples hits de ToT bajo en el mismo evento
        self.noisy_events = self.extract_noisy_events()
        self.multi_hit_pixels = {k: set(v) for k, v in self._count_pixels(self.noisy_events).items() if v}
        self._log_pixels_per_chip("Criterion A (multiple hits) · noisy pixels", self.multi_hit_pixels)

        # Criterio B: píxeles que se repiten
        self.repeated_pixels = self._repeated_pixels()
        self._log_pixels_per_chip(
            f"Criterion B (>= {self.min_repeats} hits with ToT < {self.tot_threshold} "
            f"or ToT = {TOT_SATURATED}) · noisy pixels",
            self.repeated_pixels)

        self.noisy_pixel_counts = self._merge_criteria()
        self.noisy_pixels = {k: list(v) for k, v in self.noisy_pixel_counts.items()}
        self.stats = self._noise_stats()
        self._log_pixels_per_chip("Total (A + B) · noisy pixels", self.noisy_pixel_counts)
        self.logger.info("Result: %d noisy pixel(s) (%.4f %% of %d)",
                         self.stats["n_noisy_pixels"], self.stats["noise_percentage"],
                         self.stats["total_pixels"])

    # ------------------------------------------------------------------
    # Criterio A: múltiples hits
    # ------------------------------------------------------------------
    def extract_noisy_events(self):
        noisy_events = self._noise_filter()
        self.logger.info("Filtro de ruido aplicado: %d eventos ruidosos detectados", len(noisy_events))
        return noisy_events

    def _multiple_hits(self, data=None):
        if data is None:
            data = self.clean_data
        suspects = data[ak.any(data.RD53_frame_event_nhits > 1, axis=1)] #puede que me interese quitar esto, por los que llegan cruzados
        self.logger.info("Criterion A · step 1 · events with >1 hit in some chip: %d of %d events with hits",
                         len(suspects), len(data))
        return suspects

    def _noise_filter(self, data=None):
        if data is None:
            data = self.clean_data
        suspects = self._multiple_hits(data)
        noisy = suspects[ak.all(suspects.RD53_hit_tot < self.tot_threshold, axis=1)]
        self.logger.info("Criterion A · step 2 · of those, all hits with ToT < %d: %d events",
                         self.tot_threshold, len(noisy))
        return noisy

    # ------------------------------------------------------------------
    # Conteo vectorizado de hits por (chip, píxel)
    # ------------------------------------------------------------------
    def _keys_to_counter(self, keys: np.ndarray, counts: np.ndarray) -> Counter:
        """Counter {((hybrid, lane), (row, col)): n} conservando el orden de las claves."""
        planes, rows, cols = decode_pixel_keys(keys)
        chips = self.active_chips
        return Counter({
            (chips[p], (r, c)): n
            for p, r, c, n in zip(planes.tolist(), rows.tolist(), cols.tolist(), counts.tolist())
        })

    def _count_hits_per_pixel(self) -> tuple[Counter, Counter]:
        """Cuenta hits por (chip, píxel) en todo el fichero: (todos, solo ToT sospechoso).

        Las claves quedan en el orden en que cada píxel aparece por primera vez
        (en el segundo Counter, su primer hit sospechoso).
        """
        data = self.clean_data
        if len(data) == 0:
            return Counter(), Counter()
        plane, rows, cols, tots = flat_hits(data, self.active_chips)
        keys = pixel_keys(plane, rows, cols)
        suspect = (tots < self.tot_threshold) | (tots == TOT_SATURATED)

        all_counts = self._keys_to_counter(*_unique_in_order(keys))
        suspect_tot = self._keys_to_counter(*_unique_in_order(keys[suspect]))
        return all_counts, suspect_tot

    # ------------------------------------------------------------------
    # Criterio B: repeticiones
    # ------------------------------------------------------------------
    def _repeated_pixels(self) -> dict[ChipKey, set[Pixel]]:
        pixels: dict[ChipKey, set[Pixel]] = {}
        for (chip, pixel), n in self._suspect_tot_counts.items():
            if n >= self.min_repeats:
                pixels.setdefault(chip, set()).add(pixel)
        return pixels

    def _merge_criteria(self) -> dict[ChipKey, dict[Pixel, int]]:
        """A ∪ B; el valor de cada píxel es su nº de hits con ToT sospechoso."""
        merged: dict[ChipKey, dict[Pixel, int]] = {}
        for source in (self.multi_hit_pixels, self.repeated_pixels):
            for chip, pixels in source.items():
                for pixel in pixels:
                    merged.setdefault(chip, {})[pixel] = max(1, self._suspect_tot_counts[(chip, pixel)])
        return merged

    # ------------------------------------------------------------------
    # Logs de diagnóstico
    # ------------------------------------------------------------------
    def _log_frequent_pixels(self, top: int = 5) -> None:
        """Píxeles más repetidos por chip en todos los hits, sin filtrar."""
        by_chip: dict[ChipKey, list[tuple[Pixel, int]]] = {}
        for (chip, px), n in self._all_counts.items():
            by_chip.setdefault(chip, []).append((px, n))

        for chip in self.active_chips:
            # nsmallest == sorted(...)[:top]: los empates conservan el orden de aparición
            chip_counts = heapq.nsmallest(top, by_chip.get(chip, ()), key=lambda kv: -kv[1])
            if not chip_counts:
                continue
            h, c = chip
            self.logger.info("Most frequent pixels H%d·%d (all hits): %s", h, c, ", ".join(
                f"({r},{col})×{n} [ToT<{self.tot_threshold} or ={TOT_SATURATED}: "
                f"{self._suspect_tot_counts[(chip, (r, col))]}]"
                for (r, col), n in chip_counts))

    def _log_pixels_per_chip(self, label: str, pixels_by_chip) -> None:
        self.logger.info("%s: %s", label, ", ".join(
            f"H{h}·{c}: {len(pixels_by_chip.get((h, c), ()))}" for h, c in self.active_chips))

    def _count_pixels(self, noisy_events) -> dict[tuple[int, int], dict[tuple[int, int], int]]:
        """{chip: {píxel: nº de hits}} de los eventos dados, en orden de aparición.

        Con algún evento, todos los chips activos aparecen como clave (con {}
        si no tienen hits).
        """
        if len(noisy_events) == 0:
            return {}
        pixels_by_chip: dict[tuple[int, int], dict[tuple[int, int], int]] = {
            chip: {} for chip in self.active_chips
        }
        plane, rows, cols, _ = flat_hits(noisy_events, self.active_chips)
        keys, counts = _unique_in_order(pixel_keys(plane, rows, cols))
        planes, rows, cols = decode_pixel_keys(keys)
        for p, r, c, n in zip(planes.tolist(), rows.tolist(), cols.tolist(), counts.tolist()):
            pixels_by_chip[self.active_chips[p]][(r, c)] = n
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
