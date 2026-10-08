"""Plotter de SCurves.

Posible mejora futura: añadir la conversión a electrones en esta gráfica.
"""
from __future__ import annotations
import numpy as np
from matplotlib.axes import Axes
from src.plotter.plotter_base import PlotterBase
import logging
logger = logging.getLogger(__name__)


class SCurvePlotter(PlotterBase):
    """Plotter para el histograma SCurves del chip RD53A.

    El TH2F tiene:
        Eje X: ΔVCal  (50 bins)
        Eje Y: Efficiency (201 bins)
        Z:     Número de píxeles con esa eficiencia para ese ΔVCal

    Se dibuja como mapa de calor 2D con perfil medio, banda ±σ sombreada
    y barras de error ±σ en cada punto. Eje Y limitado a [0, 1].
    """

    plot_key = "SCurves"

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
            nx = len(data["xedges"]) - 1

            self.logger.debug(f"[{self.plot_key}] Calculando perfil para {nx} bins...")
            centers_y = (data["yedges"][:-1] + data["yedges"][1:]) / 2

            # Media y sigma ponderadas de cada columna (ΔVCal), todas a la vez
            weights       = data["values"]                       # (nx, ny)
            totals        = weights.sum(axis=1)
            profile_valid = totals > 0
            safe_totals   = np.where(profile_valid, totals, 1.0)
            profile_mean  = np.where(profile_valid, weights @ centers_y / safe_totals, 0.0)
            variance      = (weights * (centers_y[None, :] - profile_mean[:, None]) ** 2).sum(axis=1) / safe_totals
            profile_sigma = np.where(profile_valid, np.sqrt(np.maximum(variance, 0.0)), 0.0)

            data["centers_x"]     = (data["xedges"][:-1] + data["xedges"][1:]) / 2
            data["profile_mean"]  = profile_mean
            data["profile_sigma"] = profile_sigma
            data["profile_valid"] = profile_valid

            n_valid = profile_valid.sum()
            if n_valid == 0:
                self.logger.warning(f"[{self.plot_key}] No hay puntos válidos en el perfil")
            else:
                mean_mu = profile_mean[profile_valid].mean()
                mean_sigma = profile_sigma[profile_valid].mean()
                self.logger.info(f"[{self.plot_key}] Perfil calculado: {n_valid}/{nx} bins válidos. "
                                f"μ_medio={mean_mu:.4f}  σ_medio={mean_sigma:.4f}")
            
            f.Close()
            self.logger.info(f"[{self.plot_key}] Extracción completada exitosamente")
            return data
        except Exception as e:
            self.logger.exception(f"[{self.plot_key}] Error durante la extracción de datos: {e}")
            raise

    def _draw(self, ax: Axes, data: dict) -> None:
        self.logger.info("[SCurves] Iniciando dibujado del gráfico")
        try:
            if not data or data.get("values") is None or len(data.get("values", [])) == 0:
                self.logger.error("[SCurves] Datos vacíos o inválidos para dibujado")
                raise ValueError("Los datos están vacíos")

            self.logger.debug("[SCurves] Dibujando mapa de calor + perfil + dispersión...")

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
                n_valid = valid.sum()
                self.logger.debug(f"[SCurves] Dibujando perfil con {n_valid} puntos válidos")
                
                x     = data["centers_x"][valid]
                mean  = data["profile_mean"][valid]
                sigma = data["profile_sigma"][valid]

                # --- Banda ±σ sombreada ---
                ax.fill_between(
                    x,
                    np.clip(mean - sigma, 0, 1),
                    np.clip(mean + sigma, 0, 1),
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
                    label="Eficiencia media ± σ",
                    zorder=5,
                )

                ax.legend(fontsize=8, framealpha=0.7)
                self.logger.debug("[SCurves] Perfil e intervalo de confianza dibujados")
            else:
                self.logger.warning("[SCurves] No hay puntos válidos en el perfil para dibujar")

            # Eje Y limitado a [0, 1] — la eficiencia nunca puede ser > 1
            ax.set_ylim(0, 1)
            ax.set_xlabel(data["xlabel"] or "ΔVCal", fontsize=9)
            ax.set_ylabel(data["ylabel"] or "Efficiency", fontsize=9)
            ax.set_title("SCurves — Efficiency vs ΔVCal", fontsize=10, fontweight="bold")
            ax.tick_params(labelsize=8)
            ax.grid(linestyle="--", alpha=0.3)
            
            self.logger.info("[SCurves] Gráfico dibujado exitosamente")
        except Exception as e:
            self.logger.exception(f"[SCurves] Error durante el dibujado: {e}")
            raise