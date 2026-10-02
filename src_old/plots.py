"""
Plotting module for RD53A chip pixel hit visualization.

This module provides functions to visualize pixel hits as heatmaps
based on TOT (Time Over Threshold) values.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')  # Backend para ventanas interactivas en Windows
import matplotlib.pyplot as plt
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("PLOTS")

# Chip dimensions (Y x X)
NROWS = 192  # Y max (filas)
NCOLS = 400  # X max (columnas)

class HeatmapPlotter:
    """
    Plotter 2D para visualizar hits del chip RD53A coloreados por TOT (0-14).
    Diseñado para trabajar con DataFrames que contienen datos del detector.
    """

    def __init__(self, figsize=(14, 7), rows=NROWS, cols=NCOLS):
        """
        Inicializa el plotter con las dimensiones del chip RD53A.
        
        Args:
            figsize: Tamaño de la figura (ancho, alto)
            rows: Número de filas (NROWS = 192)
            cols: Número de columnas (NCOLS = 400)
        """
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.rows = rows
        self.cols = cols
        self.hit_count = 0

        # Almacenar datos: usamos listas para coordenadas (col, row) y TOT
        self.x_hits = []  # columnas (RD53_hit_col)
        self.y_hits = []  # filas (RD53_hit_row)
        self.tot_hits = []  # TOT values

        # Configuración del plot
        self._setup_plot()
        plt.show(block=False)
        plt.pause(0.1)

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
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(0.001)

    def add_hits_from_dataframe(self, df_hits: pd.DataFrame, progressive: bool = False, 
                                delay: float = 0.1):
        """
        Añade múltiples hits desde un DataFrame.
        
        Args:
            df_hits: DataFrame con columnas 'RD53_hit_row', 'RD53_hit_col', 'RD53_hit_tot'
            progressive: Si True, dibuja cada hit uno por uno con delay.
                        Si False, añade todos los hits de golpe.
            delay: Tiempo entre hits si progressive=True (segundos)
        """
        total_events = len(df_hits)
        logger.info(f"Procesando {total_events} eventos del DataFrame...")
        
        for event_idx in range(total_events):
            # Extraer datos del evento
            pixel_rows = df_hits.RD53_hit_row.iloc[event_idx]
            pixel_cols = df_hits.RD53_hit_col.iloc[event_idx]
            tots = df_hits.RD53_hit_tot.iloc[event_idx]
            
            # Convertir a listas si es necesario
            if hasattr(pixel_rows, 'to_list'):
                pixel_rows = pixel_rows.to_list()
            if hasattr(pixel_cols, 'to_list'):
                pixel_cols = pixel_cols.to_list()
            if hasattr(tots, 'to_list'):
                tots = tots.to_list()
                
            # Asegurar que son listas
            if not isinstance(pixel_rows, (list, np.ndarray)):
                pixel_rows = [pixel_rows]
            if not isinstance(pixel_cols, (list, np.ndarray)):
                pixel_cols = [pixel_cols]
            if not isinstance(tots, (list, np.ndarray)):
                tots = [tots]
            
            logger.info(f"  Evento {event_idx + 1}/{total_events}: {len(pixel_rows)} hits")
            
            if progressive:
                # Modo progresivo: dibujar cada hit uno por uno
                for hit_idx, (row, col, tot) in enumerate(zip(pixel_rows, pixel_cols, tots)):
                    if pd.notna(row) and pd.notna(col) and pd.notna(tot):
                        if 0 <= row < self.rows and 0 <= col < self.cols:
                            self.add_hit(col, row, tot)
                            if delay > 0:
                                import time
                                time.sleep(delay)
            else:
                # Modo batch: añadir todos los hits del evento de golpe
                for row, col, tot in zip(pixel_rows, pixel_cols, tots):
                    if pd.notna(row) and pd.notna(col) and pd.notna(tot):
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
                    self.fig.canvas.draw()
                    self.fig.canvas.flush_events()
                    plt.pause(0.001)

    def save(self, save_path: Path):
        """Guarda la figura actual en un archivo."""
        self.fig.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {save_path}")

    def show(self, block=True):
        """Muestra la figura final."""
        plt.ioff()
        plt.show(block=block)

    def close(self):
        """Cierra la figura."""
        plt.close(self.fig)


class OccupancyMapPlotter:
    """
    Plotter 2D para visualizar mapa de ocupación del chip RD53A.
    Cada hit aparece como un punto de color (cicla entre 20 colores).
    Ideal para visualizar la distribución espacial de hits sin considerar TOT.
    """

    def __init__(self, figsize=(14, 7), rows=NROWS, cols=NCOLS):
        """
        Inicializa el plotter de ocupación con las dimensiones del chip RD53A.
        
        Args:
            figsize: Tamaño de la figura (ancho, alto)
            rows: Número de filas (NROWS = 192)
            cols: Número de columnas (NCOLS = 400)
        """
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=figsize)
        self.rows = rows
        self.cols = cols
        self.hit_count = 0

        # Colores para los hits (20 colores diferentes que se van ciclando)
        self.colors = [
            'darkblue', 'darkred', 'darkgreen', 'purple', 'darkorange',
            'teal', 'brown', 'pink', 'olive', 'cyan',
            'magenta', 'navy', 'maroon', 'lime', 'indigo',
            'coral', 'gold', 'crimson', 'steelblue', 'tomato'
        ]

        # Almacenar datos
        self.x_hits = []  # columnas (RD53_hit_col)
        self.y_hits = []  # filas (RD53_hit_row)
        self.hit_colors = []

        # Configuración del plot
        self._setup_plot()
        plt.show(block=False)
        plt.pause(0.1)

    def _setup_plot(self):
        """Configura el aspecto inicial del plot."""
        self.ax.set_xlim(0, self.cols)
        self.ax.set_ylim(0, self.rows)
        self.ax.set_xlabel('Columnas (X)', fontsize=12)
        self.ax.set_ylabel('Filas (Y)', fontsize=12)
        self.ax.set_title('Mapa de Ocupación RD53A (0 hits)', fontsize=14, weight='bold')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='box')

        # Inicializar scatter plot vacío
        self.scatter = self.ax.scatter([], [], s=50, alpha=0.7, edgecolors='black', linewidth=0.5)

    def add_hit(self, col: float, row: float):
        """
        Añade un hit individual al mapa de ocupación.
        
        Args:
            col: Columna (x) del hit (RD53_hit_col)
            row: Fila (y) del hit (RD53_hit_row)
        """
        self.hit_count += 1
        self.x_hits.append(col)
        self.y_hits.append(row)
        
        # Asignar color (cicla entre los 20 colores disponibles)
        color = self.colors[self.hit_count % len(self.colors)]
        self.hit_colors.append(color)

        # Actualizar el scatter plot con todos los puntos
        self.scatter.remove()
        self.scatter = self.ax.scatter(self.x_hits, self.y_hits, 
                                      c=self.hit_colors, s=50, 
                                      alpha=0.7, edgecolors='black', linewidth=0.5)

        # Actualizar título con contador
        self.ax.set_title(f'Mapa de Ocupación RD53A ({self.hit_count} hits)', 
                         fontsize=14, weight='bold')

        # Forzar actualización de la figura
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.pause(0.001)

    def add_hits_from_dataframe(self, df_hits: pd.DataFrame, progressive: bool = False, 
                                delay: float = 0.1, same_color_per_event: bool = True):
        """
        Añade múltiples hits desde un DataFrame.
        
        Args:
            df_hits: DataFrame con columnas 'RD53_hit_row', 'RD53_hit_col'
            progressive: Si True, dibuja cada hit uno por uno con delay.
                        Si False, añade todos los hits de golpe.
            delay: Tiempo entre hits si progressive=True (segundos)
            same_color_per_event: Si True, todos los hits del mismo evento tienen el mismo color.
                                 Si False, cada hit tiene un color diferente.
        """
        total_events = len(df_hits)
        logger.info(f"Procesando {total_events} eventos del DataFrame...")
        
        for event_idx in range(total_events):
            # Extraer datos del evento
            pixel_rows = df_hits.RD53_hit_row.iloc[event_idx]
            pixel_cols = df_hits.RD53_hit_col.iloc[event_idx]
            
            # Convertir a listas si es necesario
            if hasattr(pixel_rows, 'to_list'):
                pixel_rows = pixel_rows.to_list()
            if hasattr(pixel_cols, 'to_list'):
                pixel_cols = pixel_cols.to_list()
                
            # Asegurar que son listas
            if not isinstance(pixel_rows, (list, np.ndarray)):
                pixel_rows = [pixel_rows]
            if not isinstance(pixel_cols, (list, np.ndarray)):
                pixel_cols = [pixel_cols]
            
            logger.info(f"  Evento {event_idx + 1}/{total_events}: {len(pixel_rows)} hits")
            
            # Si queremos el mismo color para todos los hits del evento
            if same_color_per_event:
                event_color = self.colors[event_idx % len(self.colors)]
            
            if progressive:
                # Modo progresivo: dibujar cada hit uno por uno
                for hit_idx, (row, col) in enumerate(zip(pixel_rows, pixel_cols)):
                    if pd.notna(row) and pd.notna(col):
                        if 0 <= row < self.rows and 0 <= col < self.cols:
                            self.hit_count += 1
                            self.x_hits.append(col)
                            self.y_hits.append(row)
                            
                            if same_color_per_event:
                                self.hit_colors.append(event_color)
                            else:
                                color = self.colors[self.hit_count % len(self.colors)]
                                self.hit_colors.append(color)
                            
                            # Actualizar visualización
                            self.scatter.remove()
                            self.scatter = self.ax.scatter(self.x_hits, self.y_hits, 
                                                          c=self.hit_colors, s=50, 
                                                          alpha=0.7, edgecolors='black', linewidth=0.5)
                            self.ax.set_title(f'Mapa de Ocupación RD53A ({self.hit_count} hits)', 
                                            fontsize=14, weight='bold')
                            self.fig.canvas.draw()
                            self.fig.canvas.flush_events()
                            plt.pause(0.001)
                            
                            if delay > 0:
                                import time
                                time.sleep(delay)
            else:
                # Modo batch: añadir todos los hits del evento de golpe
                for row, col in zip(pixel_rows, pixel_cols):
                    if pd.notna(row) and pd.notna(col):
                        if 0 <= row < self.rows and 0 <= col < self.cols:
                            self.hit_count += 1
                            self.x_hits.append(col)
                            self.y_hits.append(row)
                            
                            if same_color_per_event:
                                self.hit_colors.append(event_color)
                            else:
                                color = self.colors[self.hit_count % len(self.colors)]
                                self.hit_colors.append(color)
                
                # Actualizar visualización una sola vez al final del evento
                if len(pixel_rows) > 0:
                    self.scatter.remove()
                    self.scatter = self.ax.scatter(self.x_hits, self.y_hits, 
                                                  c=self.hit_colors, s=50, 
                                                  alpha=0.7, edgecolors='black', linewidth=0.5)
                    self.ax.set_title(f'Mapa de Ocupación RD53A ({self.hit_count} hits)', 
                                     fontsize=14, weight='bold')
                    self.fig.canvas.draw()
                    self.fig.canvas.flush_events()
                    plt.pause(0.001)

    def save(self, save_path: Path):
        """Guarda la figura actual en un archivo."""
        self.fig.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {save_path}")

    def show(self, block=True):
        """Muestra la figura final."""
        plt.ioff()
        plt.show(block=block)

    def close(self):
        """Cierra la figura."""
        plt.close(self.fig)


def plot_hit_heatmap(
    df_hits: pd.DataFrame,
    rows: int = NROWS,
    cols: int = NCOLS,
    save_path: Optional[Path] = None,
    show: bool = True,
    title: str = "Mapa de Calor - Hits por Píxel (TOT)",
    progressive: bool = False,
    delay: float = 0.0
) -> None:
    """
    Genera un mapa de calor de los píxeles golpeados basado en TOT.
    
    Colores claros (amarillo) para TOT bajos, colores oscuros (azul) para TOT altos.
    
    Args:
        df_hits: DataFrame con columnas 'RD53_hit_row', 'RD53_hit_col', 'RD53_hit_tot'
        rows: Número de filas del detector (default: 192)
        cols: Número de columnas del detector (default: 400)
        save_path: Ruta donde guardar la figura (opcional)
        show: Si True, muestra la figura (default: True)
        title: Título del gráfico
        progressive: Si True, dibuja hits progresivamente (default: False)
        delay: Delay entre hits si progressive=True (default: 0.0s)
    """
    # Crear el plotter
    plotter = HeatmapPlotter(rows=rows, cols=cols)
    plotter.ax.set_title(title, fontsize=14, weight='bold')
    
    # Añadir hits desde el DataFrame
    plotter.add_hits_from_dataframe(df_hits, progressive=progressive, delay=delay)
    
    # Guardar si se especificó ruta
    if save_path:
        plotter.save(save_path)
    
    # Mostrar si se solicita
    if show:
        plotter.show(block=True)
    else:
        plotter.close()


def plot_occupancy_map(
    df_hits: pd.DataFrame,
    rows: int = NROWS,
    cols: int = NCOLS,
    save_path: Optional[Path] = None,
    show: bool = True,
    title: str = "Mapa de Ocupación - Distribución de Hits",
    progressive: bool = False,
    delay: float = 0.0,
    same_color_per_event: bool = True
) -> None:
    """
    Genera un mapa de ocupación mostrando la distribución espacial de hits.
    Cada hit aparece como un punto de color (sin considerar TOT).
    
    Args:
        df_hits: DataFrame con columnas 'RD53_hit_row', 'RD53_hit_col'
        rows: Número de filas del detector (default: 192)
        cols: Número de columnas del detector (default: 400)
        save_path: Ruta donde guardar la figura (opcional)
        show: Si True, muestra la figura (default: True)
        title: Título del gráfico
        progressive: Si True, dibuja hits progresivamente (default: False)
        delay: Delay entre hits si progressive=True (default: 0.0s)
        same_color_per_event: Si True, todos los hits del mismo evento tienen el mismo color
    """
    # Crear el plotter
    plotter = OccupancyMapPlotter(rows=rows, cols=cols)
    plotter.ax.set_title(title, fontsize=14, weight='bold')
    
    # Añadir hits desde el DataFrame
    plotter.add_hits_from_dataframe(df_hits, progressive=progressive, delay=delay,
                                    same_color_per_event=same_color_per_event)
    
    # Guardar si se especificó ruta
    if save_path:
        plotter.save(save_path)
    
    # Mostrar si se solicita
    if show:
        plotter.show(block=True)
    else:
        plotter.close()


def plot_streaming_update(
    df_hits: pd.DataFrame,
    plotter: Optional[HeatmapPlotter] = None,
    progressive: bool = False,
    delay: float = 0.1
) -> HeatmapPlotter:
    """
    Actualiza un heatmap existente con nuevos datos (para streaming en tiempo real).
    
    Si no se proporciona un plotter, crea uno nuevo.
    
    Args:
        df_hits: DataFrame con nuevos hits (columnas: RD53_hit_row, RD53_hit_col, RD53_hit_tot)
        plotter: HeatmapPlotter existente (opcional). Si es None, se crea uno nuevo.
        progressive: Si True, dibuja cada hit progresivamente (default: False)
        delay: Delay entre hits si progressive=True (default: 0.1s)
        
    Returns:
        HeatmapPlotter actualizado (para poder seguir añadiendo datos)
    """
    # Crear plotter si es la primera vez
    if plotter is None:
        plotter = HeatmapPlotter()
        logger.info("Nuevo HeatmapPlotter creado para streaming")
    
    # Añadir hits desde el DataFrame
    logger.info(f"Actualizando heatmap con {len(df_hits)} nuevos eventos")
    plotter.add_hits_from_dataframe(df_hits, progressive=progressive, delay=delay)
    
    return plotter


__all__ = [
    "HeatmapPlotter",
    "OccupancyMapPlotter",
    "plot_hit_heatmap",
    "plot_occupancy_map",
    "plot_streaming_update",
    "NROWS",
    "NCOLS"
]
