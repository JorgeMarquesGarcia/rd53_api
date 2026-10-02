"""
Physics analysis module for real-time RD53A data visualization.

Coordinates with remote_daq to generate ROOT files and visualize data progressively.
"""

import logging
from pathlib import Path
from typing import Optional
import time
import matplotlib.pyplot as plt
import numpy as np

from hit_accumulator import HitAccumulator
from plots import HeatmapPlotter, OccupancyMapPlotter
from files import ROOTFileHandler
from remote_daq import execute_cmsit_daq, find_latest_files, read_run_number

# ============================================================================
# CONFIGURATION FLAG: Set to True when working in the LAB, False for desktop
# ============================================================================
LAB_MODE = True  # Change to True when in the lab
# ============================================================================

# Path configuration based on mode
if LAB_MODE:
    # Lab environment (Linux)
    BASE_DIR = Path("/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A")
else:
    # Desktop environment (Windows)
    BASE_DIR = Path(__file__).parent.parent / "Data"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PhysicsMonitor:
    """
    Monitor que coordina remote_daq para generar archivos ROOT y visualizar datos en tiempo real.
    Acumula hits progresivamente y actualiza visualizaciones.
    """
    
    def __init__(self, base_dir: Path, plot_mode: str = "heatmap", verbose: bool = False):
        """
        Inicializa el monitor de física.
        
        Args:
            base_dir: Path al directorio base (contiene ConfigFiles/ y Results/)
            plot_mode: Tipo de visualización ("heatmap" o "occupancy")
            verbose: Si True, muestra salida detallada de remote_daq
        """
        self.base_dir = Path(base_dir)
        if not self.base_dir.exists():
            raise FileNotFoundError(f"Base directory not found: {self.base_dir}")
        
        self.results_dir = self.base_dir / "Results"
        if not self.results_dir.exists():
            raise FileNotFoundError(f"Results directory not found: {self.results_dir}")
        
        self.plot_mode = plot_mode
        self.verbose = verbose
        
        # Inicializar ROOTFileHandler
        self.root_handler = ROOTFileHandler(self.results_dir)
        logger.info("Initialized ROOTFileHandler for directory: %s", self.results_dir)
        
        # Inicializar acumulador de hits
        self.accumulator = HitAccumulator()
        
        # Inicializar plotter según el modo
        if plot_mode == "heatmap":
            self.plotter = HeatmapPlotter(figsize=(14, 7))
            logger.info("Initialized HeatmapPlotter (TOT-based coloring)")
        elif plot_mode == "occupancy":
            self.plotter = OccupancyMapPlotter(figsize=(14, 7))
            logger.info("Initialized OccupancyMapPlotter (event-based coloring)")
        else:
            raise ValueError(f"Invalid plot_mode: {plot_mode}. Use 'heatmap' or 'occupancy'")
        
        # Tracking de archivos procesados
        self.processed_files = set()
        self.last_processed_file = None
        
        # DAQ configuration (will be loaded on first iteration)
        self.xml_file = None
        self.raw_file = None
        self.current_run = None
        self.iteration = 1
        
        logger.info(f"PhysicsMonitor initialized. Base dir: {self.base_dir}")
    
    def find_latest_root_file(self) -> Optional[str]:
        """
        Busca el archivo .root más reciente en Results/ usando ROOTFileHandler.
        
        Returns:
            Nombre del archivo más reciente (solo nombre, no path) o None si no hay archivos
        """
        try:
            # ROOTFileHandler._list_root_files() devuelve lista ordenada por mtime
            root_files = self.root_handler._list_root_files()
            if not root_files:
                return None
            # Devolver solo el nombre del archivo más reciente
            return root_files[-1].name
        except Exception as e:
            logger.error(f"Error finding ROOT files: {e}")
            return None
    
    def load_and_accumulate(self, root_filename: str) -> int:
        """
        Carga datos del archivo ROOT y los acumula usando ROOTFileHandler.
        Filtra automáticamente por último evento para evitar duplicados.
        
        Args:
            root_filename: Nombre del archivo .root (solo nombre, no path completo)
            
        Returns:
            Número de hits nuevos añadidos
        """
        try:
            logger.info(f"Loading file: {root_filename}")
            
            # Abrir ROOT file usando ROOTFileHandler
            uproot_file, full_path = self.root_handler.open_file(filename=root_filename)
            
            # Usar append_from_uproot para extraer y acumular en un solo paso
            new_hits = self.accumulator.append_from_uproot(uproot_file)
            
            if new_hits == 0:
                logger.warning(f"No new hits added from {root_filename}")
            else:
                logger.info(f"Added {new_hits} new hits (total: {len(self.accumulator)})")
            
            return new_hits
            
        except Exception as e:
            logger.error(f"Error loading {root_filename}: {e}", exc_info=True)
            return 0
    
    def update_plot(self):
        """
        Actualiza el plot con los datos acumulados actuales.
        Maneja tanto valores escalares como listas/arrays de hits por evento.
        """
        try:
            df = self.accumulator.get_dataframe()
            
            if df.empty:
                logger.debug("No data to plot yet")
                return
            
            if self.plot_mode == "heatmap":
                # HeatmapPlotter: añadir hits progresivamente
                # Necesitamos "explotar" las columnas de listas para que cada hit sea una fila
                for _, row in df.iterrows():
                    cols = row['RD53_hit_col']
                    rows = row['RD53_hit_row']
                    tots = row['RD53_hit_tot']
                    
                    # Si son listas/arrays, iterar sobre ellos
                    if isinstance(cols, (list, np.ndarray)):
                        for col, row_val, tot in zip(cols, rows, tots):
                            self.plotter.add_hit(col=col, row=row_val, tot=tot)
                    else:
                        # Si son valores escalares, añadir directamente
                        self.plotter.add_hit(col=cols, row=rows, tot=tots)
            
            elif self.plot_mode == "occupancy":
                # OccupancyMapPlotter: añadir hits por evento
                for event in df['event'].unique():
                    event_hits = df[df['event'] == event]
                    # Aquí también necesitamos aplanar las listas
                    all_cols = []
                    all_rows = []
                    for _, row in event_hits.iterrows():
                        cols = row['RD53_hit_col']
                        rows = row['RD53_hit_row']
                        if isinstance(cols, (list, np.ndarray)):
                            all_cols.extend(cols)
                            all_rows.extend(rows)
                        else:
                            all_cols.append(cols)
                            all_rows.append(rows)
                    
                    self.plotter.add_event(
                        cols=np.array(all_cols),
                        rows=np.array(all_rows)
                    )
            
            plt.pause(0.1)
            
        except Exception as e:
            logger.error(f"Error updating plot: {e}", exc_info=True)
    
    def run_daq_cycle(self, max_iterations: Optional[int] = None):
        """
        Ciclo principal: lanza remote_daq, procesa ROOT generado, actualiza plot.
        Repite hasta que el usuario cancele (Ctrl+C) o alcance max_iterations.
        
        Args:
            max_iterations: Número máximo de iteraciones (None = infinito)
        """
        logger.info("="*60)
        logger.info("Starting Physics Monitor with Remote DAQ")
        logger.info("="*60)
        logger.info(f"Base directory: {self.base_dir}")
        logger.info(f"Plot mode: {self.plot_mode}")
        logger.info(f"Max iterations: {max_iterations if max_iterations else 'unlimited'}")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60)
        
        try:
            # Cargar configuración DAQ (solo una vez)
            self._load_daq_config()
            
            while True:
                # Check iteration limit
                if max_iterations is not None and self.iteration > max_iterations:
                    logger.info(f"Reached max_iterations ({max_iterations}). Stopping.")
                    break
                
                logger.info(f"\n--- Iteration {self.iteration} ---")
                
                # 1. Lanzar remote_daq para generar archivo ROOT
                output_file = self._run_daq_iteration()
                
                if output_file is None:
                    logger.error("Failed to generate ROOT file. Skipping iteration.")
                    self.iteration += 1
                    continue
                
                # 2. Procesar archivo ROOT generado
                new_hits = self.load_and_accumulate(output_file)
                
                # Si no hay nuevos hits, volver a paso 1 directamente
                if new_hits == 0:
                    logger.warning(f"No new hits in iteration {self.iteration}. Skipping to next iteration.")
                    self.iteration += 1
                    continue
                
                # Mostrar primeros 5 hits nuevos
                df = self.accumulator.get_dataframe()
                last_5_hits = df.tail(min(5, new_hits))
                logger.info("=" * 40)
                logger.info(f"First {min(5, new_hits)} new hits:")
                for idx, row in last_5_hits.iterrows():
                    logger.info(f"  Event {row['event']}: col={row['RD53_hit_col']}, row={row['RD53_hit_row']}, TOT={row['RD53_hit_tot']}")
                logger.info("=" * 40)
                
                # 3. Actualizar plot
                self.update_plot()
                
                # Tracking
                self.processed_files.add(output_file)
                self.last_processed_file = output_file
                
                logger.info(f"Iteration {self.iteration} complete. Total hits: {len(self.accumulator)}")
                
                self.iteration += 1
                
                # Sleep 1 second between iterations
                time.sleep(1)
                
                # Safety: stop at 99 iterations
                if self.iteration > 99:
                    logger.warning("Reached maximum iteration (99). Stopping.")
                    break
        
        except KeyboardInterrupt:
            logger.info("\n\nStopped by user (Ctrl+C)")
        
        finally:
            self.save_results()
            logger.info("="*60)
            logger.info(f"Physics Monitor finished after {self.iteration - 1} iterations")
            logger.info("="*60)
    
    def _load_daq_config(self):
        """Carga configuración DAQ (XML, RAW, run number) una sola vez."""
        logger.info("Loading DAQ configuration...")
        
        # Read run number
        self.current_run = read_run_number(self.base_dir)
        logger.info(f"Current run number: {self.current_run}")
        
        # Find latest input files
        self.xml_file, self.raw_file = find_latest_files(self.base_dir)
        logger.info(f"XML file: {self.xml_file}")
        logger.info(f"RAW file: {self.raw_file}")
    
    def _run_daq_iteration(self) -> Optional[str]:
        """
        Ejecuta una iteración de remote_daq y devuelve el nombre del archivo generado.
        
        Returns:
            Nombre del archivo ROOT generado, o None si falla
        """
        # Generate output filename
        output_file = f"Run{self.current_run}_{self.iteration:02d}.root"
        
        logger.info(f"Generating: {output_file}")
        
        # Execute CMSITminiDAQ
        return_code = execute_cmsit_daq(
            base_dir=self.base_dir,
            xml_file=self.xml_file,
            raw_file=self.raw_file,
            output_file=output_file,
            verbose=self.verbose
        )
        
        if return_code == 0:
            logger.info(f"✓ Successfully generated: {output_file}")
            return output_file
        else:
            logger.error(f"✗ Failed to generate {output_file} (return code: {return_code})")
            return None
    
    def process_single_file(self, root_filename: Optional[str] = None):
        """
        Procesa un único archivo ROOT y muestra el plot final.
        
        Args:
            root_filename: Nombre del archivo .root específico. Si None, usa el más reciente.
        """
        if root_filename is None:
            root_filename = self.find_latest_root_file()
            if root_filename is None:
                logger.error("No ROOT files found in Results/")
                return
        
        logger.info(f"Processing single file: {root_filename}")
        
        # Cargar y acumular
        self.load_and_accumulate(root_filename)
        
        # Actualizar plot
        self.update_plot()
        
        # Mostrar estadísticas
        stats = self.accumulator.get_statistics()
        logger.info("="*60)
        logger.info("STATISTICS:")
        logger.info(f"  Total events: {stats['total_events']}")
        logger.info(f"  Total hits: {stats['total_hits']}")
        logger.info(f"  Avg TOT: {stats['avg_tot']:.2f}")
        logger.info(f"  Event range: [{stats['first_event']}, {stats['last_event']}]")
        logger.info("="*60)
        
        plt.show(block=True)
    
    def save_results(self):
        """Guarda los resultados acumulados en CSV."""
        if len(self.accumulator) == 0:
            logger.warning("No data to save")
            return
        
        output_file = self.results_dir / "physics_accumulated_hits.csv"
        self.accumulator.save_to_file(output_file)
        logger.info(f"Saved accumulated hits to: {output_file}")


