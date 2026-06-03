"""Metadata class for RD53A calibration and acquisition scan results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ScanResult:
    """Represents the outcome of a calibration or acquisition scan on an RD53A chip.

    Stores execution metadata, output paths, hardware identifiers, and
    captured stdout/stderr for post-run inspection and bookkeeping.
    """

    success: bool
    scan_name: str = ""
    timestamp: datetime | None = None
    root_path: Path | None = None
    raw_path: Path | None = None
    xml_path: Path | None = None
    runtime: float = 0.0
    stdout: str = ""
    stderr: str = ""
    run_number: int | None = None
    hybrid_id: int | None = None
    rd53_id: int | None = None

    def __post_init__(self) -> None:
        """Assign current UTC timestamp if none was provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def has_root_file(self) -> bool:
        """Return True if a ROOT output file path is set and the file exists."""
        return self.root_path is not None and self.root_path.exists()

    def has_raw_file(self) -> bool:
        """Return True if a raw data file path is set and the file exists."""
        return self.raw_path is not None and self.raw_path.exists()

    def has_errors(self) -> bool:
        """Return True if the scan failed or stderr contains any output."""
        return not self.success or bool(self.stderr.strip())