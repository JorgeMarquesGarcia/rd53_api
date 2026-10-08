from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable
import logging

from src.workflow.system_state import (
    SystemState,
    TransitionRule,
    TRANSITION_RULES,
    InvalidStateTransitionError,
    TransitionConditionNotMetError,
    InvalidStateError,
    SystemNotConfiguredError,
)
from src.config.xml.xml_manager import XmlManager
from src.config.txt.txt_manager import TxtManager
from src.config.root.root_manager import RootManager


def _existing_path(path: str | Path, what: str) -> Path:
    """Convierte a Path y comprueba que existe (sin modificar ningún estado)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{what} not found: {p}")
    return p


class SystemConfig:
    """
    Configuración global del sistema RD53 con soporte de estados.

    Singleton que gestiona los paths del sistema y el estado actual.
    Todos los métodos set_* auto-validan la existencia de los paths: si la
    ruta no existe se lanza FileNotFoundError y el valor anterior se conserva.

    Usage:
        # Configurar el sistema
        SystemConfig.configure(
            ph2_acf_dir="/app/Ph2_ACF",
            xml_path="/app/config.xml"
        )

        # Cambiar a modo calibración
        SystemConfig.set_state(SystemState.CALIBRATION)

        # Ejecutar operaciones...

        # Volver a idle
        SystemConfig.set_state(SystemState.IDLE)
    """

    _instance = None
    _state: SystemState = SystemState.IDLE

    # Paths del sistema
    _ph2_acf_dir: Path | None = None
    _xml_path: Path | None = None
    _root_path: Path | None = None
    _txt_base_dir: Path | None = None
    _plots_dir: Path | None = None
    _active_hw_chips: list[tuple[int, int]] = []

    # Noisy pixels tracking (for state transition decisions)
    NOISY_PIXELS_MAX: int = 5
    _n_noisy_pixels: int = 0

    # Logger
    _logger = logging.getLogger("SystemConfig")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def setup(cls) -> None:
        """
        Initialize transition conditions for the state machine.

        Must be called once before using state transitions that depend on
        noisy pixels count (ANALYSIS -> ACQUISITION/CALIBRATION).

        This is separate from __new__ to allow explicit initialization
        and make the dependency on noisy pixel checks clear.
        """
        # ANALYSIS -> ACQUISITION: only if noisy pixels are acceptable
        cls.register_transition_condition(
            SystemState.ANALYSIS,
            SystemState.ACQUISITION,
            cls.check_noisy_below_max,
        )

        # ANALYSIS -> CALIBRATION: if noisy pixels exceed threshold
        cls.register_transition_condition(
            SystemState.ANALYSIS,
            SystemState.CALIBRATION,
            cls.check_noisy_above_max,
        )

        cls._logger.info("SystemConfig setup complete - transition conditions registered")

    # =========================================================================
    # State Management
    # =========================================================================

    @classmethod
    def get_state(cls) -> SystemState:
        """Get the current system state."""
        return cls._state

    @classmethod
    def set_state(cls, state: SystemState) -> None:
        """
        Change the system state.

        Args:
            state: The new state to transition to.

        Raises:
            InvalidStateTransitionError: If the transition is not valid.
        """
        if cls._state == state:
            cls._logger.debug("Already in state %s", state.name)
            return

        cls._validate_transition(cls._state, state)
        old_state = cls._state
        cls._state = state
        cls._logger.info("State changed: %s -> %s", old_state.name, state.name)

    @classmethod
    def _validate_transition(cls, from_state: SystemState, to_state: SystemState) -> None:
        """
        Validate that a state transition is allowed.

        Checks:
            1. The transition exists in TRANSITION_RULES
            2. Required config paths are set
            3. Dynamic condition (if any) is satisfied
        """
        rule = TRANSITION_RULES.get((from_state, to_state))

        # Check if transition is defined
        if rule is None:
            raise InvalidStateTransitionError(from_state, to_state)

        # Check required configuration
        cls._validate_required_config(rule.required_config, to_state)

        # Check dynamic condition
        if rule.condition is not None and not rule.condition():
            raise TransitionConditionNotMetError(from_state, to_state, rule.condition_name)

    @classmethod
    def _validate_required_config(cls, required: list[str], to_state: SystemState) -> None:
        """Validate that required configuration paths are set."""
        config_checks = {
            "xml_path": (cls._xml_path, "XML path"),
            "ph2_acf_dir": (cls._ph2_acf_dir, "Ph2_ACF directory"),
            "root_path": (cls._root_path, "ROOT path"),
            "txt_base_dir": (cls._txt_base_dir, "TXT base directory"),
        }

        for config_name in required:
            value, display_name = config_checks.get(config_name, (None, config_name))
            if value is None:
                raise SystemNotConfiguredError(
                    f"{display_name} (required for transition to {to_state.name})"
                )

    @classmethod
    def require_state(cls, *allowed_states: SystemState) -> None:
        """
        Verify that the system is in one of the allowed states.

        Args:
            *allowed_states: One or more states that are valid for the operation.

        Raises:
            InvalidStateError: If the current state is not in allowed_states.
        """
        if cls._state not in allowed_states:
            raise InvalidStateError(cls._state, allowed_states)

    @classmethod
    def is_state(cls, state: SystemState) -> bool:
        """Check if the system is in a specific state."""
        return cls._state == state

    # =========================================================================
    # Noisy Pixels Management
    # =========================================================================

    @classmethod
    def set_noisy_pixels(cls, n: int) -> None:
        """
        Update the noisy pixels count.

        Called by AnalysisRunner after analysis to inform state transition logic.

        Args:
            n: Number of noisy pixels detected.
        """
        cls._n_noisy_pixels = n
        cls._logger.info("Noisy pixels updated: %d (max: %d)", n, cls.NOISY_PIXELS_MAX)

    @classmethod
    def get_noisy_pixels(cls) -> int:
        """Get the current noisy pixels count."""
        return cls._n_noisy_pixels

    @classmethod
    def check_noisy_below_max(cls) -> bool:
        """
        Check if noisy pixels are within acceptable threshold.

        Used as condition for ANALYSIS -> ACQUISITION transition.
        """
        return cls._n_noisy_pixels <= cls.NOISY_PIXELS_MAX

    @classmethod
    def check_noisy_above_max(cls) -> bool:
        """
        Check if noisy pixels exceed acceptable threshold.

        Used as condition for ANALYSIS -> CALIBRATION transition.
        """
        return cls._n_noisy_pixels > cls.NOISY_PIXELS_MAX

    @classmethod
    def register_transition_condition(
        cls,
        from_state: SystemState,
        to_state: SystemState,
        condition: Callable[[], bool],
    ) -> None:
        """
        Register a dynamic condition function for a transition.

        The condition function will be called when attempting the transition.
        It should return True if the transition is allowed, False otherwise.

        Args:
            from_state: Source state
            to_state: Destination state
            condition: Callable that returns True if condition is met

        Raises:
            KeyError: If the transition (from_state, to_state) is not defined

        Example:
            def check_noisy_pixels_below_max():
                return get_noisy_pixel_count() < NPIXELSMAX

            SystemConfig.register_transition_condition(
                SystemState.ANALYSIS,
                SystemState.ACQUISITION,
                check_noisy_pixels_below_max
            )
        """
        key = (from_state, to_state)
        if key not in TRANSITION_RULES:
            raise KeyError(
                f"Transition {from_state.name} -> {to_state.name} is not defined"
            )

        rule = TRANSITION_RULES[key]
        # Se crea una regla nueva en vez de mutar la existente
        TRANSITION_RULES[key] = TransitionRule(
            required_config=rule.required_config,
            condition=condition,
            condition_name=rule.condition_name,
        )
        cls._logger.info(
            "Registered condition for transition %s -> %s",
            from_state.name, to_state.name
        )

    # =========================================================================
    # Chip / Detector Configuration
    # =========================================================================

    # Columnas activas del chip RD53A (128-263 por defecto)
    _active_col_start: int = 128
    _active_col_end:   int = 263

    # Hybrids y chips activos
    _active_hybrids: list[int] = [0]
    _active_chips:   list[int] = [0]

    # configFile por chip: {(hybrid_id, rd53_id) -> "CMSIT_RD53A_X.txt"}
    _chip_config_files: dict[tuple[int, int], str] = {}

    @classmethod
    def set_chip_config_files(
        cls, config_map: dict[tuple[int, int], str]
    ) -> None:
        """
        Almacena el nombre del configFile para cada chip presente en el XML.

        Genera una línea INFO por chip:
            Hybrid: 1, Chip_id: 4 => CMSIT_RD53A_4.txt

        Args:
            config_map: {(hybrid_id, rd53_id): "CMSIT_RD53A_X.txt", ...}
        """
        cls._chip_config_files = dict(config_map)
        for (hybrid_id, rd53_id), fname in sorted(cls._chip_config_files.items()):
            cls._logger.info(
                "Hybrid: %d, Chip_id: %d => %s", hybrid_id, rd53_id, fname
            )

    @classmethod
    def get_chip_config_files(cls) -> dict[tuple[int, int], str]:
        """Devuelve una copia del mapa completo {(hybrid_id, rd53_id): configFile}."""
        return dict(cls._chip_config_files)

    @classmethod
    def get_chip_config_file(cls, hybrid_id: int, rd53_id: int) -> str | None:
        """Devuelve el configFile de un chip concreto, o None si no se conoce."""
        return cls._chip_config_files.get((hybrid_id, rd53_id))

    @classmethod
    def set_active_columns(cls, start: int, end: int) -> None:
        """Set the active column range for the chip."""
        cls._active_col_start = start
        cls._active_col_end   = end
        cls._logger.info("Active columns set: %d-%d", start, end)

    @classmethod
    def get_active_columns(cls) -> tuple[int, int]:
        """Get the active column range (start, end)."""
        return cls._active_col_start, cls._active_col_end

    @classmethod
    def set_active_hybrids(cls, hybrids: Iterable[int]) -> None:
        """Set the list of active hybrids."""
        cls._active_hybrids = list(hybrids)
        cls._logger.info("Active hybrids set: %s", cls._active_hybrids)

    @classmethod
    def get_active_hybrids(cls) -> list[int]:
        return list(cls._active_hybrids)

    @classmethod
    def set_active_hw_chips(cls, chips: Iterable[tuple[int, int]]) -> None:
        cls._active_hw_chips = list(chips)

    @classmethod
    def get_active_hw_chips(cls) -> list[tuple[int, int]]:
        return list(cls._active_hw_chips)

    @classmethod
    def set_active_chips(cls, chips: Iterable[int]) -> None:
        """Set the list of active chips."""
        cls._active_chips = list(chips)
        cls._logger.info("Active chips set: %s", cls._active_chips)

    @classmethod
    def get_active_chips(cls) -> list[int]:
        return list(cls._active_chips)

    @classmethod
    def get_chip_dir(cls, board: int = 0, optical: int = 0,
                     hybrid: int | None = None, chip: int | None = None) -> str:
        """Build the ROOT directory path for a chip.

        Si no se especifica hybrid/chip, usa el primero de los activos.
        """
        if hybrid is None:
            if not cls._active_hybrids:
                raise SystemNotConfiguredError("active hybrids")
            hybrid = cls._active_hybrids[0]
        if chip is None:
            if not cls._active_chips:
                raise SystemNotConfiguredError("active chips")
            chip = cls._active_chips[0]
        return f"Detector/Board_{board}/OpticalGroup_{optical}/Hybrid_{hybrid}/Chip_{chip}"

    # =========================================================================
    # Configuration
    # =========================================================================

    @classmethod
    def configure(
        cls,
        ph2_acf_dir: str | Path,
        xml_path: str | Path,
        root_path: str | Path | None = None,
        txt_base_dir: str | Path | None = None,
    ) -> None:
        """
        Configure all system paths at once.

        Se validan todas las rutas antes de aplicar ninguna: si alguna no
        existe se lanza FileNotFoundError y la configuración anterior queda
        intacta.

        Args:
            ph2_acf_dir: Path to Ph2_ACF directory.
            xml_path: Path to XML configuration file.
            root_path: Optional path to ROOT files directory.
            txt_base_dir: Optional path to TXT config files directory.
                         Defaults to ph2_acf_dir if not provided.
        """
        ph2 = _existing_path(ph2_acf_dir, "Ph2_ACF directory")
        xml = _existing_path(xml_path, "XML file")
        root = _existing_path(root_path, "ROOT path") if root_path else None
        txt = _existing_path(txt_base_dir, "TXT base dir") if txt_base_dir else ph2

        cls._ph2_acf_dir = ph2
        cls._xml_path = xml
        if root is not None:
            cls._root_path = root
        cls._txt_base_dir = txt

        cls._logger.info("System configured successfully")

    @classmethod
    def reset(cls) -> None:
        """Reset all configuration and return to IDLE state."""
        cls._ph2_acf_dir = None
        cls._xml_path = None
        cls._root_path = None
        cls._txt_base_dir = None
        cls._plots_dir = None
        cls._chip_config_files = {}
        cls._state = SystemState.IDLE
        cls._active_hw_chips = []
        cls._logger.info("System configuration reset")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if minimum required paths are configured."""
        return cls._ph2_acf_dir is not None and cls._xml_path is not None

    # =========================================================================
    # Path Setters
    # =========================================================================

    @classmethod
    def set_ph2_acf_dir(cls, path: str | Path) -> None:
        """Set the Ph2_ACF directory path."""
        cls._ph2_acf_dir = _existing_path(path, "Ph2_ACF directory")
        cls._logger.debug("Ph2_ACF dir set: %s", cls._ph2_acf_dir)

    @classmethod
    def set_xml_path(cls, path: str | Path) -> None:
        """Set the XML configuration file path."""
        cls._xml_path = _existing_path(path, "XML file")
        cls._logger.debug("XML path set: %s", cls._xml_path)

    @classmethod
    def set_root_path(cls, path: str | Path) -> None:
        """Set the ROOT files directory path."""
        cls._root_path = _existing_path(path, "ROOT path")
        cls._logger.debug("ROOT path set: %s", cls._root_path)

    @classmethod
    def set_txt_base_dir(cls, path: str | Path) -> None:
        """Set the TXT config files base directory."""
        cls._txt_base_dir = _existing_path(path, "TXT base dir")
        cls._logger.debug("TXT base dir set: %s", cls._txt_base_dir)

    @classmethod
    def set_plots_dir(cls, path: str | Path | None) -> None:
        """Set the plots output directory (it is created if missing). None = sin carpeta propia."""
        if path is None or str(path).strip() == "":
            cls._plots_dir = None
            return
        plots_dir = Path(path)
        plots_dir.mkdir(parents=True, exist_ok=True)
        cls._plots_dir = plots_dir
        cls._logger.debug("Plots dir set: %s", cls._plots_dir)

    @classmethod
    def set_max_noisy_pixels(cls, n: int) -> None:
        """Set the maximum allowed noisy pixels for state transition decisions."""
        cls.NOISY_PIXELS_MAX = n
        cls._logger.info("Max noisy pixels set to: %d", n)

    # =========================================================================
    # Path Getters
    # =========================================================================

    @classmethod
    def get_ph2_acf_dir(cls) -> Path:
        """Get the configured Ph2_ACF directory."""
        if cls._ph2_acf_dir is None:
            raise SystemNotConfiguredError("Ph2_ACF directory")
        return cls._ph2_acf_dir

    @classmethod
    def get_xml_path(cls) -> Path:
        """Get the configured XML file path."""
        if cls._xml_path is None:
            raise SystemNotConfiguredError("XML path")
        return cls._xml_path

    @classmethod
    def get_root_path(cls) -> Path:
        """Get the configured ROOT files path."""
        if cls._root_path is None:
            raise SystemNotConfiguredError("ROOT path")
        return cls._root_path

    @classmethod
    def get_txt_base_dir(cls) -> Path:
        """Get the configured TXT base directory."""
        if cls._txt_base_dir is None:
            raise SystemNotConfiguredError("TXT base directory")
        return cls._txt_base_dir

    @classmethod
    def get_plots_dir(cls) -> Path | None:
        """Carpeta donde guardar los plots.

        La 'Plots output directory' de Config si se ha configurado; si no,
        <ROOT output directory>/../plots; None si no hay ninguna de las dos
        (el plotter usa entonces su carpeta por defecto).
        """
        if cls._plots_dir is not None:
            return cls._plots_dir
        if cls._root_path is not None:
            return cls._root_path.parent / "plots"
        return None

    # =========================================================================
    # Manager Factories
    # =========================================================================

    @classmethod
    def create_xml_manager(cls, read_only: bool = False) -> XmlManager:
        """
        Create and load an XmlManager instance.

        Args:
            read_only: If True, manager will be in read-only mode.

        Returns:
            Loaded XmlManager instance.
        """
        xml = XmlManager(str(cls.get_xml_path()), read_only=read_only)
        xml.load()
        return xml

    @classmethod
    def create_txt_manager(cls, chip_id: str) -> TxtManager:
        """
        Create and load a TxtManager instance.

        Args:
            chip_id: Chip identifier (e.g., 'F7', 'H4').

        Returns:
            Loaded TxtManager instance.
        """
        txt_manager = TxtManager(str(cls.get_txt_base_dir()), chip_id)
        txt_manager.load()
        return txt_manager

    @classmethod
    def create_root_manager(cls, path: str | Path | None = None,
                            branches: Iterable[str] | None = None) -> RootManager:
        """
        Create a RootManager instance.

        Args:
            path: Optional specific ROOT file path. If None, uses configured root_path.
            branches: Optional branch names to read (None = all branches).
                      Leer solo las ramas necesarias acelera la carga y reduce memoria.

        Returns:
            RootManager instance (call load() to load data).
        """
        root_path = Path(path) if path else cls.get_root_path()
        return RootManager(root_path, branches=branches)
