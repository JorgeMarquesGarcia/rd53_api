"""Energía depositada por las partículas, a partir del ToT de los hits y del Gain scan.

Para cada track de HitAnalysis (una ventana de trigger con coincidencia) y cada
plano con hits:
- cluster: el hit de máximo ToT (el mismo que usa HitAnalysis para la trayectoria)
  y los hits contiguos a él, de forma transitiva (vecindad de 8 píxeles). Los
  demás hits del plano no son de la partícula y no cuentan.
- carga del cluster: suma de la carga de sus hits (GainCalibration.to_charge).
- energía: carga · W_SI.

Un cluster con algún hit de ToT saturado (TOT_MAX) solo da una cota inferior de
la energía: se marca como saturado. Los hits de píxeles sin ajuste válido en el
Gain scan usan la recta mediana del chip (n_fallback).

Atributos:
- clusters: dict de arrays numpy, un elemento por cluster (ver CLUSTER_FIELDS).
- stats: {(hybrid_id, chip_lane): resumen} por chip.
- missing_chips: chips con hits pero sin calibración utilizable.
"""
from __future__ import annotations
import logging

import awkward as ak
import numpy as np

from src.analysis.analysis_base import flat_hits, format_chips
from src.analysis.analysis_hit import HitAnalysis
from src.analysis.gain_calibration import GainCalibration, charge_to_energy_kev
from src.chip.detector_geometry import TOT_MAX, rd53_id

CLUSTER_FIELDS = ("track", "event", "hybrid", "lane", "n_hits", "tot_sum",
                  "charge", "energy_kev", "saturated", "n_fallback")


def cluster_mask(rows: np.ndarray, cols: np.ndarray, tots: np.ndarray) -> np.ndarray:
    """Hits del cluster del hit de máximo ToT: los contiguos a él, de forma transitiva."""
    member = np.zeros(len(tots), dtype=bool)
    seed = int(np.argmax(tots))   # empate: el primero, como en HitAnalysis
    member[seed] = True
    frontier = [seed]
    while frontier:
        i = frontier.pop()
        near = ~member & (np.abs(rows - rows[i]) <= 1) & (np.abs(cols - cols[i]) <= 1)
        new = np.flatnonzero(near)
        member[new] = True
        frontier.extend(new.tolist())
    return member


