"""latency_histogram.py - Posición de los hits en la ventana de trigger, un panel por chip (matplotlib, sin ROOT)."""
from __future__ import annotations
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

BAR_COLOR = "#2a78d6"
CENTRE_COLOR = "#8a8984"
MEDIAN_COLOR = "#0b0b0b"
PANEL_HEIGHT = 2.0   # pulgadas por chip


def build_latency_canvas(histograms: dict, stats: dict, ntrig: int,
                         centre: int | None = None) -> FigureCanvas:
    """Hits por posición (BX) en la ventana de nTRIGxEvent, un panel por chip.

    histograms: {(hybrid, lane): hits en cada BX de la ventana (ntrig valores)}.
    stats:      {(hybrid, lane): dict de LatencyAnalysis.chip_statistics}.
    centre:     BX objetivo que se marca (None = ntrig // 2, el centro de esta
                ventana); p. ej. el centro de la ventana de las adquisiciones.
    Cada panel marca ese centro y la mediana de la posición.
    """
    chips = list(histograms)
    fig = Figure(figsize=(8, 0.8 + PANEL_HEIGHT * max(len(chips), 1)), constrained_layout=True)
    canvas = FigureCanvas(fig)
    axes = fig.subplots(max(len(chips), 1), 1, sharex=True, squeeze=False)[:, 0]

    positions = np.arange(ntrig)
    if centre is None:
        centre = ntrig // 2
    for i, (ax, chip) in enumerate(zip(axes, chips)):
        counts = np.asarray(histograms[chip])
        s = stats[chip]
        ax.bar(positions, counts, width=0.4, color=BAR_COLOR, zorder=2)
        top = max(int(counts.max()), 1)
        for x, n in zip(positions, counts):
            if n:
                # Fondo blanco: la línea de la mediana puede pasar por encima de la barra
                ax.text(x, n + top * 0.04, str(int(n)), ha="center", va="bottom", fontsize=8,
                        zorder=4, bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"))
        ax.axvline(centre, color=CENTRE_COLOR, linestyle="--", linewidth=1.2, zorder=1,
                   label=f"Target centre (BX{centre})")
        if s["median"] is not None:
            ax.axvline(s["median"], color=MEDIAN_COLOR, linewidth=1.2, zorder=3,
                       label=f"Median = BX{s['median']:g}")
        else:
            ax.text(0.5, 0.5, "No hits", transform=ax.transAxes, ha="center", va="center",
                    fontsize=10, color=CENTRE_COLOR)
        ax.set_ylim(0, top * 1.3)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel("Hits", fontsize=9)
        ax.set_title(f"H{chip[0]} · Chip {chip[1]} — {s['n_hits']} hits", fontsize=10,
                     fontweight="bold", loc="left")
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax.legend(fontsize=8, framealpha=0.7, loc="upper left")

    axes[-1].set_xticks(positions)
    axes[-1].set_xticklabels([f"BX{p}" for p in positions])
    axes[-1].set_xlim(-0.6, ntrig - 0.4)
    axes[-1].set_xlabel(f"Position in the trigger window ({ntrig} BX)", fontsize=9)
    return canvas
