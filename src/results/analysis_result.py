"""Metadata classes for RD53A analysis results.

One base dataclass (AnalysisResult) plus four concrete subclasses,
one per analysis type: Hit, Latency, Noise, and a combined Acquisition
result that groups Hit + Noise together (matching AnalysisRunner logic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from scan_result import ScanResult


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AnalysisResult:
    """Outcome of processing a ROOT file produced by a scan.

    Attributes:
        success:         Whether the analysis completed without fatal errors.
        scan_result:     The ScanResult that originated the ROOT file.
        timestamp:       When the analysis finished (auto-set if None).
        runtime:         Wall-clock duration in seconds.
        stderr:          Any error or warning text captured during analysis.
        failed_metrics:  Names of metrics that could not be computed.
    """

    success: bool
    scan_result: ScanResult
    timestamp: datetime | None = None
    runtime: float = 0.0
    stderr: str = ""
    failed_metrics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Auto-assign timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def has_errors(self) -> bool:
        """Return True if the analysis failed or stderr is non-empty."""
        return not self.success or bool(self.stderr.strip())

    def has_failed_metrics(self) -> bool:
        """Return True if at least one metric could not be computed."""
        return bool(self.failed_metrics)

    def all_metrics_ok(self) -> bool:
        """Return True only when successful and every metric is present."""
        return self.success and not self.failed_metrics


# ---------------------------------------------------------------------------
# Hit analysis
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class HitAnalysisResult(AnalysisResult):
    """Metrics produced by HitAnalysis.

    Attributes:
        n_hits:          Total number of hits extracted from the ROOT file.
        n_tracks:        Number of reconstructed tracks (plot coordinates).
        hit_rate:        Hits per trigger (None if not computable).
        occupancy:       Mean pixel occupancy across the active matrix.
    """

    n_hits: int | None = None
    n_tracks: int | None = None
    hit_rate: float | None = None
    occupancy: float | None = None


# ---------------------------------------------------------------------------
# Latency analysis
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LatencyAnalysisResult(AnalysisResult):
    """Metrics produced by LatencyAnalysis.

    Attributes:
        chip_latency:    Mapping of chip identifier → optimal latency value.
        ntrig:           Number of triggers used in the scan.
        mean_latency:    Mean latency across all chips (None if not computable).
    """

    chip_latency: dict[str, int] = field(default_factory=dict)
    ntrig: int | None = None
    mean_latency: float | None = None

    def has_chip_latency(self) -> bool:
        """Return True if latency data was computed for at least one chip."""
        return bool(self.chip_latency)


# ---------------------------------------------------------------------------
# Noise analysis
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NoiseAnalysisResult(AnalysisResult):
    """Metrics produced by NoiseAnalysis.

    Attributes:
        n_noisy_pixels:  Number of pixels flagged as noisy.
        noisy_pixels:    List of (row, col) tuples for each noisy pixel.
        noise_rate:      Mean noise hit rate across the matrix.
    """

    n_noisy_pixels: int | None = None
    noisy_pixels: list[tuple[int, int]] = field(default_factory=list)
    noise_rate: float | None = None

    def has_noisy_pixels(self) -> bool:
        """Return True if at least one noisy pixel was detected."""
        return bool(self.noisy_pixels)


# ---------------------------------------------------------------------------
# Acquisition analysis  (Hit + Noise combined — mirrors AnalysisRunner)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AcquisitionAnalysisResult(AnalysisResult):
    """Combined result for an ACQUISITION run (HitAnalysis + NoiseAnalysis).

    Holds the individual sub-results rather than duplicating fields,
    keeping each analysis independently inspectable.

    Attributes:
        hit_result:   Result from HitAnalysis (None if not run).
        noise_result: Result from NoiseAnalysis (None if not run).
    """

    hit_result: HitAnalysisResult | None = None
    noise_result: NoiseAnalysisResult | None = None

    def has_hit_result(self) -> bool:
        """Return True if a HitAnalysisResult is present and successful."""
        return self.hit_result is not None and self.hit_result.success

    def has_noise_result(self) -> bool:
        """Return True if a NoiseAnalysisResult is present and successful."""
        return self.noise_result is not None and self.noise_result.success

    def n_noisy_pixels(self) -> int | None:
        """Shortcut to the noisy pixel count from the embedded noise result."""
        return self.noise_result.n_noisy_pixels if self.noise_result else None