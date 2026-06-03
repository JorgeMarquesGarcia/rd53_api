from __future__ import annotations
import numpy as np
from matplotlib.axes import Axes
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from rd53_api.plotter.plotter_base import PlotterBase

# ---------------------------------------------------------------------------
# Configuración visual por figura
# ---------------------------------------------------------------------------
_PLOT_CONFIG: dict[str, dict] = {
    "PixelAlive": {
        "cmap":  "viridis",
        "label": "Occupancy",
        "title": "Pixel Alive Map",
        "mask_inactive": True,
    },
    "ToT2D": {
        "cmap":  "plasma",
        "label": "ToT (a.u.)",
        "title": "ToT 2D",
        "mask_inactive": True,
    },
    "Threshold2D": {
        "cmap":  "coolwarm",
        "label": "Threshold (ΔVCal)",
        "title": "Threshold Map",
        "mask_inactive": False,
    },
    "Noise2D": {
        "cmap":  "hot",
        "label": "Noise (ΔVCal)",
        "title": "Noise Map",
        "mask_inactive": False,
    },
    "TDAC2D": {
        "cmap":  "RdYlGn",
        "label": "TDAC",
        "title": "TDAC Map",
        "mask_inactive": True,
    },
    "Masked2D": {
        "cmap":  "Reds",
        "label": "Masked",
        "title": "Masked Pixels",
        "mask_inactive": True,
    },
}

_DEFAULT_CONFIG = {
    "cmap":  "viridis",
    "label": "Value",
    "title": "2D Map",
    "mask_inactive": False,
}

# Columnas activas por defecto — se sobreescriben desde SystemConfig en producción
_DEFAULT_COL_START = 128
_DEFAULT_COL_END   = 263


class HeatmapPlotter(PlotterBase):
    """Plotter genérico para histogramas TH2F de Column vs Row del chip RD53A.

    Para figuras con mask_inactive=True, las columnas fuera del rango activo
    se dejan sin colorear (fondo blanco/gris), aplicando el colormap solo
    en la región activa.
    """

    plot_key: str = ""

    def __init__(self, root_path: str, canvas_path: str,
                 col_start: int = _DEFAULT_COL_START,
                 col_end:   int = _DEFAULT_COL_END):
        super().__init__(root_path, canvas_path)
        self.col_start = col_start
        self.col_end   = col_end

    def _extract(self) -> dict:
        self.logger.info(f"[{self.plot_key}] Iniciando extracción de datos")
        try:
            self.logger.info(f"[{self.plot_key}] Abriendo canvas ROOT...")
            f, canvas = self._open_canvas()
            self.logger.debug(f"[{self.plot_key}] Canvas abierto exitosamente")
            
            self.logger.debug(f"[{self.plot_key}] Buscando primitiva TH2...")
            h = self._get_primitive(canvas, "TH2")
            if h is None:
                self.logger.error(f"[{self.plot_key}] No se encontró TH2 en el canvas '{self.canvas_path}'")
                f.Close()
                raise ValueError(f"No se encontró TH2 en el canvas '{self.canvas_path}'")
            
            self.logger.debug(f"[{self.plot_key}] TH2 encontrado: {h.GetName()} ({h.GetNbinsX()}x{h.GetNbinsY()} bins)")
            data = self._th2_to_dict(h)
            f.Close()
            self.logger.info(f"[{self.plot_key}] Extracción TH2 completada exitosamente")
            return data
        except Exception as e:
            self.logger.exception(f"[{self.plot_key}] Error durante la extracción de datos: {e}")
            raise

    def _draw(self, ax: Axes, data: dict) -> None:
        self.logger.info(f"[{self.plot_key}] Iniciando dibujado del gráfico")
        try:
            cfg = _PLOT_CONFIG.get(self.plot_key, _DEFAULT_CONFIG)
            self.logger.debug(f"[{self.plot_key}] Configuración aplicada - cmap='{cfg['cmap']}', mask_inactive={cfg['mask_inactive']}")

            if not data or data.get("values") is None or len(data.get("values", [])) == 0:
                self.logger.error(f"[{self.plot_key}] Datos vacíos o inválidos para dibujado")
                raise ValueError("Los datos están vacíos")

            values = data["values"]      # shape (nx, ny) = (400, 192)
            xedges = data["xedges"]
            yedges = data["yedges"]

            if cfg["mask_inactive"]:
                self.logger.debug(f"[{self.plot_key}] Aplicando máscara de columnas inactivas")
                # Crear array enmascarado: NaN fuera de la región activa
                masked = np.full_like(values, np.nan, dtype=float)
                # Encontrar índices de columnas activas
                col_centers = (xedges[:-1] + xedges[1:]) / 2
                active_mask = (col_centers >= self.col_start) & (col_centers <= self.col_end)
                masked[active_mask, :] = values[active_mask, :]

                # Fondo gris para columnas inactivas
                ax.set_facecolor("#E0E0E0")

                # Dibujar solo la región activa
                vmin = values[active_mask, :].min() if active_mask.any() else 0
                vmax = values[active_mask, :].max() if active_mask.any() else 1
                self.logger.debug(f"[{self.plot_key}] Región activa cols {self.col_start}-{self.col_end} | vmin={vmin:.2f} vmax={vmax:.2f}")

                mesh = ax.pcolormesh(
                    xedges, yedges, masked.T,
                    cmap=cfg["cmap"],
                    shading="flat",
                    vmin=vmin,
                    vmax=vmax,
                )

                # Líneas verticales marcando el límite de la región activa
                ax.axvline(self.col_start, color="black", linewidth=0.8,
                           linestyle="--", alpha=0.6, label=f"Col {self.col_start}")
                ax.axvline(self.col_end,   color="black", linewidth=0.8,
                           linestyle="--", alpha=0.6, label=f"Col {self.col_end}")
                self.logger.debug(f"[{self.plot_key}] Líneas de límites dibujadas")
            else:
                mesh = ax.pcolormesh(
                    xedges, yedges, values.T,
                    cmap=cfg["cmap"],
                    shading="flat",
                )

            cbar = self._figure.colorbar(mesh, ax=ax)
            cbar.set_label(cfg["label"], fontsize=9)
            ax.set_xlabel(data["xlabel"] or "Column", fontsize=9)
            ax.set_ylabel(data["ylabel"] or "Row", fontsize=9)
            ax.set_title(cfg["title"], fontsize=10, fontweight="bold")
            ax.set_aspect("auto")
            ax.tick_params(labelsize=8)
            
            self.logger.info(f"[{self.plot_key}] Gráfico dibujado exitosamente")
        except Exception as e:
            self.logger.exception(f"[{self.plot_key}] Error durante el dibujado: {e}")
            raise


# ---------------------------------------------------------------------------
# Subclases ligeras — una por plot_key
# ---------------------------------------------------------------------------

class PixelAlivePlotter(HeatmapPlotter):
    plot_key = "PixelAlive"

class ToT2DPlotter(HeatmapPlotter):
    plot_key = "ToT2D"

class Threshold2DPlotter(HeatmapPlotter):
    plot_key = "Threshold2D"

class Noise2DPlotter(HeatmapPlotter):
    plot_key = "Noise2D"

class TDAC2DPlotter(HeatmapPlotter):
    plot_key = "TDAC2D"

class Masked2DPlotter(HeatmapPlotter):
    plot_key = "Masked2D"