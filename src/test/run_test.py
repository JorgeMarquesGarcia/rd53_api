#!/usr/bin/env python3
"""
=============================================================================
RD53 API - RUN TEST DIDÁCTICO
=============================================================================

Este archivo es un tutorial interactivo que simula un ciclo completo de
operación del sistema RD53:

    IDLE → CALIBRATION → ANALYSIS → ACQUISITION → ANALYSIS → ...

Cada paso está documentado explicando:
- ¿Qué hace?
- ¿Por qué lo hace?
- ¿Qué parámetros son clave?
- ¿Qué decide el siguiente paso?

=============================================================================
ARQUITECTURA GENERAL DE LA API
=============================================================================

La API tiene 3 capas principales:

┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 1: CONFIGURACIÓN (config/)                                        │
│  ─────────────────────────────────────────────────────────────────────  │
│  • SystemConfig (Singleton): Estado global del sistema                  │
│  • XmlManager: Lee/escribe archivos XML de configuración del chip       │
│  • TxtManager: Lee/escribe máscaras de píxeles (formato TXT)            │
│  • RootManager: Lee archivos ROOT con datos de física/calibración       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 2: OPERACIONES (calibration/, acquisition/)                       │
│  ─────────────────────────────────────────────────────────────────────  │
│  • CalibrationMap: Configura parámetros para scans de calibración       │
│  • AcquisitionMap: Configura parámetros para adquisición de datos       │
│  • *_scan.py: Ejecuta scans específicos (threqu, scurve, noise, etc.)   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CAPA 3: ANÁLISIS (analysis/)                                           │
│  ─────────────────────────────────────────────────────────────────────  │
│  • NoiseAnalysis: Detecta píxeles ruidosos                              │
│  • HitAnalysis: Analiza hits de física (trigger, detector, TOT)         │
│  • AnalysisRunner: Orquesta qué análisis ejecutar según el estado       │
└─────────────────────────────────────────────────────────────────────────┘

=============================================================================
MÁQUINA DE ESTADOS
=============================================================================

El corazón de la API es la máquina de estados en SystemConfig:

                    ┌──────────────────┐
                    │      IDLE        │  Estado inicial
                    └────────┬─────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
            ▼                                 ▼
    ┌───────────────┐                 ┌───────────────┐
    │  CALIBRATION  │                 │  ACQUISITION  │
    └───────┬───────┘                 └───────┬───────┘
            │                                 │
            └────────────────┬────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │    ANALYSIS      │  Punto de decisión
                    └────────┬─────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
            ▼                                 ▼
    n_noisy_pixels > MAX              n_noisy_pixels <= MAX
            │                                 │
            ▼                                 ▼
    → CALIBRATION                     → ACQUISITION
    (recalibrar)                      (continuar)

=============================================================================
"""

import sys
import tempfile
from pathlib import Path
import awkward as ak

# Añadir el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def print_header(title: str) -> None:
    """Imprime un encabezado formateado."""
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def print_step(step: str, description: str) -> None:
    """Imprime un paso con descripción."""
    print(f"\n{'─' * 75}")
    print(f"  PASO: {step}")
    print(f"{'─' * 75}")
    print(f"\n  {description}\n")


def print_info(key: str, value: str) -> None:
    """Imprime información clave-valor."""
    print(f"    • {key}: {value}")


def print_code(code: str) -> None:
    """Imprime código de ejemplo."""
    print(f"\n    >>> {code}")


def print_result(result: str) -> None:
    """Imprime un resultado."""
    print(f"    ✓ {result}")


def print_warning(warning: str) -> None:
    """Imprime una advertencia."""
    print(f"    ⚠ {warning}")


def print_decision(condition: str, result: str) -> None:
    """Imprime una decisión tomada."""
    print(f"\n    DECISIÓN: {condition}")
    print(f"    → {result}")


# =============================================================================
# PASO 0: PREPARACIÓN DEL ENTORNO
# =============================================================================

