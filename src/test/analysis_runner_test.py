"""
Tests para rd53_api/analysis/analysis_runner.py

Verifica:
- AnalysisRunner ejecuta análisis según estado del sistema
- AnalysisResult contiene los datos correctos
- n_noisy_pixels se actualiza en SystemConfig
"""
from __future__ import annotations
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import awkward as ak

from rd53_api.analysis.analysis_runner import AnalysisRunner, AnalysisResult
from rd53_api.config.system_config import SystemConfig
from rd53_api.workflow.system_state import SystemState
from rd53_api.core.exceptions import AnalysisError


class FakeRootManager:
    """Mock de RootManager para tests."""
    
    def __init__(self, arrays=None, loaded: bool = True):
        self.arrays = arrays
        self._loaded = loaded

    def is_loaded(self) -> bool:
        return self._loaded


def create_test_arrays():
    """Crear arrays de prueba con datos válidos."""
    return ak.Array({
        "event": [0, 1, 2, 3],
        "RD53_frame_event_nhits": [
            [1, 0, 0],
            [2, 1, 0],  # Evento con múltiples hits (ruido potencial)
            [0, 0, 0],  # Vacío
            [1, 2, 0],
        ],
        "RD53_frame_triggered": [1, 1, 0, 1],
        "RD53_hit_tot": [
            [5],
            [2, 2],  # TOT bajo = ruido
            [],
            [10, 8],
        ],
        "RD53_hit_row": [
            [10],
            [11, 12],
            [],
            [13, 14],
        ],
        "RD53_hit_col": [
            [20],
            [21, 22],
            [],
            [23, 24],
        ],
    })


class TestAnalysisResult(unittest.TestCase):
    """Tests para AnalysisResult dataclass."""
    
    def test_analysis_result_fields(self):
        """AnalysisResult tiene los campos esperados."""
        result = AnalysisResult(
            noise_analysis=None,
            hit_analysis=None,
            n_noisy_pixels=5
        )
        self.assertIsNone(result.noise_analysis)
        self.assertIsNone(result.hit_analysis)
        self.assertEqual(result.n_noisy_pixels, 5)
    
    def test_noisy_pixels_property_returns_none_when_no_analysis(self):
        """noisy_pixels retorna None si no hay noise_analysis."""
        result = AnalysisResult(
            noise_analysis=None,
            hit_analysis=None,
            n_noisy_pixels=0
        )
        self.assertIsNone(result.noisy_pixels)


class TestAnalysisRunnerInit(unittest.TestCase):
    """Tests para inicialización de AnalysisRunner."""
    
    def setUp(self):
        SystemConfig.reset()
    
    def tearDown(self):
        SystemConfig.reset()
    
    def test_init_stores_root_manager(self):
        """AnalysisRunner guarda referencia al RootManager."""
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        
        self.assertIs(runner.root_manager, manager)
        self.assertIsNone(runner.noise_analysis)
        self.assertIsNone(runner.hit_analysis)


class TestAnalysisRunnerRun(unittest.TestCase):
    """Tests para AnalysisRunner.run()."""
    
    def setUp(self):
        SystemConfig.reset()
        self.temp_dir = tempfile.mkdtemp()
        self.xml_file = Path(self.temp_dir) / "test.xml"
        self.xml_file.touch()
        self.root_file = Path(self.temp_dir) / "test.root"
        self.root_file.touch()
    
    def tearDown(self):
        import shutil
        SystemConfig.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_run_raises_in_idle_state(self):
        """run() lanza AnalysisError en estado IDLE."""
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        
        with self.assertRaises(AnalysisError):
            runner.run()
    
    def test_run_raises_in_analysis_state(self):
        """run() lanza AnalysisError en estado ANALYSIS."""
        # Configurar para llegar a ANALYSIS
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file,
            root_path=self.root_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        SystemConfig.set_state(SystemState.ANALYSIS)
        
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        
        with self.assertRaises(AnalysisError):
            runner.run()
    
    def test_run_in_calibration_only_noise(self):
        """En CALIBRATION, run() solo ejecuta NoiseAnalysis."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        result = runner.run()
        
        self.assertIsNotNone(result.noise_analysis)
        self.assertIsNone(result.hit_analysis)
    
    def test_run_in_acquisition_both_analyses(self):
        """En ACQUISITION, run() ejecuta HitAnalysis y NoiseAnalysis."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.ACQUISITION)
        
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        result = runner.run()
        
        self.assertIsNotNone(result.noise_analysis)
        self.assertIsNotNone(result.hit_analysis)
    
    def test_run_updates_system_config_noisy_pixels(self):
        """run() actualiza n_noisy_pixels en SystemConfig."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        result = runner.run()
        
        # SystemConfig debe tener el mismo valor que el resultado
        self.assertEqual(
            SystemConfig.get_noisy_pixels(),
            result.n_noisy_pixels
        )


class TestAnalysisRunnerNoisyPixels(unittest.TestCase):
    """Tests para n_noisy_pixels property."""
    
    def setUp(self):
        SystemConfig.reset()
        self.temp_dir = tempfile.mkdtemp()
        self.xml_file = Path(self.temp_dir) / "test.xml"
        self.xml_file.touch()
    
    def tearDown(self):
        import shutil
        SystemConfig.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_n_noisy_pixels_zero_before_run(self):
        """n_noisy_pixels es 0 antes de ejecutar."""
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        
        self.assertEqual(runner.n_noisy_pixels, 0)
    
    def test_n_noisy_pixels_after_run(self):
        """n_noisy_pixels tiene valor correcto después de ejecutar."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        
        manager = FakeRootManager(arrays=create_test_arrays())
        runner = AnalysisRunner(manager)
        result = runner.run()
        
        # Debe ser >= 0 (el valor exacto depende de los datos)
        self.assertGreaterEqual(result.n_noisy_pixels, 0)
        self.assertEqual(runner.n_noisy_pixels, result.n_noisy_pixels)


if __name__ == "__main__":
    unittest.main()