class EnergyAnalysis:
    """Energía depositada por cluster a partir de los hits de un HitAnalysis."""

    def __init__(self, hit_analysis: HitAnalysis, calibration: GainCalibration):
        self.logger = logging.getLogger(__name__)
        self.calibration = calibration
        self.active_chips: list[tuple[int, int]] = list(hit_analysis.active_chips)
        self.missing_chips: list[tuple[int, int]] = []
        self.clusters = self._compute_clusters(hit_analysis.hits)
        self.stats = self._compute_stats()
        self._log_summary()

    # ------------------------------------------------------------------
    # Carga por hit
    # ------------------------------------------------------------------
    def _hit_charges(self, plane, rows, cols, tots) -> tuple[np.ndarray, np.ndarray]:
        """Carga [e⁻] de cada hit (NaN si su chip no tiene calibración) y máscara de fallback."""
        charge = np.full(len(tots), np.nan)
        fallback = np.zeros(len(tots), dtype=bool)
        for p, (hybrid, lane) in enumerate(self.active_chips):
            sel = plane == p
            if not sel.any():
                continue
            try:
                key = (hybrid, rd53_id(hybrid, lane))
            except ValueError:
                key = None
            if key is None or not self.calibration.usable(key):
                self.missing_chips.append((hybrid, lane))
                continue
            charge[sel], fallback[sel] = self.calibration.to_charge(key, rows[sel], cols[sel], tots[sel])
        return charge, fallback

    # ------------------------------------------------------------------
    # Clusters
    # ------------------------------------------------------------------
    def _compute_clusters(self, hits) -> dict[str, np.ndarray]:
        out: dict[str, list] = {name: [] for name in CLUSTER_FIELDS}
        if hits is None or len(hits) == 0:
            return {name: np.asarray(values) for name, values in out.items()}

        plane, rows, cols, tots = flat_hits(hits, self.active_chips)
        rows = rows.astype(np.int64)
        cols = cols.astype(np.int64)
        tots = tots.astype(np.int64)
        charge, fallback = self._hit_charges(plane, rows, cols, tots)

        # Hits ordenados por ventana y, dentro de cada una, por plano: cada
        # bloque contiguo con la misma (ventana, plano) es un grupo
        per_window = ak.to_numpy(ak.sum(hits.RD53_frame_event_nhits, axis=1)).astype(np.int64)
        window = np.repeat(np.arange(len(per_window)), per_window)
        events = ak.to_numpy(hits.event)
        group = window * len(self.active_chips) + plane
        starts = np.flatnonzero(np.diff(group, prepend=-1) != 0)
        ends = np.append(starts[1:], len(group))

        for start, end in zip(starts, ends):
            if np.isnan(charge[start]):   # chip sin calibración
                continue
            g_rows, g_cols, g_tots = rows[start:end], cols[start:end], tots[start:end]
            member = cluster_mask(g_rows, g_cols, g_tots)
            q = float(charge[start:end][member].sum())
            hybrid, lane = self.active_chips[plane[start]]
            out["track"].append(int(window[start]) + 1)   # misma numeración que el log de HitAnalysis
            out["event"].append(int(events[window[start]]))
            out["hybrid"].append(hybrid)
            out["lane"].append(lane)
            out["n_hits"].append(int(member.sum()))
            out["tot_sum"].append(int(g_tots[member].sum()))
            out["charge"].append(q)
            out["energy_kev"].append(charge_to_energy_kev(q))
            out["saturated"].append(bool((g_tots[member] >= TOT_MAX).any()))
            out["n_fallback"].append(int(fallback[start:end][member].sum()))

        return {name: np.asarray(values) for name, values in out.items()}

    def chip_mask(self, chip: tuple[int, int]) -> np.ndarray:
        """Máscara de los clusters de un chip (hybrid_id, chip_lane)."""
        return (self.clusters["hybrid"] == chip[0]) & (self.clusters["lane"] == chip[1])

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------
    def _compute_stats(self) -> dict[tuple[int, int], dict]:
        stats = {}
        for chip in self.active_chips:
            sel = self.chip_mask(chip)
            n = int(sel.sum())
            if n == 0:
                continue
            energy = self.clusters["energy_kev"][sel]
            stats[chip] = {
                "n_clusters": n,
                "median_kev": float(np.median(energy)),
                "mean_kev": float(np.mean(energy)),
                "median_charge": float(np.median(self.clusters["charge"][sel])),
                "saturated_fraction": float(np.mean(self.clusters["saturated"][sel])),
                "mean_size": float(np.mean(self.clusters["n_hits"][sel])),
                "n_fallback_hits": int(self.clusters["n_fallback"][sel].sum()),
            }
        return stats

    def _log_summary(self) -> None:
        if self.missing_chips:
            self.logger.warning("No usable gain calibration for %s in %s: their hits are skipped.",
                                format_chips(self.missing_chips), self.calibration.source)
        self.logger.info("Clusters with energy: %d", len(self.clusters["energy_kev"]))
        for (h, c), s in self.stats.items():
            self.logger.info(
                "H%d·%d: %d clusters, median %.2f keV (%.0f e⁻), mean %.2f keV, "
                "mean size %.2f px, %.1f %% with saturated ToT (lower bound), "
                "%d hit(s) without own gain fit",
                h, c, s["n_clusters"], s["median_kev"], s["median_charge"], s["mean_kev"],
                s["mean_size"], 100 * s["saturated_fraction"], s["n_fallback_hits"])
