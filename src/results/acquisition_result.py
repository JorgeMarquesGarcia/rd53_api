"""Metadata class for RD53A acquisition scan results.

AcquisitionResult extends ScanResult with the acquisition-specific
fields: the list of chips involved and the user-configured scan time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from scan_result import ScanResult


@dataclass(slots=True)
class AcquisitionResult(ScanResult):
    """Outcome of a timed acquisition scan over one or more RD53A chips.

    Inherits all execution metadata from ScanResult and adds:

    Attributes:
        chips:     List of (hybrid_id, rd53_id) pairs that took part in the scan.
        scan_time: User-configured acquisition duration in seconds (-1 = unlimited).
        timed_out: True if the scan was stopped by the timeout rather than scan_time.
    """

    chips: list[tuple[int, int]] = field(default_factory=list)
    scan_time: int = 60
    timed_out: bool = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def n_chips(self) -> int:
        """Return the number of chips that participated in the acquisition."""
        return len(self.chips)

    def was_unlimited(self) -> bool:
        """Return True if the scan was launched without a time limit."""
        return self.scan_time == -1