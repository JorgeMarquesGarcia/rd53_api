"""Metadata class for RD53A orchestration cycle results.

One instance is produced per StateOrchestrator.run_once() call,
summarising the state transition and key metrics of that iteration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from workflow.system_state import SystemState


@dataclass(slots=True)
class OrchestrationResult:
    """High-level summary of one StateOrchestrator iteration.

    Captures the state transition, the outcome of the active phase
    (calibration, acquisition, or analysis), and the noisy-pixel
    counter that drives future state decisions.

    Attributes:
        start_state:     SystemState at the beginning of the iteration.
        end_state:       SystemState after the iteration completes.
        scan_ended:      True if the active scan reached its end-flag.
        n_noisy_pixels:  Noisy pixel count after analysis (or last known value).
        details:         Human-readable description of what happened.
        timestamp:       When the iteration finished (auto-set if None).
        success:         False if the iteration raised a handled error.
        error:           Error message if success is False, empty otherwise.
    """

    start_state: SystemState
    end_state: SystemState
    scan_ended: bool
    n_noisy_pixels: int
    details: str = ""
    timestamp: datetime | None = None
    success: bool = True
    error: str = ""

    def __post_init__(self) -> None:
        """Auto-assign timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def state_changed(self) -> bool:
        """Return True if the iteration triggered a state transition."""
        return self.start_state != self.end_state

    def has_errors(self) -> bool:
        """Return True if the iteration did not complete successfully."""
        return not self.success or bool(self.error.strip())

    def is_idle(self) -> bool:
        """Return True if the orchestrator ended in IDLE (graceful stop)."""
        return self.end_state == SystemState.IDLE

    def noise_within_limit(self) -> bool:
        """Return True if end_state is ACQUISITION, meaning noise passed the threshold check."""
        return self.end_state == SystemState.ACQUISITION