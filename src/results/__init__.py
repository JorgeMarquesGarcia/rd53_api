from .acquisition_result import AcquisitionResult
from .analysis_result import AnalysisResult
from .orchestration_result import OrchestrationResult
from .scan_result import ScanResult

# Nombre antiguo, mantenido por compatibilidad
OrchestratorResult = OrchestrationResult

__all__ = ['AcquisitionResult', 'AnalysisResult', 'OrchestrationResult',
           'OrchestratorResult', 'ScanResult']
