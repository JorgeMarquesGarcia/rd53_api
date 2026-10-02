"""noise_map.py - Mapa de calor de píxeles ruidosos de un chip (matplotlib, sin ROOT)."""
from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS


def build_noise_map_canvas(
    pixel_counts: dict[tuple[int, int], int],
    title: str = "",
) -> FigureCanvas:
    """Canvas con los píxeles ruidosos de un chip coloreados por nº de eventos ruidosos.

    Se dibujan como puntos (no imshow) para que un píxel aislado siga siendo
    visible en la matriz completa del chip.
    """
    # constrained_layout recalcula los márgenes en cada redibujado: con
    # tight_layout() se fijaban al tamaño inicial y al redimensionar el
    # canvas en Qt se cortaban las etiquetas de los ejes.
    fig = Figure(figsize=(10, 5), constrained_layout=True)
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)

    if pixel_counts:
        rows, cols, counts = zip(*((r, c, n) for (r, c), n in pixel_counts.items()))
        sc = ax.scatter(cols, rows, c=counts, cmap="plasma", s=14, marker="s",
                        vmin=1, vmax=max(max(counts), 2))
        # Colorbar como inset del propio eje: con aspect="equal" sigue pegada
        # al mapa en vez de quedarse en el borde de la figura.
        cax = ax.inset_axes([1.02, 0.0, 0.025, 1.0])
        cbar = fig.colorbar(sc, cax=cax, label="Noisy events")
        cbar.ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    ax.set_xlim(-0.5, SENSOR_COLS - 0.5)
    ax.set_ylim(-0.5, SENSOR_ROWS - 0.5)
    ax.set_aspect("equal")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.grid(True, alpha=0.2)
    ax.set_title(title)
    return canvas
