"""
Tests para rd53_api/config/system_config.py

Verifica:
- Singleton pattern
- Gestión de estados (set_state, get_state, require_state)
- Validación de transiciones
- Gestión de noisy pixels
- Métodos setup() y register_transition_condition()
- Configuración de paths
"""
from __future__ import annotations
import unittest
import tempfile
from pathlib import Path

from src.config.system_config import SystemConfig
from src.workflow.system_state import (
    SystemState,
    TRANSITION_RULES,
    InvalidStateTransitionError,
    TransitionConditionNotMetError,
    InvalidStateError,
    SystemNotConfiguredError,
)


class TestSystemConfigSingleton(unittest.TestCase):
    """Tests para el patrón singleton."""
    
    def test_singleton_returns_same_instance(self):
        """Dos instancias de SystemConfig son el mismo objeto."""
        config1 = SystemConfig()
        config2 = SystemConfig()
        self.assertIs(config1, config2)


class TestSystemConfigStateManagement(unittest.TestCase):
    """Tests para gestión de estados."""
    
    def setUp(self):
        """Reset estado antes de cada test."""
        SystemConfig.reset()
    
    def tearDown(self):
        """Reset estado después de cada test."""
        SystemConfig.reset()
    
    def test_initial_state_is_idle(self):
        """Estado inicial es IDLE."""
        self.assertEqual(SystemConfig.get_state(), SystemState.IDLE)
    
    def test_is_state(self):
        """is_state() retorna True/False correctamente."""
        self.assertTrue(SystemConfig.is_state(SystemState.IDLE))
        self.assertFalse(SystemConfig.is_state(SystemState.CALIBRATION))
    
    def test_require_state_passes_when_valid(self):
        """require_state() no lanza excepción si estado es válido."""
        SystemConfig.require_state(SystemState.IDLE)  # No debe lanzar
    
    def test_require_state_raises_when_invalid(self):
        """require_state() lanza InvalidStateError si estado no es válido."""
        with self.assertRaises(InvalidStateError):
            SystemConfig.require_state(SystemState.CALIBRATION)


class TestSystemConfigTransitions(unittest.TestCase):
    """Tests para transiciones de estado."""
    
    def setUp(self):
        """Reset y configurar paths necesarios."""
        SystemConfig.reset()
        # Crear archivos temporales para satisfacer validaciones de paths
        self.temp_dir = tempfile.mkdtemp()
        self.xml_file = Path(self.temp_dir) / "test.xml"
        self.xml_file.touch()
        self.root_file = Path(self.temp_dir) / "test.root"
        self.root_file.touch()
    
    def tearDown(self):
        """Limpiar archivos temporales."""
        import shutil
        SystemConfig.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_idle_to_calibration_with_config(self):
        """IDLE → CALIBRATION funciona con configuración correcta."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        self.assertEqual(SystemConfig.get_state(), SystemState.CALIBRATION)
    
    def test_idle_to_calibration_without_config_raises(self):
        """IDLE → CALIBRATION sin configuración lanza excepción."""
        with self.assertRaises(SystemNotConfiguredError):
            SystemConfig.set_state(SystemState.CALIBRATION)
    
    def test_calibration_to_analysis_requires_root(self):
        """CALIBRATION → ANALYSIS requiere root_path configurado."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        
        # Sin root_path debe fallar
        with self.assertRaises(SystemNotConfiguredError):
            SystemConfig.set_state(SystemState.ANALYSIS)
        
        # Con root_path debe funcionar
        SystemConfig.set_root_path(self.root_file)
        SystemConfig.set_state(SystemState.ANALYSIS)
        self.assertEqual(SystemConfig.get_state(), SystemState.ANALYSIS)
    
    def test_calibration_to_acquisition_not_allowed(self):
        """CALIBRATION → ACQUISITION no está permitido (debe pasar por ANALYSIS)."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.CALIBRATION)
        
        with self.assertRaises(InvalidStateTransitionError):
            SystemConfig.set_state(SystemState.ACQUISITION)
    
    def test_acquisition_to_calibration_not_allowed(self):
        """ACQUISITION → CALIBRATION no está permitido (debe pasar por ANALYSIS)."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_state(SystemState.ACQUISITION)
        
        with self.assertRaises(InvalidStateTransitionError):
            SystemConfig.set_state(SystemState.CALIBRATION)
    
    def test_set_state_to_current_state_is_noop(self):
        """Establecer el mismo estado no hace nada (no lanza error)."""
        SystemConfig.set_state(SystemState.IDLE)
        self.assertEqual(SystemConfig.get_state(), SystemState.IDLE)


