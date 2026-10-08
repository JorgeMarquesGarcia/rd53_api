"""energy_histogram.py - Distribución de la energía depositada por cluster (matplotlib, sin ROOT)."""
from __future__ import annotations
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from src.analysis.gain_calibration import W_SI

N_BINS = 50
_UPPER_PERCENTILE = 99.5   # el eje X llega hasta este percentil (+10 %) para que la cola no lo aplaste


def _kev_to_ke(e):
    return e / W_SI


def _ke_to_kev(q):
    return q * W_SI


def build_energy_canvas(energy_kev: np.ndarray, saturated: np.ndarray, title: str = "") -> FigureCanvas:
    """Histograma de la energía por cluster, con los clusters saturados apilados aparte.

    Eje inferior en keV y superior en ke⁻ (Q = E / W_SI).
    """
    fig = Figure(figsize=(8, 4.5), constrained_layout=True)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)

    energy_kev = np.asarray(energy_kev, dtype=float)
    saturated = np.asarray(saturated, dtype=bool)
    if energy_kev.size:
        upper = max(float(np.percentile(energy_kev, _UPPER_PERCENTILE)) * 1.1, 1.0)
        bins = np.linspace(0.0, upper, N_BINS + 1)
        n_over = int((energy_kev > upper).sum())
        ax.hist([energy_kev[~saturated], energy_kev[saturated]], bins=bins, stacked=True,
                color=["#2196F3", "#FF9800"],
                label=[f"Clusters ({int((~saturated).sum())})",
                       f"Saturated ToT, lower bound ({int(saturated.sum())})"])
        median = float(np.median(energy_kev))
        ax.axvline(median, color="black", linestyle="--", linewidth=1.2,
                   label=f"Median = {median:.2f} keV ({_kev_to_ke(median):.1f} ke⁻)")
        if n_over:
            ax.plot([], [], " ", label=f"{n_over} above {upper:.1f} keV (not shown)")
        ax.legend(fontsize=8, framealpha=0.7)
        ax.set_xlim(0.0, upper)

    secax = ax.secondary_xaxis("top", functions=(_kev_to_ke, _ke_to_kev))
    secax.set_xlabel("Charge [ke⁻]", fontsize=9)
    secax.tick_params(labelsize=8)
    ax.set_xlabel("Deposited energy [keV]", fontsize=9)
    ax.set_ylabel("Clusters", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_title(title, fontsize=10, fontweight="bold")
    return canvas
