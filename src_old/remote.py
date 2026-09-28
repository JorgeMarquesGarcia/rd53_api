"""
Local execution module for AlmaLinux9 lab server.

This module handles local command execution on the lab server,
such as navigating to directories, listing contents, and launching programs.
"""

from __future__ import annotations
import logging
import subprocess
import platform
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger("LAUNCHER")

# Detect operating system
IS_WINDOWS = platform.system() == "Windows"


class ProgramLauncher:
    """
    Handles local command execution and program launching.
    """
    
    def __init__(self, working_directory: Optional[Path] = None):
        """
        Initialize program launcher.
        
        Args:
            working_directory: Default working directory for commands
        """
        self.working_directory = working_directory
        
    def execute_command(self, command: str, cwd: Optional[Path] = None) -> tuple[int, str, str]:
        """
        Execute a shell command locally.
        
        Args:
            command: Command to execute
            cwd: Working directory (uses default if not specified)
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        work_dir = cwd or self.working_directory
        
        try:
            logger.info("Executing command: %s", command)
            if work_dir:
                logger.info("Working directory: %s", work_dir)
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(work_dir) if work_dir else None,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("✓ Command executed successfully")
            else:
                logger.warning("Command exited with code %d", result.returncode)
            
            return (result.returncode, result.stdout, result.stderr)
            
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after 30 seconds")
            return (-1, "", "Command timed out")
        except Exception as e:
            logger.error("Error executing command: %s", e, exc_info=True)
            return (-1, "", str(e))
    
    def list_directory(self, path: Path) -> Optional[list[str]]:
        """
        List contents of a directory.
        
        Args:
            path: Path to the directory
            
        Returns:
            List of filenames/directories, or None if error
        """
        try:
            if not path.exists():
                logger.error("Directory does not exist: %s", path)
                return None
            
            if not path.is_dir():
                logger.error("Path is not a directory: %s", path)
                return None
            
            items = [item.name for item in path.iterdir()]
            items.sort()
            
            logger.info("Found %d items in %s", len(items), path)
            return items
            
        except Exception as e:
            logger.error("Error listing directory %s: %s", path, e, exc_info=True)
            return None
    
    def list_directory_detailed(self, path: Path) -> Optional[str]:
        """
        List contents of a directory with detailed information.
        Uses 'ls -lh' on Linux/Mac, 'dir' on Windows.
        
        Args:
            path: Path to the directory
            
        Returns:
            Detailed listing output, or None if error
        """
        if IS_WINDOWS:
            # Windows: use dir command
            command = f'dir "{path}"'
        else:
            # Linux/Mac: use ls command
            command = f"ls -lh {path}"
        
        exit_code, stdout, stderr = self.execute_command(command)
        
        if exit_code == 0:
            logger.info("Retrieved detailed listing of %s", path)
            return stdout
        else:
            logger.error("Failed to list directory %s: %s", path, stderr)
            return None
    
    def launch_program(
        self,
        program_path: str,
        args: Optional[list[str]] = None,
        cwd: Optional[Path] = None,
        background: bool = False
    ) -> tuple[int, str, str]:
        """
        Launch a program/script.
        
        Args:
            program_path: Path to the program/script to launch
            args: Command line arguments for the program
            cwd: Working directory (uses default if not specified)
            background: If True, run in background without waiting
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        command = program_path
        if args:
            command += " " + " ".join(args)
        
        if background:
            command += " &"
            logger.info("Launching program in background: %s", command)
        else:
            logger.info("Launching program: %s", command)
        
        return self.execute_command(command, cwd)


