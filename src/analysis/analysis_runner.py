from __future__ import annotations
import logging


from rd53_api.config.root.root_manager import RootManager
from rd53_api.config.system_config import SystemConfig
from rd53_api.workflow.system_state import SystemState
from rd53_api.core.exceptions import AnalysisError
from rd53_api.analysis.analysis_noise import NoiseAnalysis
from rd53_api.analysis.analysis_hit import HitAnalysis
from rd53_api.results.analysis_result import AnalysisResult




class AnalysisRunner:
    """
    Coordina ejecución de análisis según estado del sistema.
    
    - CALIBRATION: NoiseAnalysis
    - ACQUISITION: HitAnalysis + NoiseAnalysis
    
    Attributes:
        n_noisy_pixels: Number of noisy pixels detected (key metric for state transitions)
    """
    
    def __init__(self, root_manager: RootManager):
        self.logger = logging.getLogger(__name__)
        self.config = SystemConfig()
        self.root_manager = root_manager
        self.noise_analysis: NoiseAnalysis | None = None
        self.hit_analysis: HitAnalysis | None = None
    
    def run(self) -> AnalysisResult:
        """
        Execute analysis based on current system state.
        
        Returns:
            AnalysisResult with noise_analysis, hit_analysis, and n_noisy_pixels
            
        Raises:
            AnalysisError: If system is not in a valid state for analysis
        """
        state = self.config.get_state()
        
        if state == SystemState.CALIBRATION:
            self._run_calibration_analysis()
        elif state == SystemState.ACQUISITION:
            self._run_acquisition_analysis()
        else:
            raise AnalysisError(f"Cannot run analysis in state: {state}")
        
        # Update SystemConfig with noisy pixels count for state transition decisions
        self.config.set_noisy_pixels(self.n_noisy_pixels)
        
        return self.results
    
    def _run_calibration_analysis(self) -> None:
        """Run noise analysis only (calibration mode)."""
        self.logger.info("Running calibration analysis (noise only)")
        self.noise_analysis = NoiseAnalysis(self.root_manager)
        self.hit_analysis = None
    
    def _run_acquisition_analysis(self) -> None:
        """Run both hit and noise analysis (acquisition mode)."""
        self.logger.info("Running acquisition analysis (hits + noise)")
        self.hit_analysis = HitAnalysis(self.root_manager)
        self.noise_analysis = NoiseAnalysis(self.root_manager)
    
    @property
    def n_noisy_pixels(self) -> int:
        """
        Number of noisy pixels detected.
        
        This is the key metric for state transition decisions:
        - High count → may require re-calibration
        - Low count → system healthy for acquisition
        """
        if self.noise_analysis is None:
            return 0
        return len(self.noise_analysis.noisy_pixels) if self.noise_analysis.noisy_pixels else 0
    
    @property
    def results(self) -> AnalysisResult:
        """Get complete analysis results."""
        return AnalysisResult(
            noise_analysis=self.noise_analysis,
            hit_analysis=self.hit_analysis,
            n_noisy_pixels=self.n_noisy_pixels
        )
