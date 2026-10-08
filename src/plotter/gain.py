"""Plotters del Gain scan (ToT frente a ΔVCal) y de la Gain optimization (KRUM elegido)."""
from __future__ import annotations
import numpy as np
from matplotlib.axes import Axes
from src.plotter.plotter_base import PlotterBase
from src.plotter.scurve import SCurvePlotter
import logging
logger = logging.getLogger(__name__)


class GainPlotter(SCurvePlotter):
    """Plotter para el histograma Gain del chip RD53A.

    El TH2F tiene:
        Eje X: ΔVCal  (VCalHnsteps bins)
        Eje Y: ToT medio del píxel (nEvents bins entre 0 y 16)
        Z:     Número de píxeles con ese ToT medio para ese ΔVCal

    El perfil (media y σ por ΔVCal) se calcula igual que en SCurves; solo
    cambia el dibujado. Los píxeles sin hits en un paso cuentan con ToT 0.
    """

    plot_key = "Gain"

    def _draw(self, ax: Axes, data: dict) -> None:
        self.logger.info("[Gain] Iniciando dibujado del gráfico")
        try:
            if not data or data.get("values") is None or len(data.get("values", [])) == 0:
                self.logger.error("[Gain] Datos vacíos o inválidos para dibujado")
                raise ValueError("Los datos están vacíos")

            # --- Mapa de calor 2D ---
            mesh = ax.pcolormesh(
                data["xedges"],
                data["yedges"],
                data["values"].T,
                cmap="Blues",
                shading="flat",
                alpha=0.6,
            )
            cbar = self._figure.colorbar(mesh, ax=ax)
            cbar.set_label("Nº píxeles", fontsize=9)

            valid = data["profile_valid"]
            if valid.any():
                x     = data["centers_x"][valid]
                mean  = data["profile_mean"][valid]
                sigma = data["profile_sigma"][valid]

                # --- Banda ±σ sombreada ---
                ax.fill_between(
                    x,
                    np.clip(mean - sigma, 0, None),
                    mean + sigma,
                    alpha=0.25,
                    color="#F44336",
                    label="±σ",
                    zorder=3,
                )

                # --- Perfil medio con barras de error ±σ ---
                ax.errorbar(
                    x,
                    mean,
                    yerr=sigma,
                    color="#F44336",
                    linewidth=1.6,
                    linestyle="-",
                    marker="o",
                    markersize=3,
                    capsize=2,
                    capthick=1,
                    elinewidth=0.8,
                    label="ToT medio ± σ",
                    zorder=5,
                )

                ax.legend(fontsize=8, framealpha=0.7)
            else:
                self.logger.warning("[Gain] No hay puntos válidos en el perfil para dibujar")

            ax.set_ylim(data["yedges"][0], data["yedges"][-1])
            ax.set_xlabel("ΔVCal", fontsize=9)
            ax.set_ylabel("ToT", fontsize=9)
            ax.set_title("Gain — ToT vs ΔVCal", fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=8)
            ax.grid(linestyle="--", alpha=0.3)

            self.logger.info("[Gain] Gráfico dibujado exitosamente")
        except Exception as e:
            self.logger.exception(f"[Gain] Error durante el dibujado: {e}")
            raise


class KrumCurrPlotter(PlotterBase):
    """Plotter para el histograma KrumCurr de GainOptimization.

    TH1F con una sola entrada por chip: el KRUM_CURR_LIN elegido. Se dibuja
    con el eje X acotado alrededor de ese valor.
    """

    plot_key = "KrumCurr"
    _HALF_WINDOW = 20   # bins a cada lado del valor elegido

    def _extract(self) -> dict:
        self.logger.info("[KrumCurr] Iniciando extracción de datos")
        f, canvas = self._open_canvas()
        try:
            h = self._get_primitive(canvas, "TH1")
            if h is None:
                raise ValueError(f"No se encontró TH1 en el canvas '{self.canvas_path}'")
            data = self._th1_to_dict(h)
            filled = np.flatnonzero(data["values"])
            if filled.size == 0:
                raise ValueError(f"Histograma '{h.GetName()}' está vacío (0 entradas)")
        finally:
            f.Close()
        data["krum"] = [int(data["edges"][i]) for i in filled]
        self.logger.info(f"[KrumCurr] KRUM_CURR_LIN elegido: {data['krum']}")
        return data

    def _draw(self, ax: Axes, data: dict) -> None:
        edges, values = data["edges"], data["values"]
        lo = max(edges[0], min(data["krum"]) - self._HALF_WINDOW)
        hi = min(edges[-1], max(data["krum"]) + self._HALF_WINDOW + 1)
        ax.bar(
            edges[:-1],
            values,
            width=edges[1:] - edges[:-1],
            align="edge",
            color="#3F51B5",
            alpha=0.75,
            linewidth=0.4,
            edgecolor="white",
        )
        ax.set_xlim(lo, hi)
        ax.set_xlabel("KRUM_CURR_LIN", fontsize=9)
        ax.set_ylabel("Entries", fontsize=9)
        krum = ", ".join(str(k) for k in data["krum"])
        ax.set_title(f"Krummenacher Current = {krum}", fontsize=10, fontweight="bold")
        ax.tick_params(labelsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