def run_physics_analysis(base_dir: Path, plot_mode: str = "heatmap", 
                        max_iterations: Optional[int] = None, verbose: bool = False):
    """
    Función principal: ejecuta remote_daq + visualización en tiempo real.
    
    Args:
        base_dir: Path al directorio base (contiene ConfigFiles/ y Results/)
        plot_mode: "heatmap" (TOT) o "occupancy" (eventos)
        max_iterations: Número máximo de iteraciones DAQ (None = infinito)
        verbose: Si True, muestra salida detallada de CMSITminiDAQ
    """
    monitor = PhysicsMonitor(
        base_dir=base_dir,
        plot_mode=plot_mode,
        verbose=verbose
    )
    
    monitor.run_daq_cycle(max_iterations=max_iterations)


def analyze_existing_file(base_dir: Path, root_filename: Optional[str] = None, 
                          plot_mode: str = "heatmap"):
    """
    Modo análisis: procesa un archivo ROOT existente sin ejecutar DAQ.
    
    Args:
        base_dir: Path al directorio base (contiene Results/)
        root_filename: Nombre del archivo específico (None = más reciente)
        plot_mode: "heatmap" (TOT) o "occupancy" (eventos)
    """
    monitor = PhysicsMonitor(
        base_dir=base_dir,
        plot_mode=plot_mode,
        verbose=False
    )
    
    monitor.process_single_file(root_filename=root_filename)


