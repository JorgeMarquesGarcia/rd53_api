from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any, Optional
import logging

from src.analysis.analysis_hit import HitAnalysis
from src.analysis.analysis_noise import NoiseAnalysis
from src.calibration.scans.noise import NoiseScan
from src.calibration.scans.scurve import SCurveScan
from src.calibration.scans.threqu import ThresholdEqualizationScan
from src.config.system_config import SystemConfig
from src.workflow.system_state import SystemState
from src.results.orchestration_result import OrchestrationResult


@dataclass
class CalibrationStep:
    """Define un paso de calibración en la secuencia."""
    name: str
    scan_cls: type
    scan_kwargs: Optional[dict[str, Any]] = None


class StateOrchestrator:
    """
    Orquestador de alto nivel.

    Responsabilidades:
    - Ejecutar pasos de calibración en orden.
    - Ejecutar el callback de adquisición.
    - Ejecutar análisis y actualizar contadores de píxeles ruidosos.
    - Disparar transiciones de estado según las reglas de SystemConfig.

    Atributos públicos tras run() en estado ACQUISITION:
        last_hit_analysis : HitAnalysis | None
            Instancia del último análisis de hits ejecutado.
            Contiene plot_coord con las trayectorias reconstruidas.
            None si el último ciclo fue de calibración o no se ha ejecutado análisis.
    """

    def __init__(
        self,
        calibration_sequence: Optional[list[CalibrationStep]] = None,
        acquisition_executor: Optional[Callable[[], bool]] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self._calibration_sequence = calibration_sequence or self._default_calibration_sequence()
        self._acquisition_executor = acquisition_executor
        self._calibration_step_idx = 0
        self._last_operational_state: Optional[SystemState] = None

        # Resultado del último HitAnalysis — accesible para plotters externos
        self.last_hit_analysis: Optional[HitAnalysis] = None

    @staticmethod
    def _default_calibration_sequence() -> list[CalibrationStep]:
        # Calibration sequence: ThreshEqu -> SCurve -> Noise
        # Repeat calibration until noise gives back 0 noisy pixels
        return [
            CalibrationStep(name="threqu", scan_cls=ThresholdEqualizationScan),
            CalibrationStep(name="scurve", scan_cls=SCurveScan),
            CalibrationStep(name="noise",  scan_cls=NoiseScan),
        ]

    def run_once(self) -> OrchestrationResult:
        """Ejecuta una iteración del orquestador según el estado actual."""
        start_state = SystemConfig.get_state()

        if start_state == SystemState.IDLE:
            return OrchestrationResult(
                start_state=start_state,
                end_state=SystemConfig.get_state(),
                scan_ended=False,
                n_noisy_pixels=SystemConfig.get_noisy_pixels(),
                details="IDLE state: no action executed.",
            )

        if start_state == SystemState.CALIBRATION:
            scan_ended, details = self._run_calibration_state()
        elif start_state == SystemState.ACQUISITION:
            scan_ended, details = self._run_acquisition_state()
        elif start_state == SystemState.ANALYSIS:
            scan_ended, details = self._run_analysis_state()
        else:
            raise RuntimeError(f"Unsupported state: {start_state}")

        return OrchestrationResult(
            start_state=start_state,
            end_state=SystemConfig.get_state(),
            scan_ended=scan_ended,
            n_noisy_pixels=SystemConfig.get_noisy_pixels(),
            details=details,
        )

    def run(self, max_iterations: int = 100) -> list[OrchestrationResult]:
        """
        Ejecuta el loop del orquestador hasta max_iterations o hasta volver a IDLE.
        El límite es intencional para evitar bucles infinitos en modo automático.
        """
        if max_iterations <= 0:
            raise ValueError("max_iterations must be > 0")

        results: list[OrchestrationResult] = []
        for _ in range(max_iterations):
            result = self.run_once()
            results.append(result)
            if result.end_state == SystemState.IDLE:
                break

        return results

    def _run_calibration_state(self) -> tuple[bool, str]:
        if not self._calibration_sequence:
            raise RuntimeError("Calibration sequence is empty.")

        if self._calibration_step_idx >= len(self._calibration_sequence):
            self._calibration_step_idx = 0

        step = self._calibration_sequence[self._calibration_step_idx]
        scan = step.scan_cls(**(step.scan_kwargs or {}))

        self.logger.info("Running calibration step '%s'", step.name)
        scan.run()

        if not scan.scan_ended:
            raise RuntimeError(
                f"Calibration step '{step.name}' finished without terminal end-flag."
            )

        self._calibration_step_idx += 1

        if self._calibration_step_idx >= len(self._calibration_sequence):
            self._calibration_step_idx = 0
            self._last_operational_state = SystemState.CALIBRATION
            SystemConfig.set_state(SystemState.ANALYSIS)
            return True, f"Calibration sequence completed with final step '{step.name}'."

        return True, f"Calibration step '{step.name}' completed."

    def _run_acquisition_state(self) -> tuple[bool, str]:
        if self._acquisition_executor is None:
            raise RuntimeError(
                "Acquisition executor is not configured. "
                "Pass acquisition_executor callable when creating StateOrchestrator."
            )

        self.logger.info("Running acquisition executor")
        scan_ended = bool(self._acquisition_executor())
        if not scan_ended:
            raise RuntimeError("Acquisition finished without end-flag.")

        self._last_operational_state = SystemState.ACQUISITION
        SystemConfig.set_state(SystemState.ANALYSIS)
        return True, "Acquisition completed and transitioned to ANALYSIS."

    def _run_analysis_state(self) -> tuple[bool, str]:
        root_manager = SystemConfig.create_root_manager()
        root_manager.load()

        if self._last_operational_state == SystemState.ACQUISITION:
            self.last_hit_analysis = HitAnalysis(root_manager)
            self.logger.info(
                "HitAnalysis complete: %d tracks reconstructed",
                len(self.last_hit_analysis.plot_coord),
            )
        else:
            self.last_hit_analysis = None

        noise = NoiseAnalysis(root_manager)
        n_noisy = len(noise.noisy_pixels) if noise.noisy_pixels else 0
        SystemConfig.set_noisy_pixels(n_noisy)

        if SystemConfig.check_noisy_below_max():
            SystemConfig.set_state(SystemState.ACQUISITION)
            return False, f"Analysis done: n_noisy_pixels={n_noisy}, next=ACQUISITION."

        SystemConfig.set_state(SystemState.CALIBRATION)
        return False, f"Analysis done: n_noisy_pixels={n_noisy}, next=CALIBRATION."