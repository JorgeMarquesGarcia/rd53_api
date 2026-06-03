from __future__ import annotations
import numpy as np
from matplotlib.axes import Axes
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from rd53_api.plotter.plotter_base import PlotterBase

# ---------------------------------------------------------------------------
# Configuración visual por figura
# ---------------------------------------------------------------------------
_PLOT_CONFIG: dict[str, dict] = {
    "Threshold1D": {
        "color": "#2196F3",
        "title": "Threshold Distribution",
        "ylabel": "Entries",
    },
    "Noise1D": {
        "color": "#F44336",
        "title": "Noise Distribution",
        "ylabel": "Entries",
    },
    "Occ1D": {
        "color": "#4CAF50",
        "title": "Occupancy Distribution",
        "ylabel": "Entries",
    },
    "ToT1D": {
        "color": "#FF9800",
        "title": "Time over Threshold Distribution",
        "ylabel": "Entries",
    },
    "TDAC1D": {
        "color": "#9C27B0",
        "title": "TDAC Distribution",
        "ylabel": "Entries",
    },
    "ThrEqualization": {
        "color": "#00BCD4",
        "title": "Threshold Equalization",
        "ylabel": "Entries",
    },
}

_DEFAULT_CONFIG = {
    "color": "#607D8B",
    "title": "Distribution",
    "ylabel": "Entries",
}


class Histogram1DPlotter(PlotterBase):
    """Plotter genérico para histogramas TH1F del chip RD53A.

    Dibuja un histograma de barras con línea de media y desviación estándar.
    """

    plot_key: str = ""

    def _extract(self) -> dict:
        logger.info(f"Iniciando extracción de datos para {self.plot_key} desde {self.canvas_path}")
        try:
            f, canvas = self._open_canvas()
            logger.debug(f"Canvas abierto exitosamente")
            
            h = self._get_primitive(canvas, "TH1")
            if h is None:
                logger.error(f"No se encontró histograma TH1 en el canvas '{self.canvas_path}'")
                f.Close()
                raise ValueError(f"No se encontró TH1 en el canvas '{self.canvas_path}'")
            
            logger.info(f"Histograma TH1 encontrado. Convirtiendo a diccionario...")
            data = self._th1_to_dict(h)
            f.Close()

            # Calcular media y sigma ponderados por entradas
            centers = (data["edges"][:-1] + data["edges"][1:]) / 2
            total = data["values"].sum()
            logger.debug(f"Total de entradas: {total}")
            
            if total > 0:
                mean = np.average(centers, weights=data["values"])
                variance = np.average((centers - mean) ** 2, weights=data["values"])
                data["mean"] = mean
                data["sigma"] = np.sqrt(variance)
                logger.info(f"Estadísticas calculadas - Media: {mean:.4f}, Sigma: {np.sqrt(variance):.4f}")
            else:
                logger.warning(f"Datos vacíos para {self.plot_key} - Total de entradas es 0")
                data["mean"] = 0.0
                data["sigma"] = 0.0

            logger.info(f"Extracción completada para {self.plot_key}")
            return data
        except Exception as e:
            logger.exception(f"Error durante la extracción de datos: {e}")
            raise

    def _draw(self, ax: Axes, data: dict) -> None:
        logger.info(f"Iniciando dibujado del gráfico para {self.plot_key}")
        try:
            cfg = _PLOT_CONFIG.get(self.plot_key, _DEFAULT_CONFIG)
            logger.debug(f"Configuración aplicada: {self.plot_key}")

            if not data or data.get("values") is None or len(data.get("values", [])) == 0:
                logger.error(f"Datos vacíos o inválidos para dibujado en {self.plot_key}")
                raise ValueError("Los datos están vacíos")

            centers = (data["edges"][:-1] + data["edges"][1:]) / 2
            widths  = data["edges"][1:] - data["edges"][:-1]
            logger.debug(f"Dibujando {len(centers)} bins")

            ax.bar(
                centers,
                data["values"],
                width=widths,
                color=cfg["color"],
                alpha=0.75,
                linewidth=0.4,
                edgecolor="white",
            )

            # Línea de media
            if data["mean"] != 0.0:
                ax.axvline(
                    data["mean"],
                    color="black",
                    linewidth=1.2,
                    linestyle="--",
                    label=f"μ = {data['mean']:.2f}",
                )
                # Banda ± sigma
                ax.axvspan(
                    data["mean"] - data["sigma"],
                    data["mean"] + data["sigma"],
                    alpha=0.10,
                    color="black",
                    label=f"σ = {data['sigma']:.2f}",
                )
                logger.debug(f"Media y sigma dibujadas: μ={data['mean']:.4f}, σ={data['sigma']:.4f}")
                ax.legend(fontsize=8, framealpha=0.6)
            else:
                logger.warning(f"Media es 0 para {self.plot_key} - saltando líneas de media/sigma")

            ax.set_xlabel(data["xlabel"], fontsize=9)
            ax.set_ylabel(cfg["ylabel"], fontsize=9)
            ax.set_title(cfg["title"], fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=8)
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            
            logger.info(f"Gráfico {self.plot_key} dibujado exitosamente")
        except Exception as e:
            logger.exception(f"Error durante el dibujado del gráfico {self.plot_key}: {e}")
            raise


# ---------------------------------------------------------------------------
# Subclases ligeras — una por plot_key
# ---------------------------------------------------------------------------

class Threshold1DPlotter(Histogram1DPlotter):
    plot_key = "Threshold1D"

class Noise1DPlotter(Histogram1DPlotter):
    plot_key = "Noise1D"

class Occ1DPlotter(Histogram1DPlotter):
    plot_key = "Occ1D"

class ToT1DPlotter(Histogram1DPlotter):
    plot_key = "ToT1D"

class TDAC1DPlotter(Histogram1DPlotter):
    plot_key = "TDAC1D"

class ThrEqualizationPlotter(Histogram1DPlotter):
    plot_key = "ThrEqualization"