def test_directory_listing(target_path: str) -> bool:
    """
    Test directory listing functionality.
    
    Args:
        target_path: Path to list
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("=" * 60)
    logger.info("Testing directory listing")
    logger.info("=" * 60)
    
    launcher = ProgramLauncher()
    path = Path(target_path)
    
    # Simple listing
    logger.info("Listing contents of: %s", path)
    items = launcher.list_directory(path)
    
    if items:
        logger.info("Directory contents (%d items):", len(items))
        for item in items:
            logger.info("  - %s", item)
        
        # Detailed listing
        logger.info("\nDetailed listing:")
        detailed = launcher.list_directory_detailed(path)
        if detailed:
            print(detailed)
        
        return True
    else:
        logger.error("Failed to list directory")
        return False


def get_latest_raw_file(results_path: Path) -> Optional[Path]:
    """
    Find the latest .raw file in the Results directory.
    
    Args:
        results_path: Path to the Results directory
        
    Returns:
        Path to the latest .raw file, or None if not found
    """
    try:
        if not results_path.exists():
            logger.error("Results directory does not exist: %s", results_path)
            return None
        
        if not results_path.is_dir():
            logger.error("Path is not a directory: %s", results_path)
            return None
        
        # Get all .raw files
        raw_files = list(results_path.glob("*.raw"))
        
        if not raw_files:
            logger.warning("No .raw files found in %s", results_path)
            return None
        
        # Sort by modification time, newest first
        raw_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        latest_file = raw_files[0]
        logger.info("Found latest .raw file: %s", latest_file.name)
        logger.info("  Modified: %s", 
                   datetime.fromtimestamp(latest_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'))
        
        return latest_file
        
    except Exception as e:
        logger.error("Error finding latest .raw file: %s", e, exc_info=True)
        return None


def launch_cmsit_minidaq(
    base_dir: str = "/home/usuario/testing/CosmicRays/Ph2_ACF_6.15/RD53A_6.15",
    xml_config: str = "CMSIT_RD53A_test.xml",
    background: bool = True
) -> bool:
    """
    Launch CMSITminiDAQ with the latest .raw file from Results directory.
    
    Args:
        base_dir: Base directory containing the XML config and Results folder
        xml_config: Name of the XML configuration file
        background: If True, launch in background (default: True)
        
    Returns:
        True if launched successfully, False otherwise
    """
    logger.info("=" * 60)
    logger.info("Launching CMSITminiDAQ")
    logger.info("=" * 60)
    
    base_path = Path(base_dir)
    results_path = base_path / "Results"
    xml_path = base_path / xml_config
    
    # Check if base directory exists
    if not base_path.exists():
        logger.error("Base directory does not exist: %s", base_path)
        return False
    
    # Check if XML config exists
    if not xml_path.exists():
        logger.error("XML configuration file not found: %s", xml_path)
        return False
    
    # Find latest .raw file
    logger.info("Searching for latest .raw file in: %s", results_path)
    latest_raw = get_latest_raw_file(results_path)
    
    if not latest_raw:
        logger.error("No .raw file found to process")
        return False
    
    # Build relative path from base_dir
    relative_raw_path = f"Results/{latest_raw.name}"
    
    # Build command
    command = f"CMSITminiDAQ -f {xml_config} -b {relative_raw_path}"
    
    logger.info("Working directory: %s", base_path)
    logger.info("XML config: %s", xml_config)
    logger.info("RAW file: %s", relative_raw_path)
    logger.info("Command: %s", command)
    
    if background:
        logger.info("Launching in background...")
    
    # Execute command
    launcher = ProgramLauncher(working_directory=base_path)
    exit_code, stdout, stderr = launcher.launch_program(
        program_path=command,
        cwd=base_path,
        background=background
    )
    
    if exit_code == 0 or background:
        logger.info("✓ CMSITminiDAQ launched successfully")
        if stdout:
            logger.info("Output:\n%s", stdout)
        return True
    else:
        logger.error("✗ CMSITminiDAQ failed with exit code %d", exit_code)
        if stderr:
            logger.error("Error output:\n%s", stderr)
        return False


__all__ = [
    "ProgramLauncher",
    "test_directory_listing",
    "get_latest_raw_file",
    "launch_cmsit_minidaq",
]