def setup_test_environment():
    """
    Crea archivos temporales para simular el entorno de trabajo.
    
    En un entorno real, estos serían:
    - XML: Configuración del chip RD53A (registros, etc.)
    - ROOT: Datos de física o calibración
    - PH2_ACF: Directorio del software Ph2_ACF del CERN
    """
    print_header("PASO 0: PREPARACIÓN DEL ENTORNO")
    
    print("""
    En un sistema real, necesitas:
    
    1. Ph2_ACF directory: Software del CERN para controlar el chip
       - Contiene ejecutables para correr scans
       - Path típico: /app/Ph2_ACF
    
    2. XML config file: Configuración del chip RD53A
       - Define registros, umbrales, máscaras
       - Path típico: /app/CMSIT_RD53A.xml
    
    3. ROOT files: Datos de salida de calibración/adquisición
       - Generados por Ph2_ACF tras cada scan
       - Path típico: /data/Run000010_NoiseScan.root
    """)
    
    # Crear directorio temporal
    temp_dir = tempfile.mkdtemp(prefix="rd53_test_")
    temp_path = Path(temp_dir)
    
    # Crear archivos dummy
    xml_file = temp_path / "CMSIT_RD53A.xml"
    xml_file.write_text("<root><chip>RD53A</chip></root>")
    
    root_file = temp_path / "Run000010_Calibration.root"
    root_file.touch()
    
    print_info("Directorio temporal", temp_dir)
    print_info("XML config", str(xml_file))
    print_info("ROOT file", str(root_file))
    
    return temp_path, xml_file, root_file


# =============================================================================
# FAKE ROOT MANAGER (para simular datos)
# =============================================================================

class FakeRootManager:
    """
    Simulador de RootManager para tests.
    
    En un sistema real, RootManager lee archivos .root con uproot
    y extrae los arrays de hits del chip.
    
    Estructura de datos típica:
    - event: Número de evento
    - RD53_frame_event_nhits: Hits por chip [chip0, chip1, chip2, ...]
    - RD53_frame_triggered: Si el evento tiene trigger (0/1)
    - RD53_hit_tot: Time Over Threshold (proporcional a la carga)
    - RD53_hit_row/col: Coordenadas del píxel
    """
    
    def __init__(self, noisy_pixel_count: int = 2):
        """
        Args:
            noisy_pixel_count: Cuántos píxeles ruidosos simular.
                              Esto afecta la decisión de estado.
        """
        self._loaded = True
        self._noisy_count = noisy_pixel_count
        self._create_arrays()
    
    def _create_arrays(self):
        """Crea arrays de prueba con estructura realista."""
        # Simulamos 10 eventos
        n_events = 10
        
        # Crear estructura de datos
        self.arrays = ak.Array({
            "event": list(range(n_events)),
            
            # Hits por chip: [chip_trigger, chip_1, chip_2]
            # chip_trigger es el chip que genera el trigger
            "RD53_frame_event_nhits": [
                [1, 0, 0],   # Evento 0: 1 hit solo en trigger
                [2, 1, 0],   # Evento 1: 2 hits en trigger, 1 en chip1 (ruido potencial)
                [0, 0, 0],   # Evento 2: vacío (será filtrado)
                [1, 2, 1],   # Evento 3: hits en todos los chips
                [1, 0, 0],   # Evento 4: solo trigger
                [3, 0, 0],   # Evento 5: múltiples hits en trigger (ruido)
                [1, 1, 0],   # Evento 6: hit en chip1
                [1, 0, 1],   # Evento 7: hit en chip2
                [2, 2, 0],   # Evento 8: múltiples hits (ruido)
                [1, 1, 1],   # Evento 9: hits en todos
            ],
            
            # Trigger flag
            "RD53_frame_triggered": [1, 1, 0, 1, 1, 1, 1, 1, 1, 1],
            
            # TOT: Time Over Threshold (carga del hit)
            # TOT bajo (<=3) + múltiples hits = ruido
            "RD53_hit_tot": [
                [10],           # Evento 0: TOT alto (bueno)
                [2, 2, 3],      # Evento 1: TOT bajo (ruido)
                [],             # Evento 2: vacío
                [8, 7, 6, 5],   # Evento 3: TOT alto (bueno)
                [12],           # Evento 4: TOT alto
                [1, 2, 1],      # Evento 5: TOT bajo (ruido)
                [9, 8],         # Evento 6: TOT alto
                [10, 9],        # Evento 7: TOT alto
                [2, 1, 3, 2],   # Evento 8: TOT bajo (ruido)
                [7, 8, 9],      # Evento 9: TOT alto
            ],
            
            # Coordenadas de los hits
            "RD53_hit_row": [
                [100],
                [101, 102, 103],
                [],
                [200, 201, 202, 203],
                [104],
                [105, 106, 107],
                [108, 109],
                [110, 111],
                [112, 113, 114, 115],
                [116, 117, 118],
            ],
            "RD53_hit_col": [
                [50],
                [51, 52, 53],
                [],
                [60, 61, 62, 63],
                [54],
                [55, 56, 57],
                [58, 59],
                [70, 71],
                [72, 73, 74, 75],
                [76, 77, 78],
            ],
        })
    
    def is_loaded(self) -> bool:
        return self._loaded
    
    def load(self, *args, **kwargs):
        """Simula cargar un archivo ROOT."""
        self._loaded = True


