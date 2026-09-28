from __future__ import annotations
import os 
import glob
import logging
import re
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Any

try:
    import uproot
    UPROOT_AVAILABLE = True
except Exception:
    uproot = None  # type: ignore
    UPROOT_AVAILABLE = False

logger = logging.getLogger("FILES")



class FileSelectionError(Exception):
    """Custom exception for file selection errors."""
    pass


class ROOTFileHandler:
    """Class to handle ROOT files"""
    """ Open a directory and allows to open latests ROOT file or a specific one """

    def __init__(self, directory: str | Path, input_func: Callable[[str], str] = input):
        self.directory = Path(directory)
        self.input_func = input_func
        if not self.directory.exists() or not self.directory.is_dir():
            raise FileSelectionError(f"The directory {directory} does not exist or is not a directory.")
        logger.debug("Initialized ROOTFileHandler with directory: %s", self.directory)


    def _list_root_files(self) -> List[Path]:
        files = sorted(self.directory.glob("*.root"), key=os.path.getmtime)
        logger.debug("Found ROOT files: %s", files)
        return files

    def open_file(self, filename: Optional[str] = None) -> Tuple[object, str]:
        """
        Open a ROOT file. If filename is provided, open that specific file.
        If filename is None, open the latest modified file.
        
        Args:
            filename: Optional filename (not full path, just the name)
            
        Returns:
            Tuple of (uproot file object, full path as string)
            
        Raises:
            FileSelectionError: If file not found or no ROOT files in directory
        """
        if filename:
            # Open specific file
            file_path = self.directory / filename
            if not file_path.exists():
                raise FileSelectionError(f"ROOT file not found: {file_path}")
            return self._open_with_uproot(file_path), str(file_path)
        else:
            # Reuse _open_latest method
            return self._open_latest()
    
    def _open_latest(self) -> Tuple[object,str]:
        """Internal method to open the latest ROOT file."""
        files = self._list_root_files()
        if not files:
            raise FileSelectionError(f"No ROOT files found in directory {self.directory}.")
        newest_file = files[-1] 
        return self._open_with_uproot(newest_file), newest_file.name
    
    def select_open(self, index: Optional[int] = None) -> Tuple[object,str]:
        files = self._list_root_files()
        if not files:
            raise FileSelectionError(f"No ROOT files found in directory {self.directory}.")
        if index is None:
            print("Available ROOT files:")
            for i, file in enumerate(files, start=1):
                print(f"[{i}] {file.name}")
            while True:
                try: 
                    choice_str = self.input_func("Select a file by number: ")
                    choice = int(choice_str)
                    if 1 <= choice <= len(files):
                        selected_file = files[choice - 1]
                        logger.info("Opening selected ROOT file: %s", selected_file.name)
                        return self._open_with_uproot(selected_file), selected_file.name
                    else:
                        print(f"Please enter a number between 1 and {len(files)}.")
                except ValueError:
                    print("Invalid input. Please enter a valid number.")
        else:
            if not (1 <= index <= len(files)):
                raise FileSelectionError(f"Index {index} is out of range. There are {len(files)} files.")
            selected_file = files[index - 1]
            logger.info("Opening selected ROOT file: %s", selected_file.name)
            return self._open_with_uproot(selected_file), selected_file.name

    def _open_with_uproot(self, file_path: Path): 
        if not UPROOT_AVAILABLE:
            raise ImportError("uproot is not installed. Please install it to handle ROOT files.")
        logger.debug("Opening ROOT file with uproot: %s", file_path)
        return uproot.open(str(file_path))


