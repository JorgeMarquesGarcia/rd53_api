from __future__ import annotations
import logging
from pathlib import Path

from cli import parse_arguments
from files import ROOTFileHandler, TxtFileHandler, XMLFileHandler, FileSelectionError
from cal import run_calibration
from remote_daq import run_daq_iterations, hit_accumulator

# ============================================================================
# CONFIGURATION FLAG: Set to True when working in the LAB, False for desktop
# ============================================================================
LAB_MODE = True  # Change to True when in the lab
# ============================================================================

# ============================================================================
# EXAMPLE OF USAGE
# ============================================================================
"""
CALIBRATION MODE:
  python main.py --root Run000145_Physics_Board000.root --txt CMSIT_RD53A.txt --xml CMSIT_RD53A.xml --latency
  python main.py --root Run000145_Physics_Board000.root --txt CMSIT_RD53A.txt --xml CMSIT_RD53A.xml
  python main.py --root Run000145_Physics_Board000.root --txt CMSIT_RD53A.txt
  python main.py --root Run000145_Physics_Board000.root
  
  If no latency argument is given, latency scan is skipped
  If no xml, txt or root file is given, latest file in the folder is used

REMOTE DAQ MODE:
  python main.py --remote --max-iterations 10
  python main.py --remote --max-iterations 5 --verbose
"""
# ============================================================================

# Path configuration based on mode
if LAB_MODE:
    # Lab environment (Linux)
    ROOT_PATH = "/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A/Results"
    CONFIG_PATH = "/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A"
    REMOTE_BASE_DIR = "/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A"
else:
    # Desktop environment (Windows)
    ROOT_PATH = "C:\\Users\\jmarques\\Documents\\00_Projects\\02_TFM\\01_Lab\\Python\\Data"
    CONFIG_PATH = r"C:\\Users\\jmarques\\Documents\\00_Projects\\02_TFM\\01_Lab\\Python\\ConfigFiles"
    REMOTE_BASE_DIR = None  # Remote DAQ not available on desktop


# Configure logging (WARNING level for speed)
logging.basicConfig(
    level=logging.INFO,  # Changed from INFO to WARNING
    format="[%(levelname)s] %(message)s",  # Simplified format
)
logger = logging.getLogger("MAIN")


def main():
    """Main program entry point."""
    
    # Parse arguments
    args = parse_arguments()
    
    # ========================================================================
    # REMOTE DAQ MODE
    # ========================================================================
    if args.remote:
        if not LAB_MODE:
            logger.error("Remote DAQ mode is only available in LAB_MODE")
            logger.error("Set LAB_MODE = True in main.py")
            exit(1)
        
        logger.info("=" * 80)
        logger.info("REMOTE DAQ MODE")
        logger.info("=" * 80)
        
        try:
            output_files = run_daq_iterations(
                base_dir=REMOTE_BASE_DIR,
                max_iterations=args.max_iterations,
                verbose=args.verbose
            )
            
            logger.info("=" * 80)
            logger.info(f"Remote DAQ completed: {len(output_files)} files created")
            logger.info("=" * 80)
            
            # Guardar el plot final acumulado
            if len(hit_accumulator.events) > 0:
                from remote_daq import read_run_number
                
                # Guardar en la carpeta Plots del proyecto (donde está main.py)
                plots_dir = Path(__file__).parent / "Plots"
                plots_dir.mkdir(exist_ok=True)  # Crear carpeta si no existe
                
                current_run = read_run_number(Path(REMOTE_BASE_DIR))
                
                final_plot_path = plots_dir / f"Run{current_run}.png"
                hit_accumulator.save_final_plot(final_plot_path)
                logger.info(f"Final visualization saved: {final_plot_path}")
            
        except KeyboardInterrupt:
            logger.warning("\n\nRemote DAQ interrupted by user (Ctrl+C)")
            
            # Guardar el plot final incluso si se interrumpe
            if len(hit_accumulator.events) > 0:
                from remote_daq import read_run_number
                logger.info("Saving accumulated visualization...")
                
                # Guardar en la carpeta Plots del proyecto (donde está main.py)
                plots_dir = Path(__file__).parent / "Plots"
                plots_dir.mkdir(exist_ok=True)  # Crear carpeta si no existe
                
                current_run = read_run_number(Path(REMOTE_BASE_DIR))
                
                final_plot_path = plots_dir / f"Run{current_run}.png"
                hit_accumulator.save_final_plot(final_plot_path)
                logger.info(f"Visualization saved after interruption: {final_plot_path}")
            
        except Exception as e:
            logger.error(f"Remote DAQ failed: {e}", exc_info=True)
            exit(1)
        
        return
    
    # ========================================================================
    # CALIBRATION MODE (default)
    # ========================================================================
    
    logger.info("=" * 80)
    logger.info("CALIBRATION MODE")
    logger.info("=" * 80)
    
    # Open ROOT file
    roothandler = ROOTFileHandler(ROOT_PATH)
    try:
        root_file_select, filename_select = roothandler.open_file(args.root)
    except FileSelectionError as e:
        logger.error(str(e))
        exit(1)
    
    # Open TXT config file
    txthandler = TxtFileHandler(CONFIG_PATH)
    try:
        txt_file_select, txt_filename_select = txthandler.open_file(args.txt)
    except FileSelectionError as e:
        logger.error(str(e))
        exit(1)
    
    # Open XML config file and extract Vthreshold_LIN
    xmlhandler = XMLFileHandler(CONFIG_PATH)
    try:
        xml_file, Vthreshold_LIN = xmlhandler.open_file(args.xml)
        if Vthreshold_LIN is None:
            logger.error("Could not extract Vthreshold_LIN from XML file")
            exit(1)
        logger.info(f"Using Vthreshold_LIN from XML file: {Vthreshold_LIN}")
    except FileSelectionError as e:
        logger.error(f"No XML file found: {e}")
        exit(1)
    
    # Run calibration procedure
    run_calibration(
        root_file_object=root_file_select,
        root_filename=filename_select,
        txt_file_path=txt_file_select,
        vthreshold_lin=Vthreshold_LIN,
        xml_file_path=xml_file,
        perform_latency_scan=args.latency
    )
    
    logger.info("=" * 80)
    logger.info("Program finished successfully!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()


