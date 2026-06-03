"""
Tests para rd53_api/core/system_state.py

Verifica:
- Definición de estados (SystemState enum)
- Estructura de TransitionRule
- TRANSITION_RULES: transiciones válidas e inválidas
- Excepciones de estado
"""
from __future__ import annotations
import unittest

from rd53_api.workflow.system_state import (
    SystemState,
    TransitionRule,
    TRANSITION_RULES,
    get_valid_transitions,
    InvalidStateTransitionError,
    TransitionConditionNotMetError,
    InvalidStateError,
    SystemNotConfiguredError,
)


class TestSystemState(unittest.TestCase):
    """Tests para el enum SystemState."""
    
    def test_all_states_defined(self):
        """Verificar que existen los 4 estados."""
        self.assertEqual(len(SystemState), 4)
        self.assertIn(SystemState.IDLE, SystemState)
        self.assertIn(SystemState.CALIBRATION, SystemState)
        self.assertIn(SystemState.ACQUISITION, SystemState)
        self.assertIn(SystemState.ANALYSIS, SystemState)
    
    def test_state_names(self):
        """Verificar nombres de estados."""
        self.assertEqual(SystemState.IDLE.name, "IDLE")
        self.assertEqual(SystemState.CALIBRATION.name, "CALIBRATION")
        self.assertEqual(SystemState.ACQUISITION.name, "ACQUISITION")
        self.assertEqual(SystemState.ANALYSIS.name, "ANALYSIS")
    
    def test_states_are_unique(self):
        """Verificar que cada estado tiene un valor único."""
        values = [s.value for s in SystemState]
        self.assertEqual(len(values), len(set(values)))


class TestTransitionRule(unittest.TestCase):
    """Tests para el dataclass TransitionRule."""
    
    def test_default_values(self):
        """TransitionRule sin argumentos tiene valores por defecto."""
        rule = TransitionRule()
        self.assertEqual(rule.required_config, [])
        self.assertIsNone(rule.condition)
        self.assertIsNone(rule.condition_name)
    
    def test_with_required_config(self):
        """TransitionRule con configuración requerida."""
        rule = TransitionRule(required_config=["xml_path", "ph2_acf_dir"])
        self.assertEqual(rule.required_config, ["xml_path", "ph2_acf_dir"])
    
    def test_with_condition(self):
        """TransitionRule con condición dinámica."""
        condition = lambda: True
        rule = TransitionRule(
            condition=condition,
            condition_name="always_true"
        )
        self.assertEqual(rule.condition, condition)
        self.assertEqual(rule.condition_name, "always_true")
        self.assertTrue(rule.condition())


class TestTransitionRules(unittest.TestCase):
    """Tests para el diccionario TRANSITION_RULES."""
    
    def test_idle_transitions(self):
        """Desde IDLE se puede ir a CALIBRATION o ACQUISITION."""
        valid = get_valid_transitions(SystemState.IDLE)
        self.assertIn(SystemState.CALIBRATION, valid)
        self.assertIn(SystemState.ACQUISITION, valid)
        self.assertNotIn(SystemState.ANALYSIS, valid)
    
    def test_calibration_transitions(self):
        """Desde CALIBRATION se puede ir a IDLE o ANALYSIS."""
        valid = get_valid_transitions(SystemState.CALIBRATION)
        self.assertIn(SystemState.IDLE, valid)
        self.assertIn(SystemState.ANALYSIS, valid)
        # NO se puede ir directo a ACQUISITION
        self.assertNotIn(SystemState.ACQUISITION, valid)
    
    def test_acquisition_transitions(self):
        """Desde ACQUISITION se puede ir a IDLE o ANALYSIS."""
        valid = get_valid_transitions(SystemState.ACQUISITION)
        self.assertIn(SystemState.IDLE, valid)
        self.assertIn(SystemState.ANALYSIS, valid)
        # NO se puede ir directo a CALIBRATION
        self.assertNotIn(SystemState.CALIBRATION, valid)
    
    def test_analysis_transitions(self):
        """Desde ANALYSIS se puede ir a IDLE, CALIBRATION o ACQUISITION."""
        valid = get_valid_transitions(SystemState.ANALYSIS)
        self.assertIn(SystemState.IDLE, valid)
        self.assertIn(SystemState.CALIBRATION, valid)
        self.assertIn(SystemState.ACQUISITION, valid)
    
    def test_idle_to_calibration_requires_config(self):
        """IDLE → CALIBRATION requiere xml_path y ph2_acf_dir."""
        rule = TRANSITION_RULES[(SystemState.IDLE, SystemState.CALIBRATION)]
        self.assertIn("xml_path", rule.required_config)
        self.assertIn("ph2_acf_dir", rule.required_config)
    
    def test_calibration_to_analysis_requires_root(self):
        """CALIBRATION → ANALYSIS requiere root_path."""
        rule = TRANSITION_RULES[(SystemState.CALIBRATION, SystemState.ANALYSIS)]
        self.assertIn("root_path", rule.required_config)
    
    def test_analysis_to_acquisition_has_condition_name(self):
        """ANALYSIS → ACQUISITION tiene condition_name definido."""
        rule = TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.ACQUISITION)]
        self.assertEqual(rule.condition_name, "noisy_pixels_below_threshold")
    
    def test_analysis_to_calibration_has_condition_name(self):
        """ANALYSIS → CALIBRATION tiene condition_name definido."""
        rule = TRANSITION_RULES[(SystemState.ANALYSIS, SystemState.CALIBRATION)]
        self.assertEqual(rule.condition_name, "noisy_pixels_above_threshold")


class TestExceptions(unittest.TestCase):
    """Tests para las excepciones de estado."""
    
    def test_invalid_state_transition_error(self):
        """InvalidStateTransitionError contiene información útil."""
        error = InvalidStateTransitionError(
            SystemState.CALIBRATION, 
            SystemState.ACQUISITION
        )
        self.assertEqual(error.from_state, SystemState.CALIBRATION)
        self.assertEqual(error.to_state, SystemState.ACQUISITION)
        self.assertIn("CALIBRATION", str(error))
        self.assertIn("ACQUISITION", str(error))
        self.assertIn("Valid transitions", str(error))
    
    def test_transition_condition_not_met_error(self):
        """TransitionConditionNotMetError contiene información útil."""
        error = TransitionConditionNotMetError(
            SystemState.ANALYSIS,
            SystemState.ACQUISITION,
            "noisy_pixels_below_threshold"
        )
        self.assertEqual(error.from_state, SystemState.ANALYSIS)
        self.assertEqual(error.to_state, SystemState.ACQUISITION)
        self.assertEqual(error.condition_name, "noisy_pixels_below_threshold")
        self.assertIn("noisy_pixels_below_threshold", str(error))
    
    def test_invalid_state_error(self):
        """InvalidStateError contiene información útil."""
        error = InvalidStateError(
            SystemState.IDLE,
            (SystemState.CALIBRATION, SystemState.ACQUISITION)
        )
        self.assertEqual(error.current_state, SystemState.IDLE)
        self.assertEqual(
            error.required_states, 
            (SystemState.CALIBRATION, SystemState.ACQUISITION)
        )
        self.assertIn("IDLE", str(error))
    
    def test_system_not_configured_error(self):
        """SystemNotConfiguredError contiene información útil."""
        error = SystemNotConfiguredError("xml_path")
        self.assertIn("xml_path", str(error))
        self.assertIn("configure", str(error).lower())


if __name__ == "__main__":
    unittest.main()
