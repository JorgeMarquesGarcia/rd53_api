"""
Coincidence Plotter module for RD53A chip trajectory visualization.

Módulo para visualizar trayectorias de hits a través de múltiples planos
extraídos por HitAnalysis en 3D.
"""

from __future__ import annotations
import logging
import matplotlib.pyplot as plt
import matplotlib
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import awkward as ak
from pathlib import Path
from datetime import datetime
import time

matplotlib.use('Agg')  # Backend no-interactivo para contenedores

logger = logging.getLogger("COINCIDENCE_PLOTTER")

# Chip dimensions (Y x X)
NROWS = 192  # Y max (filas)
NCOLS = 400  # X max (columnas)


class CoincidencePlotter:
    """
    Clase para visualizar trayectorias de hits a través de 3 planos.
    Trabaja con datos awkward arrays procedentes de HitAnalysis.
    """

    def __init__(self, figsize=(12, 9), rows=NROWS, cols=NCOLS):
        """
        Inicializa el plotter 3D con 3 planos paralelos.
        
        Args:
            figsize: Tamaño de la figura (ancho, alto)
            rows: Número de filas por plano (NROWS = 192)
            cols: Número de columnas por plano (NCOLS = 400)
        """
        self.fig = plt.figure(figsize=figsize)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.rows = rows
        self.cols = cols
        self.trajectory_count = 0
        self.colors = plt.cm.tab20(np.linspace(0, 1, 20))  # 20 colores diferentes

        # Almacenar trayectorias para visualización
        self.trajectories = []

        # Configuración del plot 3D
        self._setup_3d_plot()

    def _setup_3d_plot(self):
        """Configura el aspecto inicial del plot 3D."""
        self.ax.set_xlabel('Columnas (X)', fontsize=11)
        self.ax.set_ylabel('Filas (Y)', fontsize=11)
        self.ax.set_zlabel('Plano (Z)', fontsize=11)
        self.ax.set_title('3D Coincidence Trajectories', fontsize=14, weight='bold')
        
        # Límites de los ejes
        self.ax.set_xlim(0, self.cols)
        self.ax.set_ylim(0, self.rows)
        self.ax.set_zlim(0, 3)  # 3 planos
        
        # Dibujar los planos como referencias (líneas de contorno)
        z_positions = [0.5, 1.5, 2.5]  # Posiciones de los 3 planos
        for z in z_positions:
            # Líneas de contorno en los planos
            x_corners = [0, self.cols, self.cols, 0, 0]
            y_corners = [0, 0, self.rows, self.rows, 0]
            z_corners = [z] * 5
            self.ax.plot(x_corners, y_corners, z_corners, 'k-', alpha=0.2, linewidth=0.5)

    def add_trajectory(self, plane1_coords, plane2_coords, plane3_coords):
        """
        Añade una trayectoria individual a través de los 3 planos en 3D.
        Maneja casos donde algunos planos pueden no tener datos (None).
        
        Args:
            plane1_coords: Tupla (row, col) en el plano 1 o None
            plane2_coords: Tupla (row, col) en el plano 2 o None
            plane3_coords: Tupla (row, col) en el plano 3 o None
        """
        self.trajectory_count += 1
        color = self.colors[self.trajectory_count % 20]
        
        # Recopilar puntos válidos
        all_coords = []
        z_positions_actual = []
        z_names = []
        z_positions = [0.5, 1.5, 2.5]
        
        if plane1_coords is not None:
            if 0 <= plane1_coords[0] < self.rows and 0 <= plane1_coords[1] < self.cols:
                all_coords.append(plane1_coords)
                z_positions_actual.append(z_positions[0])
                z_names.append("P1")
            else:
                logger.warning(f"Trayectoria {self.trajectory_count} P1{plane1_coords} fuera de límites")
        
        if plane2_coords is not None:
            if 0 <= plane2_coords[0] < self.rows and 0 <= plane2_coords[1] < self.cols:
                all_coords.append(plane2_coords)
                z_positions_actual.append(z_positions[1])
                z_names.append("P2")
            else:
                logger.warning(f"Trayectoria {self.trajectory_count} P2{plane2_coords} fuera de límites")
        
        if plane3_coords is not None:
            if 0 <= plane3_coords[0] < self.rows and 0 <= plane3_coords[1] < self.cols:
                all_coords.append(plane3_coords)
                z_positions_actual.append(z_positions[2])
                z_names.append("P3")
            else:
                logger.warning(f"Trayectoria {self.trajectory_count} P3{plane3_coords} fuera de límites")
        
        # Si no hay ningún punto válido, no hacer nada
        if len(all_coords) == 0:
            logger.warning(f"Trayectoria {self.trajectory_count} no tiene puntos válidos")
            self.trajectory_count -= 1
            return
        
        # Convertir a coordenadas 3D
        x_coords = [coord[1] for coord in all_coords]  # columnas (X)
        y_coords = [coord[0] for coord in all_coords]  # filas (Y)
        z_coords = z_positions_actual  # planos (Z)
        
        # Dibujar línea que conecta los puntos (trayectoria)
        if len(all_coords) > 1:
            self.ax.plot(x_coords, y_coords, z_coords, color=color, linewidth=2, 
                        label=f'Traj {self.trajectory_count}', zorder=2)
        
        # Dibujar puntos en cada plano
        self.ax.scatter(x_coords, y_coords, z_coords, s=100, c=[color]*len(all_coords), 
                       edgecolors='black', linewidth=1, zorder=3)
        
        # Guardar trayectoria
        self.trajectories.append({
            'plane1': plane1_coords,
            'plane2': plane2_coords,
            'plane3': plane3_coords,
            'color': color,
            'id': self.trajectory_count,
            'planes_with_data': z_names
        })

        # Actualizar figura
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def add_trajectories_from_awkward(self, awkward_data, delay: float = 1.0):
        """
        Añade múltiples trayectorias desde datos awkward array (formato de HitAnalysis).
        
        Interpreta los datos así:
        - RD53_frame_event_nhits [a, b, c]: número de hits en cada plano
        - RD53_hit_row y RD53_hit_col: coordenadas concatenadas
          * Primeros a elementos: plano 1
          * Siguientes b elementos: plano 2
          * Últimos c elementos: plano 3
        
        Args:
            awkward_data: Datos awkward array con campos RD53_hit_row, RD53_hit_col, RD53_frame_event_nhits
            delay: Tiempo en segundos entre trayectorias (default: 1.0s)
        """
        if len(awkward_data) == 0:
            logger.error("No hay datos para procesar (array vacío)")
            return

        total_events = len(awkward_data)
        logger.info(f"Procesando {total_events} eventos desde awkward array...")
        logger.info(f"Delay entre trayectorias: {delay}s")
        
        for event_idx in range(total_events):
            # Extraer datos del evento
            pixel_rows = awkward_data.RD53_hit_row[event_idx]
            pixel_cols = awkward_data.RD53_hit_col[event_idx]
            nhits = awkward_data.RD53_frame_event_nhits[event_idx]
            
            # Convertir awkward arrays a numpy
            pixel_rows = ak.to_numpy(pixel_rows)
            pixel_cols = ak.to_numpy(pixel_cols)
            nhits = ak.to_numpy(nhits)
            
            # Asegurar que son arrays
            if not isinstance(pixel_rows, np.ndarray):
                pixel_rows = np.array([pixel_rows])
            if not isinstance(pixel_cols, np.ndarray):
                pixel_cols = np.array([pixel_cols])
            if not isinstance(nhits, np.ndarray):
                nhits = np.array([nhits])
            
            logger.debug(f"  Evento {event_idx + 1}/{total_events}: nhits={nhits}, "
                        f"total hits={len(pixel_rows)}")
            
            # Extraer número de hits en cada plano
            if len(nhits) < 3:
                logger.debug(f"Evento {event_idx + 1}: nhits tiene {len(nhits)} componentes (esperado 3)")
                # Si solo tenemos 1 hit, asumimos que está en el plano 1
                if len(nhits) == 1 and nhits[0] > 0:
                    logger.debug(f"  -> Tratando como hit único en plano 1")
                continue
            
            n_plane1 = int(nhits[0])
            n_plane2 = int(nhits[1])
            n_plane3 = int(nhits[2])
            
            logger.debug(f"  Evento {event_idx + 1}: hits por plano: P1={n_plane1}, P2={n_plane2}, P3={n_plane3}")
            
            # Verificar que tenemos suficientes hits
            total_expected = n_plane1 + n_plane2 + n_plane3
            if len(pixel_rows) != total_expected:
                logger.warning(f"Evento {event_idx + 1}: número de hits no coincide. "
                             f"Esperado: {total_expected}, Obtenido: {len(pixel_rows)}")
                continue
            
            # Extraer coordenadas de cada plano
            # Dibujar si hay al menos 1 hit en cualquier plano
            total_hits = n_plane1 + n_plane2 + n_plane3
            if total_hits > 0:
                # Tomar el primer hit de cada plano (en caso de múltiples)
                # Si un plano no tiene hits, usar None
                plane1_coords = None
                plane2_coords = None
                plane3_coords = None
                
                if n_plane1 > 0:
                    plane1_coords = (int(pixel_rows[0]), int(pixel_cols[0]))
                
                if n_plane2 > 0:
                    plane2_coords = (int(pixel_rows[n_plane1]), int(pixel_cols[n_plane1]))
                
                if n_plane3 > 0:
                    plane3_coords = (int(pixel_rows[n_plane1 + n_plane2]), int(pixel_cols[n_plane1 + n_plane2]))
                
                logger.debug(f"    Trayectoria: P1{plane1_coords} -> P2{plane2_coords} -> P3{plane3_coords}")
                
                self.add_trajectory(plane1_coords, plane2_coords, plane3_coords)
                
                if delay > 0:
                    time.sleep(delay)
            else:
                logger.debug(f"    Evento {event_idx + 1} sin hits: "
                           f"P1={n_plane1}, P2={n_plane2}, P3={n_plane3}")

        logger.info(f"Procesamiento completado: {self.trajectory_count} trayectorias dibujadas")

    def save(self, output_dir: Path = None):
        """
        Guarda la figura en un archivo con timestamp.
        
        Args:
            output_dir: Directorio de salida. Si es None, usa rd53_api/plots
        """
        if output_dir is None:
            # Usar ruta por defecto relativa a este archivo
            output_dir = Path(__file__).parent.parent / "plots"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear nombre con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Coincidence_{timestamp}.png"
        filepath = output_dir / filename
        
        self.fig.suptitle(f'Coincidence Trajectories - {self.trajectory_count} trayectorias', 
                         fontsize=14, weight='bold')
        self.fig.tight_layout()
        self.fig.savefig(filepath, dpi=300, bbox_inches='tight')
        logger.info(f"Figura guardada en: {filepath}")
        
        return filepath

    def show(self, block=False):
        """Muestra la figura final. En contenedores, block=False (no-interactivo)."""
        plt.show(block=block)

    def close(self):
        """Cierra la figura."""
        plt.close(self.fig)


__all__ = [
    "CoincidencePlotter",
    "NROWS",
    "NCOLS"
]