class TestSystemConfigNoisyPixels(unittest.TestCase):
    """Tests para gestión de noisy pixels."""
    
    def setUp(self):
        SystemConfig.reset()
    
    def tearDown(self):
        SystemConfig.reset()
    
    def test_initial_noisy_pixels_is_zero(self):
        """Contador inicial de noisy pixels es 0."""
        self.assertEqual(SystemConfig.get_noisy_pixels(), 0)
    
    def test_set_noisy_pixels(self):
        """set_noisy_pixels() actualiza el contador."""
        SystemConfig.set_noisy_pixels(3)
        self.assertEqual(SystemConfig.get_noisy_pixels(), 3)
    
    def test_check_noisy_below_max_default(self):
        """Con 0 píxeles, está por debajo del máximo."""
        self.assertTrue(SystemConfig.check_noisy_below_max())
    
    def test_check_noisy_above_max_default(self):
        """Con 0 píxeles, NO está por encima del máximo."""
        self.assertFalse(SystemConfig.check_noisy_above_max())
    
    def test_check_noisy_at_threshold(self):
        """En el umbral exacto (5), below=True, above=False."""
        SystemConfig.set_noisy_pixels(5)  # NOISY_PIXELS_MAX = 5
        self.assertTrue(SystemConfig.check_noisy_below_max())  # <= 5
        self.assertFalse(SystemConfig.check_noisy_above_max())  # > 5
    
    def test_check_noisy_above_threshold(self):
        """Por encima del umbral (6), below=False, above=True."""
        SystemConfig.set_noisy_pixels(6)
        self.assertFalse(SystemConfig.check_noisy_below_max())
        self.assertTrue(SystemConfig.check_noisy_above_max())


class TestSystemConfigSetup(unittest.TestCase):
    """Tests para setup() y register_transition_condition()."""
    
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
        # Reset conditions in TRANSITION_RULES
        from src.workflow.system_state import TransitionRule
        TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.ACQUISITION)] = TransitionRule(
            required_config=["xml_path", "ph2_acf_dir"],
            condition=None,
            condition_name="noisy_pixels_below_threshold",
        )
        TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.CALIBRATION)] = TransitionRule(
            required_config=["xml_path", "ph2_acf_dir"],
            condition=None,
            condition_name="noisy_pixels_above_threshold",
        )
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_registers_conditions(self):
        """setup() registra condiciones para transiciones desde ANALYSIS."""
        SystemConfig.setup()
        
        # Las reglas ahora tienen condiciones
        rule_acq = TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.ACQUISITION)]
        rule_cal = TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.CALIBRATION)]
        
        self.assertIsNotNone(rule_acq.condition)
        self.assertIsNotNone(rule_cal.condition)
    
    def test_analysis_to_acquisition_blocked_when_noisy(self):
        """ANALYSIS → ACQUISITION bloqueado si hay muchos píxeles ruidosos."""
        SystemConfig.setup()
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file,
            root_path=self.root_file
        )
        
        # Ir a ANALYSIS
        SystemConfig.set_state(SystemState.CALIBRATION)
        SystemConfig.set_state(SystemState.ANALYSIS)
        
        # Simular muchos píxeles ruidosos
        SystemConfig.set_noisy_pixels(10)
        
        # Intentar ir a ACQUISITION debe fallar
        with self.assertRaises(TransitionConditionNotMetError):
            SystemConfig.set_state(SystemState.ACQUISITION)
    
    def test_analysis_to_acquisition_allowed_when_clean(self):
        """ANALYSIS → ACQUISITION permitido si hay pocos píxeles ruidosos."""
        SystemConfig.setup()
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file,
            root_path=self.root_file
        )
        
        # Ir a ANALYSIS
        SystemConfig.set_state(SystemState.CALIBRATION)
        SystemConfig.set_state(SystemState.ANALYSIS)
        
        # Simular pocos píxeles ruidosos
        SystemConfig.set_noisy_pixels(2)
        
        # Ir a ACQUISITION debe funcionar
        SystemConfig.set_state(SystemState.ACQUISITION)
        self.assertEqual(SystemConfig.get_state(), SystemState.ACQUISITION)


class TestSystemConfigPaths(unittest.TestCase):
    """Tests para configuración de paths."""
    
    def setUp(self):
        SystemConfig.reset()
        self.temp_dir = tempfile.mkdtemp()
        self.xml_file = Path(self.temp_dir) / "test.xml"
        self.xml_file.touch()
    
    def tearDown(self):
        import shutil
        SystemConfig.reset()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_is_configured_false_initially(self):
        """is_configured() retorna False sin configuración."""
        self.assertFalse(SystemConfig.is_configured())
    
    def test_is_configured_true_after_configure(self):
        """is_configured() retorna True después de configure()."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        self.assertTrue(SystemConfig.is_configured())
    
    def test_set_path_to_nonexistent_raises(self):
        """Establecer path a archivo inexistente lanza FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            SystemConfig.set_xml_path("/nonexistent/file.xml")
    
    def test_reset_clears_configuration(self):
        """reset() limpia toda la configuración."""
        SystemConfig.configure(
            ph2_acf_dir=self.temp_dir,
            xml_path=self.xml_file
        )
        SystemConfig.set_noisy_pixels(5)
        
        SystemConfig.reset()
        
        self.assertFalse(SystemConfig.is_configured())
        self.assertEqual(SystemConfig.get_state(), SystemState.IDLE)


if __name__ == "__main__":
    unittest.main()
