from __future__ import annotations
from ..core.mask import NROWS, NCOLS


##############################################################################
## Xml manager related exceptions
###############################################################################

class XmlManagerError(Exception):
    """Custom exception for XmlManager errors."""
    pass

class XmlFileNotFoundError(XmlManagerError):
    def __init__(self, file_path: str):
        if file_path:
            msg = (f"XML file not found: '{file_path}'.")
        else: 
            msg = ("No XML file path provided.")
        super().__init__(msg)
    pass

class XmlParsingError(XmlManagerError):
    pass

class XmlNotLoadedError(XmlManagerError):
    def __init__(self):
        msg = "XML file is not loaded; operation cannot be performed."
        super().__init__(msg)
    pass

class XmlNodeNotFoundError(XmlManagerError):
    pass

class XmlAttributeNotFoundError(XmlManagerError):
    pass

class XmlStructureError(XmlManagerError):
    def __init__(self, details: str | None = None, hybrid_id: int | None = None, rd53_id: int | None = None, attribute: str | None = None, value: str | None = None):
        if hybrid_id is not None and rd53_id is not None and attribute is not None and value is not None:
            msg = f"Value '{value}' not acceptable for attribute '{attribute}' in RD53A Id='{rd53_id}' Hybrid Id='{hybrid_id}'"
        elif hybrid_id is not None and rd53_id is not None and attribute is not None and value is None:
            msg = f"Attribute '{attribute}' not found in RD53A Id='{rd53_id}' Hybrid Id='{hybrid_id}'"
        elif hybrid_id is not None and rd53_id is not None and attribute is None and value is None:
            msg = f"XML structure error in Hybrid Id='{hybrid_id}', RD53A Id='{rd53_id}': {details}"
        else:
            msg = f"XML structure error: {details}"
        super().__init__(msg)
    pass

class XmlPermissionError(XmlManagerError):
    def __init__(self):
        msg = "XML is opened in read-only mode. Modification is not allowed."
        super().__init__(msg)
    pass
class UnknownHybridError(XmlManagerError):
    def __init__(self, hybrid_id: int):
        msg = (f"Unknown Hybrid Id='{hybrid_id}'.")
        super().__init__(msg)
    pass

class UnknownChipError(XmlManagerError):
    def __init__(self, rd53_id: int, hybrid_id: int | None = None):
        if hybrid_id is not None:
            msg = (f"Unknown RD53A Id='{rd53_id}' in Hybrid Id='{hybrid_id}'.")
        else:
            msg = (f"Unknown RD53A Id='{rd53_id}'.")
        super().__init__(msg)
    pass

class UnknownChipSettingError(XmlManagerError):
    def __init__(self, name: str, rd53_id: int, hybrid_id: int | None = None):
        if hybrid_id is not None:
            msg = (f"Unknown chip setting '{name}' for RD53A Id='{rd53_id}' in Hybrid Id='{hybrid_id}'.")
        else:
            msg = (f"Unknown chip setting '{name}' for RD53A Id='{rd53_id}'.")
        super().__init__(msg)   
    pass

class UnknownCalibrationSettingError(XmlManagerError):
    def __init__(self, name: str):
        msg = (f"Unknown calibration setting '{name}'.")
        super().__init__(msg)   
    pass
class XmlUnsavedChangesError(XmlManagerError):
    def __init__(self):
        msg = "There are unsaved changes in the XML. Operation cannot be performed."
        super().__init__(msg)
    pass

##############################################################################
## Txt manager related exceptions
###############################################################################

class TxtManagerError(Exception):
    """Custom exception for TxtManager errors."""
    pass
    
class TxtFileNotFoundError(TxtManagerError):
    def __init__(self, file_path: str):
        if file_path:
            msg = (f"TXT file not found: '{file_path}'.")
        else: 
            msg = ("No TXT file path provided.")
        super().__init__(msg)
    pass

class TxtNotLoadedError(TxtManagerError):
    def __init__(self):
        msg = "TXT file is not loaded; operation cannot be performed."
        super().__init__(msg)
    pass

class  TxtInvalidPixelError(TxtManagerError):
    def __init__(self, row: int, col: int):
        msg = f"Invalid pixel coordinates: row={row}, col={col}."
        super().__init__(msg)
    pass

class TxtInvalidNoisyPixelError(TxtManagerError):
    def __init__(self):
        msg = "Invalid noisy pixel format:"
        super().__init__(msg)
    pass

class TxtInvalidMaskError(TxtManagerError):
    def __init__(self, nrows: int, ncols: int):
        if nrows is not None and ncols is None: 
            msg = f"Invalid mask dimensions: expected {NROWS} rows, got {nrows}."
        elif ncols is not None and nrows is None:
            msg = f"Invalid mask dimensions: expected {NCOLS} columns, got {ncols}."
        else:
            msg = f"Invalid mask dimensions: expected {NROWS} rows and {NCOLS} columns, got {nrows} rows and {ncols} columns."
        super().__init__(msg)
    pass

class TxtSaveNameRequiredError(TxtManagerError):
    def __init__(self):
        msg = "A name must be provided when using EXPLICIT save mode."
        super().__init__(msg)
    pass




##############################################################################
## Terminal related exceptions
###############################################################################

class TerminalManagerError(Exception):
    """Custom exception for TerminalManager errors."""
    pass

class TerminalError(TerminalManagerError):
    """Base exception for terminal operations."""
    pass


class TerminalTimeOutError(TerminalManagerError):
    def __init__(self, cmd: str | None):
        if cmd is not None:
            msg = f"Command {cmd} timed out."
        else: 
            msg = "Terminal operation timed out."
        super().__init__(msg)
    pass


class TerminalDeadError(TerminalManagerError):
    """Raised when the terminal process is dead."""
    pass


class TerminalCommandError(TerminalManagerError):
    """Raised when a terminal command detects a specific error."""
    def __init__(self, error_code: str, error_msg: str, output: str = ""):
        self.error_code = error_code
        self.error_msg = error_msg
        self.output = output
        msg = f"{error_code}: {error_msg}"
        super().__init__(msg)
    pass

##############################################################################
## ROOT file related exceptions ###############################################################################
##############################################################################


class RootManagerError(Exception): 
    """Handling Root Manager Errors"""    
    pass


class RootFileNotFoundError(RootManagerError):
    pass

#############################################################################
## Noise analysis related exceptions ############################################################################### ###############################################################################
#################################################################################

class NoiseAnalysisError(Exception):
    """Handling Noise Analysis Errors"""
    pass

class NAnRootError(NoiseAnalysisError):
    pass

class NAnRootArraysError(NoiseAnalysisError): 
    pass

class NAErrorEmptyData(NoiseAnalysisError):
    pass

class NAErrorNoHits(NoiseAnalysisError):
    pass

#############################################################################
## Latency analysis related exceptions ############################################################################### ###############################################################################
#################################################################################

class LatencyAnalysisError(Exception):
    """Handling Latency Analysis Errors"""
    pass

class LAnRootError(LatencyAnalysisError):
    pass

class LAnRootArraysError(LatencyAnalysisError):
    pass

class LAErrorEmptyData(LatencyAnalysisError):
    pass


##############################################################################
## Analysis related exceptions ###############################################################################
###############################################################################

class AnalysisError(Exception):
    """Handling Analysis Errors"""
    pass