class TxtFileHandler: 
    """Class to handle TXT files"""
    """ Open a directory and allows to open latests TXT file or a specific one """
    def __init__(self, directory: str | Path, input_func: Callable[[str], str] = input, encoding : str = 'utf-8'):
        self.directory = Path(directory)
        self.input_func = input_func
        self.encoding = encoding
        if not self.directory.exists() or not self.directory.is_dir():
            raise FileSelectionError(f"The directory {directory} does not exist or is not a directory.")
        logger.debug("Initialized TxtFileHandler with directory: %s", self.directory)
    
    def _list_txt_files(self) -> List[Path]:
        return sorted(self.directory.glob("*.txt"), key=os.path.getmtime)
    
    def open_file(self, filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Open a TXT file. If filename is provided, open that specific file.
        If filename is None, open the latest modified file.
        
        Args:
            filename: Optional filename (not full path, just the name)
            
        Returns:
            Tuple of (file path as string, filename)
            
        Raises:
            FileSelectionError: If file not found or no TXT files in directory
        """
        if filename:
            # Open specific file
            file_path = self.directory / filename
            if not file_path.exists():
                raise FileSelectionError(f"TXT file not found: {file_path}")
            logger.info("Opening specified TXT file: %s", filename)
            return str(file_path), filename
        else:
            # Reuse _open_latest method
            return self._open_latest()
    
    def _open_latest(self) -> Tuple[str, str]:
        """Internal method to open the latest TXT file."""
        files = self._list_txt_files()
        if not files:
            raise FileSelectionError(f"No TXT files found in directory {self.directory}.")
        newest_file = files[-1]
        logger.info("Opening latest TXT file: %s", newest_file.name)
        return str(newest_file), newest_file.name
    

    def select_open(self, index: Optional[int] = None) -> Tuple[Path, List[str]]:
        files = self._list_txt_files()
        if not files:
            raise FileSelectionError(f"No TXT files found in directory {self.directory}.")
        
        if index is None:
            print("Available TXT files:")
            for i, file in enumerate(files, start=1):
                print(f"[{i}] {file.name}")
            while True:
                try:
                    choice_str = self.input_func("Select a file by number: ")
                    choice = int(choice_str)
                    if 1 <= choice <= len(files):
                        selected_file = files[choice - 1]
                        logger.info("Opening selected TXT file: %s", selected_file.name)
                        return selected_file, self._read_file(selected_file)
                    else:
                        print(f"Please enter a number between 1 and {len(files)}.")
                except ValueError:
                    print("Invalid input. Please enter a valid number.")
        else: 
            if not (1 <= index <= len(files)):
                raise FileSelectionError(f"Index {index} is out of range. There are {len(files)} files.")
            selected_file = files[index - 1]
            logger.info("Opening selected TXT file: %s", selected_file.name)
            return selected_file, self._read_file(selected_file)

    def _read_file(self, file_path: Path) -> List[str]:
        with file_path.open(encoding=self.encoding) as f:
            return f.readlines()
        

class FileCreator: 

    def __init__(self, base_dir: str | Path | None = None, input_func: Callable[[str], str] = input):
        self.input_func = input_func
        self.base_dir = Path(base_dir) if base_dir else None

        if self.base_dir:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Initialized FileCreator with base directory: %s", self.base_dir)
        else: 
            logger.debug("Initialized FileCreator with no base directory.")
    
    def create_file(self, filename: str | None = None) -> Path:
        if not filename: 
            filename = self.input_func("Enter the name for the new file (with extension): ").strip()
        
        if not self.base_dir:
            file_path = Path(self.input_func("Enter the full path for the new file").strip())
            file_path.mkdir(parents=True, exist_ok=True)
        else: 
            file_path = self.base_dir / filename

        try: 
            file_path.touch(exist_ok=False)
            logger.info("Created new file: %s", file_path)
        except Exception as e: 
            logger.error("Error creating file %s: %s", file_path, e)
            raise FileSelectionError(f"Could not create file {file_path}: {e}")

        return file_path
    



class XMLFileHandler:
    """Class to handle XML files"""
    """Open a directory and allows to open latest XML file or a specific one"""
    
    def __init__(self, directory: str | Path, encoding: str = 'utf-8'):
        self.directory = Path(directory)
        self.encoding = encoding
        if not self.directory.exists() or not self.directory.is_dir():
            raise FileSelectionError(f"The directory {directory} does not exist or is not a directory.")
        logger.debug("Initialized XMLFileHandler with directory: %s", self.directory)
    
    def _list_xml_files(self) -> List[Path]:
        return sorted(self.directory.glob("*.xml"), key=os.path.getmtime)
    
    def open_file(self, filename: Optional[str] = None) -> Tuple[Path, Optional[float]]:
        """
        Open an XML file and extract Vthreshold_LIN. If filename is provided, open that specific file.
        If filename is None, open the latest modified file.
        
        Args:
            filename: Optional filename (not full path, just the name)
            
        Returns:
            Tuple of (file_path, vthreshold_value)
            vthreshold_value is None if not found
            
        Raises:
            FileSelectionError: If file not found or no XML files in directory
        """
        if filename:
            # Open specific file
            file_path = self.directory / filename
            if not file_path.exists():
                raise FileSelectionError(f"XML file not found: {file_path}")
            logger.info("Opening XML file: %s", file_path.name)
            vthreshold = self.extract_vthreshold(file_path)
            return file_path, vthreshold
        else:
            # Reuse _open_latest method
            return self._open_latest()
    
    def _open_latest(self) -> Tuple[Path, Optional[float]]:
        """
        Internal method to open the latest XML file and extract Vthreshold_LIN.
        
        Returns:
            Tuple of (file_path, vthreshold_value)
            vthreshold_value is None if not found
        """
        files = self._list_xml_files()
        if not files:
            raise FileSelectionError(f"No XML files found in directory {self.directory}.")
        newest_file = files[-1]
        logger.info("Opening latest XML file: %s", newest_file.name)
        vthreshold = self.extract_vthreshold(newest_file)
        return newest_file, vthreshold
    
    def extract_vthreshold(self, xml_path: Path) -> Optional[float]:
        """
        Extract Vthreshold_LIN value from XML configuration file.
        
        Args:
            xml_path: Path to the XML file
            
        Returns:
            Vthreshold_LIN value as float, or None if not found
        """
        try:
            with open(xml_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Search for Vthreshold_LIN = "value" pattern
            pattern = r'Vthreshold_LIN\s*=\s*["\'](\d+(?:\.\d+)?)["\']'
            match = re.search(pattern, content)
            
            if match:
                vthreshold = float(match.group(1))
                logger.info("Found Vthreshold_LIN = %s in %s", vthreshold, xml_path.name)
                return vthreshold
            else:
                logger.warning("Could not find Vthreshold_LIN in %s", xml_path.name)
                return None
        except Exception as e:
            logger.error("Error reading XML file %s: %s", xml_path, e)
            return None
    
    def extract_latency_config(self, xml_path: Path) -> tuple[Optional[int], Optional[int]]:
        """
        Extract LATENCY_CONFIG and nTRIGxEvent values from XML configuration file.
        
        Args:
            xml_path: Path to the XML file
            
        Returns:
            Tuple of (LATENCY_CONFIG, nTRIGxEvent) as integers, or (None, None) if not found
        """
        try:
            with open(xml_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Search for LATENCY_CONFIG = "value" pattern
            latency_pattern = r'LATENCY_CONFIG\s*=\s*["\'](\d+)["\']'
            latency_match = re.search(latency_pattern, content)
            
            # Search for nTRIGxEvent = "value" pattern
            ntrig_pattern = r'nTRIGxEvent\s*=\s*["\'](\d+)["\']'
            ntrig_match = re.search(ntrig_pattern, content)
            
            latency_config = int(latency_match.group(1)) if latency_match else None
            ntrig_event = int(ntrig_match.group(1)) if ntrig_match else None
            
            if latency_config is not None and ntrig_event is not None:
                logger.info("Found LATENCY_CONFIG = %d, nTRIGxEvent = %d in %s", 
                           latency_config, ntrig_event, xml_path.name)
            else:
                logger.warning("Could not find LATENCY_CONFIG or nTRIGxEvent in %s", xml_path.name)
            
            return latency_config, ntrig_event
            
        except Exception as e:
            logger.error("Error reading XML file %s: %s", xml_path, e)
            return None, None
    
    def update_latency_config(self, xml_path: Path, new_latency_config: int, new_ntrig_event: int) -> bool:
        """
        Update LATENCY_CONFIG and nTRIGxEvent values in XML configuration file.
        
        Args:
            xml_path: Path to the XML file
            new_latency_config: New value for LATENCY_CONFIG
            new_ntrig_event: New value for nTRIGxEvent
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            with open(xml_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Replace LATENCY_CONFIG value
            latency_pattern = r'(LATENCY_CONFIG\s*=\s*["\'])(\d+)(["\'])'
            content = re.sub(latency_pattern, rf'\g<1>{new_latency_config}\g<3>', content)
            
            # Replace nTRIGxEvent value
            ntrig_pattern = r'(nTRIGxEvent\s*=\s*["\'])(\d+)(["\'])'
            content = re.sub(ntrig_pattern, rf'\g<1>{new_ntrig_event}\g<3>', content)
            
            # Write back to file
            with open(xml_path, 'w', encoding=self.encoding) as f:
                f.write(content)
            
            logger.info("Updated %s: LATENCY_CONFIG = %d, nTRIGxEvent = %d", 
                       xml_path.name, new_latency_config, new_ntrig_event)
            return True
            
        except Exception as e:
            logger.error("Error updating XML file %s: %s", xml_path, e)
            return False
    
    def extract_column_range(self, xml_path: Path) -> tuple[Optional[int], Optional[int]]:
        """
        Extract COLstart and COLstop values from XML configuration file.
        
        Args:
            xml_path: Path to the XML file
            
        Returns:
            Tuple of (COLstart, COLstop) as integers, or (None, None) if not found
        """
        try:
            with open(xml_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Search for COLstart and COLstop in <Setting> tags
            colstart_pattern = r'<Setting\s+name\s*=\s*["\']COLstart["\']>\s*(\d+)\s*</Setting>'
            colstop_pattern = r'<Setting\s+name\s*=\s*["\']COLstop["\']>\s*(\d+)\s*</Setting>'
            
            colstart_match = re.search(colstart_pattern, content, re.IGNORECASE)
            colstop_match = re.search(colstop_pattern, content, re.IGNORECASE)
            
            colstart = int(colstart_match.group(1)) if colstart_match else None
            colstop = int(colstop_match.group(1)) if colstop_match else None
            
            if colstart is not None and colstop is not None:
                logger.info("Found COLstart = %d, COLstop = %d in %s", 
                           colstart, colstop, xml_path.name)
            else:
                logger.warning("Could not find COLstart or COLstop in %s", xml_path.name)
            
            return colstart, colstop
            
        except Exception as e:
            logger.error("Error reading XML file %s: %s", xml_path, e)
            return None, None


#  API export
__all__ = ["ROOTFileHandler", "TxtFileHandler", "XMLFileHandler", "FileSelectionError", "FileCreator"]