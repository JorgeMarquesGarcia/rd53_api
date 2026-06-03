from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


class SystemState(Enum):
    """
    Estados posibles del sistema RD53.
    
    Flujo típico:
        IDLE → CALIBRATION → ANALYSIS → ACQUISITION → ANALYSIS → ...
    
    TODO: Considerar añadir estados PLOT, ERROR, subestados de calibración.
    """
    
    IDLE = auto()           # Sin configurar / en reposo
    CALIBRATION = auto()    # Modo calibración (scans de calibración)
    ACQUISITION = auto()    # Modo adquisición de datos (physics)
    ANALYSIS = auto()       # Modo análisis (post-adquisición)


@dataclass
class TransitionRule:
    """
    Regla que define las condiciones para una transición entre estados.
    
    Attributes:
        required_config: Lista de paths que deben estar configurados
                        (e.g., ["xml_path", "ph2_acf_dir"])
        condition: Función que retorna True si la condición dinámica se cumple.
                  Si es None, no hay condición dinámica.
        condition_name: Nombre descriptivo de la condición (para mensajes de error)
    """
    required_config: list[str] = field(default_factory=list)
    condition: Callable[[], bool] | None = None
    condition_name: str | None = None


# Reglas de transición: (from_state, to_state) → TransitionRule
# Solo las transiciones definidas aquí son válidas
TRANSITION_RULES: dict[tuple[SystemState, SystemState], TransitionRule] = {
    # =========================================================================
    # Desde IDLE
    # =========================================================================
    (SystemState.IDLE, SystemState.CALIBRATION): TransitionRule(
        required_config=["xml_path", "ph2_acf_dir"],
    ),
    (SystemState.IDLE, SystemState.ACQUISITION): TransitionRule(
        required_config=["xml_path", "ph2_acf_dir"],
    ),
    (SystemState.IDLE, SystemState.ANALYSIS): TransitionRule(
        required_config=["root_path"],
    ),
    
    # =========================================================================
    # Desde CALIBRATION
    # =========================================================================
    (SystemState.CALIBRATION, SystemState.IDLE): TransitionRule(),
    (SystemState.CALIBRATION, SystemState.ANALYSIS): TransitionRule(
        required_config=["root_path"],
        condition=None,  # Se inyecta: check_root_available(run_number)
        condition_name="root_file_available",
    ),
    # NOTA: CAL → ACQ no permitido, debe pasar por ANALYSIS
    
    # =========================================================================
    # Desde ACQUISITION
    # =========================================================================
    (SystemState.ACQUISITION, SystemState.IDLE): TransitionRule(),
    (SystemState.ACQUISITION, SystemState.ANALYSIS): TransitionRule(
        required_config=["root_path"],
        condition=None,  # Se inyecta: check_root_available(run_number)
        condition_name="root_file_available",
    ),
    # NOTA: ACQ → CAL no permitido, debe pasar por ANALYSIS
    
    # =========================================================================
    # Desde ANALYSIS
    # =========================================================================
    (SystemState.ANALYSIS, SystemState.IDLE): TransitionRule(),
    (SystemState.ANALYSIS, SystemState.ACQUISITION): TransitionRule(
        required_config=["xml_path", "ph2_acf_dir"],
        condition=None,  # Se inyecta: noisy_pixels < NPIXELSMAX
        condition_name="noisy_pixels_below_threshold",
    ),
    (SystemState.ANALYSIS, SystemState.CALIBRATION): TransitionRule(
        required_config=["xml_path", "ph2_acf_dir"],
        condition=None,  # Se inyecta: noisy_pixels > NPIXELSMAX
        condition_name="noisy_pixels_above_threshold",
    ),
}


def get_valid_transitions(from_state: SystemState) -> list[SystemState]:
    """Get list of valid destination states from a given state."""
    return [to_state for (src, to_state) in TRANSITION_RULES.keys() if src == from_state]


# =============================================================================
# Exceptions
# =============================================================================

class SystemStateError(Exception):
    """Base exception for system state errors."""
    pass


class InvalidStateTransitionError(SystemStateError):
    """Raised when attempting an invalid state transition."""
    
    def __init__(self, from_state: SystemState, to_state: SystemState):
        self.from_state = from_state
        self.to_state = to_state
        valid = get_valid_transitions(from_state)
        msg = (
            f"Cannot transition from {from_state.name} to {to_state.name}. "
            f"Valid transitions from {from_state.name}: {[s.name for s in valid]}"
        )
        super().__init__(msg)


class TransitionConditionNotMetError(SystemStateError):
    """Raised when a transition's dynamic condition is not satisfied."""
    
    def __init__(self, from_state: SystemState, to_state: SystemState, condition_name: str | None):
        self.from_state = from_state
        self.to_state = to_state
        self.condition_name = condition_name
        msg = (
            f"Cannot transition from {from_state.name} to {to_state.name}: "
            f"condition '{condition_name or 'unknown'}' not met."
        )
        super().__init__(msg)


class InvalidStateError(SystemStateError):
    """Raised when an operation is attempted in an invalid state."""
    
    def __init__(self, current_state: SystemState, required_states: tuple[SystemState, ...]):
        self.current_state = current_state
        self.required_states = required_states
        msg = (
            f"Operation requires state {[s.name for s in required_states]}, "
            f"but current state is {current_state.name}"
        )
        super().__init__(msg)


class SystemNotConfiguredError(SystemStateError):
    """Raised when system is not properly configured."""
    
    def __init__(self, missing: str):
        msg = f"System not configured: {missing}. Call SystemConfig.configure() first."
        super().__init__(msg)
