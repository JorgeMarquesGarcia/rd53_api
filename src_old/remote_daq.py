"""
Remote DAQ control for CMSITminiDAQ execution.
Generates .root files from .raw data.
"""

import subprocess
import logging
import sys
from pathlib import Path
from typing import Union, List, Tuple
from cli import build_parser

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Minimal logging for speed
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def read_run_number(base_dir: Path) -> str:
    """
    Read run number from RunNumber.txt file.
    
    Args:
        base_dir: Base directory containing RunNumber.txt
        
    Returns:
        Run number as 6-digit string (e.g., "000006")
    """
    run_number_file = base_dir / "RunNumber.txt"
    
    if not run_number_file.exists():
        raise FileNotFoundError(f"RunNumber.txt not found in {base_dir}")
    
    try:
        with open(run_number_file, 'r') as f:
            content = f.read().strip()
        
        # Ensure it's a valid number and format as 6 digits
        run_num = int(content)
        if run_num < 0 or run_num > 299:
            raise ValueError(f"Run number {run_num} out of range (0-299)")
        
        run_number_str = f"{run_num:06d}"
        return run_number_str
        
    except Exception as e:
        logger.error(f"Error reading RunNumber.txt: {e}")
        raise


def find_latest_files(base_dir: Path) -> Tuple[str, str]:
    """
    Find latest XML and RAW files.
    
    Args:
        base_dir: Base directory to search in
    Returns:
        Tuple of (xml_filename, raw_filename)
    """
    # Find latest XML
    xml_files = sorted(base_dir.glob("*.xml"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not xml_files:
        raise FileNotFoundError(f"No XML files found in {base_dir}")
    latest_xml = xml_files[0].name
    
    # Find latest RAW in Results subdirectory
    results_dir = base_dir / "Results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    
    raw_files = sorted(results_dir.glob("*.raw"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not raw_files:
        raise FileNotFoundError(f"No RAW files found in {results_dir}")
    latest_raw = raw_files[0].name
    
    return latest_xml, latest_raw


def execute_cmsit_daq(
    base_dir: Union[str, Path],
    xml_file: str,
    raw_file: str,
    output_file: str,
    verbose: bool = False
) -> int:
    """
    Execute CMSITminiDAQ command with enhanced debugging.
    
    Args:
        base_dir: Base directory (/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A)
        xml_file: XML filename (just the name, not full path)
        raw_file: RAW filename (just the name, in Results/)
        output_file: Output ROOT filename (just the name, will go to Results/)
        verbose: If True, print full command output
        
    Returns:
        Return code (0 for success)
    """
    base_dir = Path(base_dir)
    parent_dir = base_dir.parent
    
    # Verificar existencia de archivos y directorios
    logger.warning("=== Starting Pre-execution Checks ===")
    
    # Verificar directorios
    logger.warning(f"Base directory: {base_dir}")
    if not base_dir.exists():
        logger.error(f"Base directory does not exist: {base_dir}")
        return 1
        
    logger.warning(f"Parent directory: {parent_dir}")
    if not parent_dir.exists():
        logger.error(f"Parent directory does not exist: {parent_dir}")
        return 1
        
    # Verificar setup.sh
    setup_script = parent_dir / "setup.sh"
    logger.warning(f"Looking for setup script: {setup_script}")
    if not setup_script.exists():
        logger.error(f"setup.sh not found at: {setup_script}")
        return 1
    
    # Verificar archivos de entrada
    xml_path = base_dir / xml_file
    logger.warning(f"Checking XML file: {xml_path}")
    if not xml_path.exists():
        logger.error(f"XML file not found: {xml_path}")
        return 1
        
    raw_path = base_dir / "Results" / raw_file
    logger.warning(f"Checking RAW file: {raw_path}")
    if not raw_path.exists():
        logger.error(f"RAW file not found: {raw_path}")
        return 1
    
    # Verificar directorio de salida
    output_dir = base_dir / "Results"
    logger.warning(f"Checking output directory: {output_dir}")
    if not output_dir.exists():
        logger.error(f"Output directory does not exist: {output_dir}")
        return 1
    
    logger.warning("All pre-execution checks passed")
    
    # Build bash command with error capture
    commands = f"""
cd {parent_dir}
if [ ! -f setup.sh ]; then
    echo "ERROR: setup.sh not found"
    exit 1
fi

source setup.sh 2>&1
cd RD53A

if ! command -v CMSITminiDAQ &> /dev/null; then
    echo "ERROR: CMSITminiDAQ command not found"
    exit 1
fi

CMSITminiDAQ -f {xml_file} -b Results/{raw_file} -o Results/{output_file} 2>&1
"""
    
    logger.warning("=== Executing Command ===")
    logger.warning("Commands to execute:")
    logger.warning(commands)
    
    # Capturar tanto stdout como stderr para debugging
    process = subprocess.Popen(
        commands,
        shell=True,
        executable='/bin/bash',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Capturar la salida en tiempo real
    stdout, stderr = process.communicate()
    
    # Loggear la salida completa
    if stdout:
        logger.warning("=== Command Output ===")
        for line in stdout.splitlines():
            if verbose:
                print(line)  # Print to console if verbose
            logger.warning(f"STDOUT: {line}")
            
    if stderr:
        logger.warning("=== Error Output ===")
        for line in stderr.splitlines():
            if verbose:
                print(line, file=sys.stderr)  # Print to stderr if verbose
            logger.error(f"STDERR: {line}")
    
    return_code = process.returncode  # process.communicate() already waits for completion
    
    # Verificar si el archivo de salida se creó correctamente
    output_path = base_dir / "Results" / output_file
    if output_path.exists() and output_path.stat().st_size > 0:
        # Si el archivo existe y no está vacío, consideramos la operación exitosa
        return 0
    elif return_code != 0:
        logger.error(f"✗ Command failed with exit code: {return_code}")
    
    return return_code


def run_daq_iterations(
    base_dir: Union[str, Path],
    max_iterations: int = None,
    verbose: bool = False
) -> List[str]:
    """
    Run multiple DAQ iterations with optimized performance.
    
    Args:
        base_dir: Base directory (/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A)
        max_iterations: Number of iterations to run (None = infinite, 1-99 for limited)
        verbose: If True, show detailed output
        
    Returns:
        List of output filenames created
    """
    base_dir = Path(base_dir)
    
    # Validate iterations (if specified)
    if max_iterations is not None and (max_iterations < 1 or max_iterations > 99):
        raise ValueError(f"max_iterations must be between 1 and 99 or None (got {max_iterations})")
    
    # Read current run number (sin restar 1, ya que estamos en streaming del run actual)
    current_run = read_run_number(base_dir)
    
    # Find latest input files (only once)
    xml_file, raw_file = find_latest_files(base_dir)
    
    # Execute iterations
    output_files = []
    iteration = 1
    
    # Infinite loop if max_iterations is None, otherwise use range
    while True:
        # Check if we should stop (only if max_iterations is specified)
        if max_iterations is not None and iteration > max_iterations:
            break
        
        # Generate output filename using current run number
        output_file = f"Run{current_run}_{iteration:02d}.root"
        
        # Execute DAQ (no delay - runs as fast as possible)
        return_code = execute_cmsit_daq(
            base_dir=base_dir,
            xml_file=xml_file,
            raw_file=raw_file,
            output_file=output_file,
            verbose=verbose
        )
        
        if return_code == 0:
            output_files.append(output_file)
        
        iteration += 1
        
        # Safety check to prevent infinite filename growth beyond 99
        if iteration > 99:
            logger.warning("Reached maximum iteration number (99). Stopping.")
            break
    
    # Final summary (only show if verbose or errors)
    total_iterations = max_iterations if max_iterations is not None else iteration - 1
    if verbose or len(output_files) != total_iterations:
        logger.warning(f"Completed: {len(output_files)}/{total_iterations} iterations successful")
    
    return output_files


if __name__ == "__main__":
    # Import parser from cli module
    
    
    # Build parser and parse arguments
    parser = build_parser()
    args = parser.parse_args()
    
    # Default base directory for standalone execution
    base_dir = "/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A"
    
    try:
        output_files = run_daq_iterations(
            base_dir=base_dir,
            max_iterations=args.max_iterations,
            verbose=args.verbose
        )
        
        # Exit with success if at least one iteration succeeded
        exit(0 if output_files else 1)
        
    except KeyboardInterrupt:
        logger.warning("\n\nInterrupción por usuario (Ctrl+C)")
        exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
