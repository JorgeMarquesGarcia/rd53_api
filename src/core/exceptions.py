from __future__ import annotations
from src.chip.detector_geometry import SENSOR_ROWS, SENSOR_COLS


##############################################################################
## Xml manager related exceptions
##############################################################################

class XmlManagerError(Exception):
    """Custom exception for XmlManager errors."""


class XmlFileNotFoundError(XmlManagerError):
    def __init__(self, file_path: str | None = None):
        if file_path:
            msg = f"XML file not found: '{file_path}'."
        else:
            msg = "No XML file path provided."
        super().__init__(msg)


class XmlParsingError(XmlManagerError):
    pass


class XmlNotLoadedError(XmlManagerError):
    def __init__(self):
        super().__init__("XML file is not loaded; operation cannot be performed.")


class XmlNodeNotFoundError(XmlManagerError):
    pass


class XmlAttributeNotFoundError(XmlManagerError):
    pass


class XmlStructureError(XmlManagerError):
    def __init__(self, details: str | None = None, hybrid_id: int | None = None,
                 rd53_id: int | None = None, attribute: str | None = None,
                 value: str | None = None):
        if hybrid_id is not None and rd53_id is not None and attribute is not None and value is not None:
            msg = f"Value '{value}' not acceptable for attribute '{attribute}' in RD53A Id='{rd53_id}' Hybrid Id='{hybrid_id}'"
        elif hybrid_id is not None and rd53_id is not None and attribute is not None:
            msg = f"Attribute '{attribute}' not found in RD53A Id='{rd53_id}' Hybrid Id='{hybrid_id}'"
        elif hybrid_id is not None and rd53_id is not None:
            msg = f"XML structure error in Hybrid Id='{hybrid_id}', RD53A Id='{rd53_id}': {details}"
        else:
            msg = f"XML structure error: {details}"
        super().__init__(msg)


class XmlPermissionError(XmlManagerError, PermissionError):
    """Escritura sobre un XML abierto en solo lectura (también es un PermissionError)."""

    def __init__(self):
        super().__init__("XML is opened in read-only mode. Modification is not allowed.")


class UnknownHybridError(XmlManagerError):
    def __init__(self, hybrid_id: int):
        super().__init__(f"Unknown Hybrid Id='{hybrid_id}'.")


class UnknownChipError(XmlManagerError):
    def __init__(self, rd53_id: int, hybrid_id: int | None = None):
        if hybrid_id is not None:
            msg = f"Unknown RD53A Id='{rd53_id}' in Hybrid Id='{hybrid_id}'."
        else:
            msg = f"Unknown RD53A Id='{rd53_id}'."
        super().__init__(msg)


class UnknownChipSettingError(XmlManagerError):
    def __init__(self, name: str, rd53_id: int, hybrid_id: int | None = None):
        if hybrid_id is not None:
            msg = f"Unknown chip setting '{name}' for RD53A Id='{rd53_id}' in Hybrid Id='{hybrid_id}'."
        else:
            msg = f"Unknown chip setting '{name}' for RD53A Id='{rd53_id}'."
        super().__init__(msg)


class UnknownCalibrationSettingError(XmlManagerError):
    def __init__(self, name: str):
        super().__init__(f"Unknown calibration setting '{name}'.")


class XmlUnsavedChangesError(XmlManagerError):
    def __init__(self):
        super().__init__("There are unsaved changes in the XML. Operation cannot be performed.")


##############################################################################
## Txt manager related exceptions
##############################################################################

class TxtManagerError(Exception):
    """Custom exception for TxtManager errors."""


class TxtFileNotFoundError(TxtManagerError):
    def __init__(self, file_path: str | None = None):
        if file_path:
            msg = f"TXT file not found: '{file_path}'."
        else:
            msg = "No TXT file path provided."
        super().__init__(msg)


class TxtNotLoadedError(TxtManagerError):
    def __init__(self):
        super().__init__("TXT file is not loaded; operation cannot be performed.")


class TxtInvalidPixelError(TxtManagerError):
    def __init__(self, row: int, col: int):
        super().__init__(f"Invalid pixel coordinates: row={row}, col={col}.")


class TxtInvalidNoisyPixelError(TxtManagerError):
    def __init__(self, details: str = ""):
        msg = "Invalid noisy pixel format; expected (row, col) pairs"
        super().__init__(f"{msg}: {details}" if details else f"{msg}.")


class TxtInvalidMaskError(TxtManagerError):
    def __init__(self, nrows: int | None = None, ncols: int | None = None):
        if nrows is not None and ncols is None:
            msg = f"Invalid mask dimensions: expected {SENSOR_ROWS} rows, got {nrows}."
        elif ncols is not None and nrows is None:
            msg = f"Invalid mask dimensions: expected {SENSOR_COLS} columns, got {ncols}."
        else:
            msg = (f"Invalid mask dimensions: expected {SENSOR_ROWS} rows and {SENSOR_COLS} "
                   f"columns, got {nrows} rows and {ncols} columns.")
        super().__init__(msg)


class TxtSaveNameRequiredError(TxtManagerError):
    def __init__(self):
        super().__init__("A name must be provided when using NEWFILE save mode.")


##############################################################################
## Terminal related exceptions
##############################################################################

class TerminalManagerError(Exception):
    """Custom exception for TerminalManager errors."""


class TerminalError(TerminalManagerError):
    """Base exception for terminal operations."""


class TerminalTimeOutError(TerminalManagerError):
    def __init__(self, cmd: str | None = None):
        if cmd is not None:
            msg = f"Command {cmd} timed out."
        else:
            msg = "Terminal operation timed out."
        super().__init__(msg)


class TerminalDeadError(TerminalManagerError):
    """Raised when the terminal process is dead."""


class TerminalCommandError(TerminalManagerError):
    """Raised when a terminal command detects a specific error."""

    def __init__(self, error_code: str, error_msg: str, output: str = ""):
        self.error_code = error_code
        self.error_msg = error_msg
        self.output = output
        super().__init__(f"{error_code}: {error_msg}")


##############################################################################
## ROOT file related exceptions
##############################################################################

class RootManagerError(Exception):
    """Handling Root Manager Errors"""


class RootFileNotFoundError(RootManagerError):
    pass


##############################################################################
## Noise analysis related exceptions
##############################################################################

class NoiseAnalysisError(Exception):
    """Handling Noise Analysis Errors"""


class NAnRootError(NoiseAnalysisError):
    pass


class NAnRootArraysError(NoiseAnalysisError):
    pass


class NAErrorEmptyData(NoiseAnalysisError):
    pass


class NAErrorNoHits(NoiseAnalysisError):
    pass


##############################################################################
## Latency analysis related exceptions
##############################################################################

class LatencyAnalysisError(Exception):
    """Handling Latency Analysis Errors"""


class LAnRootError(LatencyAnalysisError):
    pass


class LAnRootArraysError(LatencyAnalysisError):
    pass


class LAErrorEmptyData(LatencyAnalysisError):
    pass


##############################################################################
## Analysis related exceptions
##############################################################################

class AnalysisError(Exception):
    """Handling Analysis Errors"""