if __name__ == "__main__":
    """
    Ejemplo de uso standalone:
    
    # Modo DAQ + visualización en tiempo real:
    python physics.py
    
    # Análisis de archivo existente:
    python physics.py --analyze
    """
    import sys
    from cli import build_parser
    
    # Re-usar parser de cli.py y añadir opciones específicas
    parser = build_parser()
    parser.add_argument("--analyze", action="store_true", 
                       help="Analyze existing file without running DAQ")
    parser.add_argument("--plot-mode", choices=["heatmap", "occupancy"], 
                       default="heatmap", help="Visualization mode")
    parser.add_argument("--file", type=str, default=None,
                       help="Specific ROOT file to analyze (only with --analyze)")
    
    args = parser.parse_args()
    
    # Configurar logging según verbosidad
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validar que estamos en LAB_MODE si se ejecuta DAQ
    if not args.analyze and not LAB_MODE:
        logger.error("Physics DAQ mode is only available in LAB_MODE")
        logger.error("Set LAB_MODE = True in physics.py or use --analyze for desktop")
        sys.exit(1)
    
    # Usar directorio base configurado
    if not BASE_DIR.exists():
        logger.error(f"Base directory not found: {BASE_DIR}")
        logger.error(f"Current LAB_MODE: {LAB_MODE}")
        sys.exit(1)
    
    # Ejecutar según modo
    if args.analyze:
        logger.info("="*60)
        logger.info("ANALYZE MODE: Processing existing ROOT file")
        logger.info("="*60)
        analyze_existing_file(
            base_dir=BASE_DIR,
            root_filename=args.file,
            plot_mode=args.plot_mode
        )
    else:
        logger.info("="*60)
        logger.info("PHYSICS MODE: Running DAQ + Real-time visualization")
        logger.info("="*60)
        run_physics_analysis(
            base_dir=BASE_DIR,
            plot_mode=args.plot_mode,
            max_iterations=args.max_iterations,
            verbose=args.verbose
        )