# =============================================================================
# EJECUCIÓN DEL CICLO COMPLETO
# =============================================================================

def run_complete_cycle():
    """
    Ejecuta un ciclo completo de operación:
    
    IDLE → CALIBRATION → ANALYSIS → ACQUISITION → ANALYSIS
    
    Cada paso está documentado con explicaciones detalladas.
    """
    
    # =========================================================================
    # IMPORTS
    # =========================================================================
    print_header("IMPORTS NECESARIOS")
    
    print("""
    Los imports principales de la API son:
    """)
    
    print_code("from rd53_api.config.system_config import SystemConfig")
    print("""
        SystemConfig: Singleton que controla el estado del sistema.
        Es el "cerebro" de la API. Gestiona:
        - Estado actual (IDLE, CALIBRATION, ACQUISITION, ANALYSIS)
        - Paths del sistema (XML, ROOT, Ph2_ACF)
        - Contador de píxeles ruidosos (n_noisy_pixels)
    """)
    
    print_code("from rd53_api.core.system_state import SystemState")
    print("""
        SystemState: Enum con los 4 estados posibles.
        Define las transiciones válidas entre estados.
    """)
    
    print_code("from rd53_api.analysis.analysis_runner import AnalysisRunner")
    print("""
        AnalysisRunner: Orquesta la ejecución de análisis.
        Decide qué análisis ejecutar según el estado actual:
        - CALIBRATION → solo NoiseAnalysis
        - ACQUISITION → HitAnalysis + NoiseAnalysis
    """)
    
    # Imports reales
    from rd53_api.config.system_config import SystemConfig
    from rd53_api.workflow.system_state import SystemState
    from rd53_api.workflow.system_state import TransitionConditionNotMetError
    
    # =========================================================================
    # PASO 1: ESTADO INICIAL (IDLE)
    # =========================================================================
    print_header("PASO 1: ESTADO INICIAL - IDLE")
    
    print_step(
        "Verificar estado inicial",
        """El sistema siempre comienza en estado IDLE.
        Este es el estado de reposo donde el sistema está configurado
        pero no está ejecutando ninguna operación."""
    )
    
    # Reset para asegurar estado limpio
    SystemConfig.reset()
    
    print_code("SystemConfig.reset()")
    print_code("state = SystemConfig.get_state()")
    
    state = SystemConfig.get_state()
    print_result(f"Estado actual: {state.name}")
    
    print("""
    PARÁMETROS CLAVE en IDLE:
    - No hay restricciones
    - Desde aquí puedes ir a CALIBRATION o ACQUISITION
    - Necesitas configurar paths antes de cambiar de estado
    """)
    
    # =========================================================================
    # PASO 2: CONFIGURACIÓN DEL SISTEMA
    # =========================================================================
    print_header("PASO 2: CONFIGURACIÓN DEL SISTEMA")
    
    print_step(
        "Configurar paths del sistema",
        """Antes de cambiar de estado, debes configurar los paths necesarios.
        SystemConfig valida que existan antes de permitir transiciones."""
    )
    
    # Crear entorno de prueba
    temp_path, xml_file, root_file = setup_test_environment()
    
    print_code(f"""SystemConfig.configure(
    ph2_acf_dir="{temp_path}",
    xml_path="{xml_file}",
    root_path="{root_file}"
)""")
    
    SystemConfig.configure(
        ph2_acf_dir=temp_path,
        xml_path=xml_file,
        root_path=root_file
    )
    
    print_result("Sistema configurado correctamente")
    print_info("is_configured()", str(SystemConfig.is_configured()))
    
    print("""
    CONFIGURACIÓN REQUERIDA por transición:
    
    │ Transición              │ Requiere                    │
    │─────────────────────────│─────────────────────────────│
    │ IDLE → CALIBRATION      │ xml_path, ph2_acf_dir       │
    │ IDLE → ACQUISITION      │ xml_path, ph2_acf_dir       │
    │ CAL/ACQ → ANALYSIS      │ root_path                   │
    │ ANALYSIS → CAL/ACQ      │ xml_path, ph2_acf_dir       │
    """)
    
    # =========================================================================
    # PASO 3: SETUP DE CONDICIONES
    # =========================================================================
    print_header("PASO 3: SETUP DE CONDICIONES DE TRANSICIÓN")
    
    print_step(
        "Registrar condiciones dinámicas",
        """Algunas transiciones requieren condiciones dinámicas además de paths.
        SystemConfig.setup() registra las condiciones para transiciones desde ANALYSIS."""
    )
    
    print_code("SystemConfig.setup()")
    
    SystemConfig.setup()
    
    print_result("Condiciones de transición registradas")
    
    print("""
    CONDICIONES REGISTRADAS:
    
    1. ANALYSIS → ACQUISITION:
       Condición: check_noisy_below_max()
       → n_noisy_pixels <= NOISY_PIXELS_MAX (default: 5)
       → Si se cumple: el sistema está sano, puede adquirir datos
    
    2. ANALYSIS → CALIBRATION:
       Condición: check_noisy_above_max()
       → n_noisy_pixels > NOISY_PIXELS_MAX
       → Si se cumple: demasiados píxeles ruidosos, hay que recalibrar
    """)
    
    print_info("NOISY_PIXELS_MAX", str(SystemConfig.NOISY_PIXELS_MAX))
    
    # =========================================================================
    # PASO 4: TRANSICIÓN A CALIBRATION
    # =========================================================================
    print_header("PASO 4: TRANSICIÓN IDLE → CALIBRATION")
    
    print_step(
        "Iniciar modo calibración",
        """En modo CALIBRATION se ejecutan scans de calibración del chip:
        - Threshold equalization (ajustar umbrales)
        - Noise scan (detectar píxeles ruidosos)
        - S-Curve (caracterizar respuesta)"""
    )
    
    print_code("SystemConfig.set_state(SystemState.CALIBRATION)")
    
    try:
        SystemConfig.set_state(SystemState.CALIBRATION)
        print_result(f"Estado cambiado a: {SystemConfig.get_state().name}")
    except Exception as e:
        print_warning(f"Error: {e}")
        return
    
    print("""
    ¿QUÉ OCURRIÓ INTERNAMENTE?
    
    1. SystemConfig._validate_transition() verifica:
       - ¿Existe la transición (IDLE, CALIBRATION) en TRANSITION_RULES? ✓
       - ¿Están configurados xml_path y ph2_acf_dir? ✓
       - ¿Hay alguna condición dinámica? No (es None)
    
    2. Se actualiza _state a SystemState.CALIBRATION
    
    3. Se registra en el logger el cambio de estado
    """)
    
    print("""
    EN UN SISTEMA REAL, AHORA EJECUTARÍAS:
    
    # Crear mapa de calibración
    from rd53_api.calibration.maps import CalibrationMap
    cal_map = CalibrationMap()
    cal_map.set_param("VCAL_HIGH", 400)
    
    # Ejecutar scan de calibración
    from rd53_api.calibration.scans import ThresholdEqualization
    scan = ThresholdEqualization(cal_map)
    scan.run()  # Esto genera un archivo ROOT
    """)
    
    # =========================================================================
    # PASO 5: SIMULAR CALIBRACIÓN Y TRANSICIÓN A ANALYSIS
    # =========================================================================
    print_header("PASO 5: CALIBRACIÓN COMPLETA → ANALYSIS")
    
    print_step(
        "Transición a modo análisis",
        """Tras completar la calibración, analizamos los resultados.
        El sistema pasa a estado ANALYSIS para procesar los datos ROOT."""
    )
    
    print_code("SystemConfig.set_state(SystemState.ANALYSIS)")
    
    try:
        SystemConfig.set_state(SystemState.ANALYSIS)
        print_result(f"Estado cambiado a: {SystemConfig.get_state().name}")
    except Exception as e:
        print_warning(f"Error: {e}")
        return
    
    print("""
    REQUISITOS PARA ESTA TRANSICIÓN:
    - root_path debe estar configurado ✓
    - No hay condición dinámica (por ahora)
    """)
    
    # =========================================================================
    # PASO 6: EJECUTAR ANÁLISIS
    # =========================================================================
    print_header("PASO 6: EJECUTAR ANÁLISIS CON AnalysisRunner")
    
    print_step(
        "Crear y ejecutar AnalysisRunner",
        """AnalysisRunner examina el estado actual del sistema y decide
        qué análisis ejecutar:
        - Si venimos de CALIBRATION → solo NoiseAnalysis
        - Si venimos de ACQUISITION → HitAnalysis + NoiseAnalysis
        
        ¡IMPORTANTE! El estado actual es ANALYSIS, pero AnalysisRunner
        recuerda de dónde venimos por el último estado antes de ANALYSIS."""
    )
    
    # NOTA: Hay un bug en el código actual - AnalysisRunner verifica el estado
    # ACTUAL, no el anterior. Como estamos en ANALYSIS, fallará.
    # Vamos a simular el comportamiento correcto.
    
    print("""
    NOTA: En la implementación actual, AnalysisRunner verifica que estemos
    en CALIBRATION o ACQUISITION para ejecutar. Esto significa que debes
    llamar a run() ANTES de cambiar a ANALYSIS, o modificar el diseño.
    
    Para este ejemplo, simularemos el análisis manualmente:
    """)
    
    # Crear fake root manager con pocos píxeles ruidosos (sistema sano)
    print_code("root_manager = FakeRootManager(noisy_pixel_count=2)")
    root_manager = FakeRootManager(noisy_pixel_count=2)
    
    print_code("""
# Ejecutar análisis de ruido manualmente
from rd53_api.analysis.analysis_noise import NoiseAnalysis
noise_analysis = NoiseAnalysis(root_manager)
""")
    
    from rd53_api.analysis.analysis_noise import NoiseAnalysis
    noise_analysis = NoiseAnalysis(root_manager)
    
    n_noisy = len(noise_analysis.noisy_pixels) if noise_analysis.noisy_pixels else 0
    
    print_result("Análisis completado")
    print_info("Eventos analizados", str(len(noise_analysis.clean_data)))
    print_info("Eventos ruidosos detectados", str(len(noise_analysis.noisy_events)))
    print_info("Píxeles ruidosos", str(n_noisy))
    print_info("Coordenadas", str(noise_analysis.noisy_pixels[:5]) + "..." if n_noisy > 5 else str(noise_analysis.noisy_pixels))
    
    print("""
    ¿CÓMO DETECTA NoiseAnalysis PÍXELES RUIDOSOS?
    
    1. Filtra eventos vacíos → clean_data
    2. Busca eventos con múltiples hits (_multiple_hits)
    3. De esos, busca los que tienen TOT <= 3 (_noise_filter)
       - TOT bajo = poca carga = probablemente ruido, no partícula real
    4. Extrae coordenadas (row, col) de esos eventos
    """)
    
    # Actualizar SystemConfig con el conteo
    print_code(f"SystemConfig.set_noisy_pixels({n_noisy})")
    SystemConfig.set_noisy_pixels(n_noisy)
    
    print_result(f"SystemConfig actualizado con n_noisy_pixels = {n_noisy}")
    
    # =========================================================================
    # PASO 7: DECISIÓN - ¿A DÓNDE VAMOS?
    # =========================================================================
    print_header("PASO 7: DECISIÓN BASADA EN PÍXELES RUIDOSOS")
    
    print_step(
        "Evaluar condiciones de transición",
        """Ahora el sistema decide a dónde ir basándose en n_noisy_pixels:
        
        - Si n_noisy_pixels <= 5 → Ir a ACQUISITION (sistema sano)
        - Si n_noisy_pixels > 5 → Ir a CALIBRATION (recalibrar)"""
    )
    
    print_info("n_noisy_pixels", str(SystemConfig.get_noisy_pixels()))
    print_info("NOISY_PIXELS_MAX", str(SystemConfig.NOISY_PIXELS_MAX))
    print_info("check_noisy_below_max()", str(SystemConfig.check_noisy_below_max()))
    print_info("check_noisy_above_max()", str(SystemConfig.check_noisy_above_max()))
    
    if SystemConfig.check_noisy_below_max():
        print_decision(
            f"n_noisy_pixels ({n_noisy}) <= NOISY_PIXELS_MAX ({SystemConfig.NOISY_PIXELS_MAX})",
            "Sistema SANO → Ir a ACQUISITION"
        )
        next_state = SystemState.ACQUISITION
    else:
        print_decision(
            f"n_noisy_pixels ({n_noisy}) > NOISY_PIXELS_MAX ({SystemConfig.NOISY_PIXELS_MAX})",
            "Sistema con RUIDO → Volver a CALIBRATION"
        )
        next_state = SystemState.CALIBRATION
    
    # =========================================================================
    # PASO 8: TRANSICIÓN A ACQUISITION
    # =========================================================================
    print_header("PASO 8: TRANSICIÓN ANALYSIS → ACQUISITION")
    
    print_step(
        "Intentar transición a adquisición",
        """Ahora intentamos cambiar a ACQUISITION.
        La transición verificará la condición check_noisy_below_max()."""
    )
    
    print_code("SystemConfig.set_state(SystemState.ACQUISITION)")
    
    try:
        SystemConfig.set_state(next_state)
        print_result(f"Estado cambiado a: {SystemConfig.get_state().name}")
    except TransitionConditionNotMetError as e:
        print_warning(f"Transición bloqueada: {e}")
        print("""
        La condición no se cumplió. El sistema tiene demasiados píxeles
        ruidosos y necesita recalibración.
        """)
        # Intentar ir a calibración
        SystemConfig.set_state(SystemState.CALIBRATION)
        print_result(f"Redirigido a: {SystemConfig.get_state().name}")
    
    print("""
    ¿QUÉ VERIFICÓ _validate_transition()?
    
    1. ¿Existe (ANALYSIS, ACQUISITION) en TRANSITION_RULES? ✓
    2. ¿Están configurados xml_path y ph2_acf_dir? ✓
    3. ¿Se cumple check_noisy_below_max()? 
       - Verifica: n_noisy_pixels <= NOISY_PIXELS_MAX
       - Si es True: transición permitida
       - Si es False: lanza TransitionConditionNotMetError
    """)
    
    # =========================================================================
    # PASO 9: MODO ACQUISITION
    # =========================================================================
    if SystemConfig.get_state() == SystemState.ACQUISITION:
        print_header("PASO 9: MODO ACQUISITION")
        
        print_step(
            "Adquisición de datos de física",
            """En modo ACQUISITION se adquieren datos reales de partículas.
            El chip detecta partículas que atraviesan el detector."""
        )
        
        print("""
        EN UN SISTEMA REAL:
        
        # Configurar adquisición
        from rd53_api.acquisition.maps import PhysicsMap
        phys_map = PhysicsMap()
        phys_map.set_param("TRIGGER_MODE", "external")
        
        # Ejecutar adquisición
        from rd53_api.acquisition.scans import PhysicsRun
        run = PhysicsRun(phys_map, n_events=10000)
        run.start()  # Genera Run000013_Physics.root
        """)
        
        print_result("Simulando adquisición completada...")
        print_info("Eventos adquiridos", "10000 (simulado)")
    
    # =========================================================================
    # PASO 10: SEGUNDO ANÁLISIS
    # =========================================================================
    print_header("PASO 10: SEGUNDO CICLO DE ANÁLISIS")
    
    print_step(
        "Analizar datos de física",
        """Tras la adquisición, analizamos los datos.
        En este caso ejecutamos AMBOS: HitAnalysis y NoiseAnalysis."""
    )
    
    if SystemConfig.get_state() == SystemState.ACQUISITION:
        print_code("SystemConfig.set_state(SystemState.ANALYSIS)")
        SystemConfig.set_state(SystemState.ANALYSIS)
        print_result(f"Estado: {SystemConfig.get_state().name}")
    
    print("""
    ANÁLISIS EN MODO ACQUISITION (diferente a CALIBRATION):
    
    1. HitAnalysis:
       - Filtra eventos con trigger (_apply_trigger_filter)
       - Filtra eventos con hits en detectores (_detector_filter)
       - Aplica filtros de TOT y layer
       - Extrae hits de física válidos
    
    2. NoiseAnalysis:
       - Mismo proceso que antes
       - Detecta píxeles que siguen generando ruido
    """)
    
    # Simular análisis con más ruido
    print_code("root_manager_physics = FakeRootManager(noisy_pixel_count=7)")
    root_manager_2 = FakeRootManager(noisy_pixel_count=7)
    
    noise_analysis_2 = NoiseAnalysis(root_manager_2)
    n_noisy_2 = len(noise_analysis_2.noisy_pixels) if noise_analysis_2.noisy_pixels else 0
    
    print_result("Segundo análisis completado")
    print_info("Píxeles ruidosos ahora", str(n_noisy_2))
    
    SystemConfig.set_noisy_pixels(n_noisy_2)
    
    # =========================================================================
    # PASO 11: DECISIÓN FINAL
    # =========================================================================
    print_header("PASO 11: DECISIÓN FINAL")
    
    print_step(
        "Evaluar estado del sistema",
        """Con los nuevos datos de análisis, decidimos el siguiente paso."""
    )
    
    print_info("n_noisy_pixels", str(SystemConfig.get_noisy_pixels()))
    print_info("NOISY_PIXELS_MAX", str(SystemConfig.NOISY_PIXELS_MAX))
    
    if SystemConfig.check_noisy_below_max():
        print_decision(
            f"n_noisy_pixels ({n_noisy_2}) <= MAX",
            "Continuar con ACQUISITION"
        )
    else:
        print_decision(
            f"n_noisy_pixels ({n_noisy_2}) > MAX",
            "Necesita RECALIBRACIÓN"
        )
    
    # =========================================================================
    # RESUMEN
    # =========================================================================
    print_header("RESUMEN DEL CICLO")
    
    print("""
    CICLO EJECUTADO:
    
    1. IDLE
       ↓ (configure + set_state)
    2. CALIBRATION
       ↓ (ejecutar scan + set_state)
    3. ANALYSIS (post-calibración)
       ↓ (NoiseAnalysis + decisión)
    4. ACQUISITION (si n_noisy <= MAX)
       ↓ (adquirir datos + set_state)
    5. ANALYSIS (post-adquisición)
       ↓ (HitAnalysis + NoiseAnalysis + decisión)
    6. → ACQUISITION (si está limpio) o → CALIBRATION (si hay ruido)
    
    
    FUNCIONES CLAVE:
    
    │ Función                          │ Propósito                        │
    │──────────────────────────────────│──────────────────────────────────│
    │ SystemConfig.configure()         │ Establecer paths del sistema     │
    │ SystemConfig.setup()             │ Registrar condiciones de trans.  │
    │ SystemConfig.set_state()         │ Cambiar estado (con validación)  │
    │ SystemConfig.set_noisy_pixels()  │ Actualizar contador de ruido     │
    │ NoiseAnalysis()                  │ Detectar píxeles ruidosos        │
    │ HitAnalysis()                    │ Analizar hits de física          │
    │ AnalysisRunner.run()             │ Orquestar análisis según estado  │
    
    
    PARÁMETROS DE DECISIÓN:
    
    │ Parámetro          │ Valor Default │ Afecta                          │
    │────────────────────│───────────────│─────────────────────────────────│
    │ NOISY_PIXELS_MAX   │ 5             │ Decisión ANALYSIS → ACQ/CAL     │
    │ n_noisy_pixels     │ 0             │ Conteo actual de píxeles ruido  │
    │ TOT threshold      │ 3             │ Qué se considera ruido          │
    """)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_path, ignore_errors=True)
    SystemConfig.reset()
    
    print_result("Test completado y recursos limpiados")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                    RD53 API - TUTORIAL INTERACTIVO                        ║
║                                                                           ║
║  Este script demuestra el funcionamiento completo de la API RD53          ║
║  ejecutando un ciclo típico de operación:                                 ║
║                                                                           ║
║      IDLE → CALIBRATION → ANALYSIS → ACQUISITION → ANALYSIS               ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        run_complete_cycle()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 75)
    print("  FIN DEL TUTORIAL")
    print("=" * 75)
