"""
Plotting module for RD53A chip visualization.

Módulo para visualizar datos de hits extraídos por HitAnalysis.
"""

from __future__ import annotations
import logging
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import awkward as ak
from pathlib import Path

matplotlib.use('Agg')  # Backend no-interactivo para contenedores

logger = logging.getLogger("PLOTTER")

# Chip dimensions (Y x X)
NROWS = 192  # Y max (filas)
NCOLS = 400  # X max (columnas)


class Plotter:
    """
    Clase para visualizar hits del chip RD53A coloreados por TOT.
    Trabaja con datos awkward arrays procedentes de HitAnalysis.
    """

    def __init__(self, figsize=(14, 7), rows=NROWS, cols=NCOLS):
        """
        Inicializa el plotter con las dimensiones del chip RD53A.
        
        Args:
            figsize: Tamaño de la figura (ancho, alto)
            rows: Número de filas (NROWS = 192)
            cols: Número de columnas (NCOLS = 400)
        """
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.rows = rows
        self.cols = cols
        self.hit_count = 0

        # Almacenar datos: listas para coordenadas (col, row) y TOT
        self.x_hits = []  # columnas (RD53_hit_col)
        self.y_hits = []  # filas (RD53_hit_row)
        self.tot_hits = []  # TOT values

        # Configuración del plot
        self._setup_plot()

    def _setup_plot(self):
        """Configura el aspecto inicial del plot."""
        self.ax.set_xlim(0, self.cols)
        self.ax.set_ylim(0, self.rows)
        self.ax.set_xlabel('Columnas (X)', fontsize=12)
        self.ax.set_ylabel('Filas (Y)', fontsize=12)
        self.ax.set_title('Heatmap RD53A - TOT por Hit (0 hits)', fontsize=14, weight='bold')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='box')

        # Scatter vacío; usaremos viridis (claro->oscuro = bajo->alto TOT)
        self.scatter = self.ax.scatter([], [], c=[], cmap='viridis', vmin=0, vmax=14,
                                       s=30, alpha=0.9, edgecolors='black', linewidth=0.3)
        # Crear colorbar UNA SOLA VEZ al inicio (tamaño fijo)
        self.cbar = self.fig.colorbar(self.scatter, ax=self.ax, orientation='vertical', 
                                      pad=0.02, fraction=0.046)
        self.cbar.set_label('TOT (0-14)', fontsize=11)

    def add_hit(self, col: float, row: float, tot: int):
        """
        Añade un hit individual al heatmap.
        
        Args:
            col: Columna (x) del hit (RD53_hit_col)
            row: Fila (y) del hit (RD53_hit_row)
            tot: Valor TOT (0-14)
        """
        self.hit_count += 1
        self.x_hits.append(col)
        self.y_hits.append(row)
        self.tot_hits.append(int(tot))

        # Actualizar scatter (NO recreamos el colorbar para mantener tamaño fijo)
        self.scatter.remove()
        self.scatter = self.ax.scatter(self.x_hits, self.y_hits, c=self.tot_hits, cmap='viridis',
                                       vmin=0, vmax=14, s=30, alpha=0.9, edgecolors='black', linewidth=0.3)

        self.ax.set_title(f'Heatmap RD53A - TOT por Hit ({self.hit_count} hits)', 
                         fontsize=14, weight='bold')

    def add_hits_from_awkward(self, awkward_data, progressive: bool = False, delay: float = 0.1):
        """
        Añade múltiples hits desde datos awkward array (formato de HitAnalysis).
        
        Args:
            awkward_data: Datos awkward array con campos RD53_hit_row, RD53_hit_col, RD53_hit_tot
            progressive: Si True, dibuja cada hit uno por uno con delay.
                        Si False, añade todos los hits de golpe.
            delay: Tiempo entre hits si progressive=True (segundos)
        """
        import time
        
        total_events = len(awkward_data)
        logger.info(f"Procesando {total_events} eventos desde awkward array...")
        
        for event_idx in range(total_events):
            # Extraer datos del evento
            pixel_rows = awkward_data.RD53_hit_row[event_idx]
            pixel_cols = awkward_data.RD53_hit_col[event_idx]
            tots = awkward_data.RD53_hit_tot[event_idx]
            
            # Convertir awkward arrays a listas numpy
            pixel_rows = ak.to_numpy(pixel_rows)
            pixel_cols = ak.to_numpy(pixel_cols)
            tots = ak.to_numpy(tots)
            
            # Asegurar que son arrays
            if not isinstance(pixel_rows, np.ndarray):
                pixel_rows = np.array([pixel_rows])
            if not isinstance(pixel_cols, np.ndarray):
                pixel_cols = np.array([pixel_cols])
            if not isinstance(tots, np.ndarray):
                tots = np.array([tots])
            
            logger.info(f"  Evento {event_idx + 1}/{total_events}: {len(pixel_rows)} hits")
            
            if progressive:
                # Modo progresivo: dibujar cada hit uno por uno
                for hit_idx, (row, col, tot) in enumerate(zip(pixel_rows, pixel_cols, tots)):
                    if not np.isnan(row) and not np.isnan(col) and not np.isnan(tot):
                        if 0 <= row < self.rows and 0 <= col < self.cols:
                            self.add_hit(col, row, tot)
                            if delay > 0:
                                time.sleep(delay)
            else:
                # Modo batch: añadir todos los hits del evento de golpe
                for row, col, tot in zip(pixel_rows, pixel_cols, tots):
                    if not np.isnan(row) and not np.isnan(col) and not np.isnan(tot):
                        if 0 <= row < self.rows and 0 <= col < self.cols:
                            self.hit_count += 1
                            self.x_hits.append(col)
                            self.y_hits.append(row)
                            self.tot_hits.append(int(tot))
                
                # Actualizar visualización una sola vez al final del evento
                if len(pixel_rows) > 0:
                    self.scatter.remove()
                    self.scatter = self.ax.scatter(self.x_hits, self.y_hits, c=self.tot_hits, 
                                                   cmap='viridis', vmin=0, vmax=14, s=30, 
                                                   alpha=0.9, edgecolors='black', linewidth=0.3)
                    self.ax.set_title(f'Heatmap RD53A - TOT por Hit ({self.hit_count} hits)', 
                                     fontsize=14, weight='bold')

    def save(self, save_path: Path):
        """Guarda la figura actual en un archivo."""
        self.fig.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {save_path}")

    def show(self, block=False):
        """Muestra la figura final. En contenedores, block=False (no-interactivo)."""
        plt.show(block=block)

    def close(self):
        """Cierra la figura."""
        plt.close(self.fig)


__all__ = [
    "Plotter",
    "NROWS",
    "NCOLS"
]
