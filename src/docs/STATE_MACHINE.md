# Sistema de Máquina de Estados RD53 API

## Índice

1. [Visión General](#visión-general)
2. [Arquitectura de Componentes](#arquitectura-de-componentes)
3. [Estados del Sistema](#estados-del-sistema)
4. [Reglas de Transición](#reglas-de-transición)
5. [Flujo de Trabajo Típico](#flujo-de-trabajo-típico)
6. [Integración con Análisis](#integración-con-análisis)
7. [API de Referencia](#api-de-referencia)
8. [Ejemplos de Uso](#ejemplos-de-uso)
9. [Diagrama de Estados](#diagrama-de-estados)

---

## Visión General

La máquina de estados del sistema RD53 controla el flujo de operaciones entre calibración,
adquisición de datos y análisis. Su propósito principal es:

1. **Garantizar secuencias válidas**: No se puede pasar de CALIBRATION a ACQUISITION 
   directamente; debe hacerse a través de ANALYSIS para validar el estado del detector.

2. **Validar precondiciones**: Cada transición requiere que ciertos paths estén configurados
   (XML, ROOT, etc.) y que se cumplan condiciones dinámicas.

3. **Automatizar decisiones**: El número de píxeles ruidosos (`n_noisy_pixels`) determina
   automáticamente si el sistema puede continuar con adquisición o necesita recalibración.

---

## Arquitectura de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              rd53_api/                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  core/system_state.py                                                        │
│  ├── SystemState (Enum)          # Estados: IDLE, CALIBRATION, etc.        │
│  ├── TransitionRule (dataclass)  # Regla: config requerida + condición     │
│  ├── TRANSITION_RULES (dict)     # Mapa de transiciones válidas            │
│  └── Excepciones                 # InvalidStateTransitionError, etc.       │
│                                                                              │
│  config/system_config.py                                                     │
│  ├── SystemConfig (Singleton)    # Gestor global de configuración          │
│  │   ├── _state                  # Estado actual del sistema               │
│  │   ├── _n_noisy_pixels         # Contador de píxeles ruidosos            │
│  │   ├── NOISY_PIXELS_MAX        # Umbral (default: 5)                     │
│  │   ├── set_state()             # Cambiar estado (con validación)         │
│  │   ├── setup()                 # Registrar condiciones de transición     │
│  │   └── register_transition_condition()  # Inyectar condiciones           │
│  │                                                                          │
│  analysis/analysis_runner.py                                                 │
│  ├── AnalysisRunner              # Orquestador de análisis                 │
│  │   ├── run()                   # Ejecuta según estado actual             │
│  │   └── n_noisy_pixels          # Actualiza SystemConfig automáticamente  │
│  └── AnalysisResult (dataclass)  # Contenedor de resultados                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Estados del Sistema

### `SystemState` (Enum)

Definido en `rd53_api/core/system_state.py`:

| Estado | Valor | Descripción |
|--------|-------|-------------|
| `IDLE` | 1 | Sistema en reposo, sin configurar o tras reset |
| `CALIBRATION` | 2 | Ejecutando scans de calibración (threshold, noise, etc.) |
| `ACQUISITION` | 3 | Adquiriendo datos de física (runs de partículas) |
| `ANALYSIS` | 4 | Analizando datos ROOT post-run |

### Significado Operativo

- **IDLE**: El sistema está preparado pero no activo. Desde aquí se puede ir a 
  CALIBRATION o ACQUISITION (si ya se calibró previamente).

- **CALIBRATION**: Se ejecutan scans de calibración del chip RD53A:
  - Threshold equalization
  - Noise scan
  - S-Curve
  
  Al finalizar, se genera un archivo ROOT con los resultados.

- **ACQUISITION**: Se adquieren datos de física (partículas reales):
  - Physics runs
  - Datos de trigger
  
  Al finalizar, se genera un archivo ROOT con hits.

- **ANALYSIS**: Se analizan los datos ROOT:
  - Desde CALIBRATION: Solo `NoiseAnalysis` (detectar píxeles ruidosos)
  - Desde ACQUISITION: `HitAnalysis` + `NoiseAnalysis`
  
  El resultado determina el siguiente estado.

---

## Reglas de Transición

### `TransitionRule` (dataclass)

```python
@dataclass
class TransitionRule:
    required_config: list[str]              # Paths necesarios
    condition: Callable[[], bool] | None    # Condición dinámica
    condition_name: str | None              # Nombre para mensajes de error
```

### Mapa de Transiciones `TRANSITION_RULES`

```
┌──────────────┐                           ┌──────────────┐
│              │ ──── xml_path ──────────▶ │              │
│     IDLE     │      ph2_acf_dir          │ CALIBRATION  │
│              │ ◀─────────────────────────│              │
└──────────────┘          (sin requisitos) └──────┬───────┘
       │                                          │
       │ xml_path                                 │ root_path
       │ ph2_acf_dir                              │ root_file_available
       ▼                                          ▼
┌──────────────┐                           ┌──────────────┐
│              │ ◀─────────────────────────│              │
│  ACQUISITION │          (sin requisitos) │   ANALYSIS   │
│              │ ──── root_path ─────────▶ │              │
└──────────────┘      root_file_available  └──────────────┘
                                                  │
                              ┌────────────────────┴────────────────────┐
                              │                                         │
                              ▼                                         ▼
                    ┌─────────────────┐                      ┌─────────────────┐
                    │ ANALYSIS → ACQ  │                      │ ANALYSIS → CAL  │
                    │                 │                      │                 │
                    │ Condición:      │                      │ Condición:      │
                    │ n_noisy ≤ MAX   │                      │ n_noisy > MAX   │
                    │ (sistema sano)  │                      │ (recalibrar)    │
                    └─────────────────┘                      └─────────────────┘
```

### Tabla Detallada de Transiciones

| Desde | Hacia | `required_config` | `condition` | Descripción |
|-------|-------|-------------------|-------------|-------------|
| IDLE | CALIBRATION | `xml_path`, `ph2_acf_dir` | - | Iniciar calibración |
| IDLE | ACQUISITION | `xml_path`, `ph2_acf_dir` | - | Iniciar adquisición (asume calibrado) |
| CALIBRATION | IDLE | - | - | Abortar/reset |
| CALIBRATION | ANALYSIS | `root_path` | `root_file_available`* | Analizar resultados de calibración |
| ACQUISITION | IDLE | - | - | Abortar/reset |
| ACQUISITION | ANALYSIS | `root_path` | `root_file_available`* | Analizar datos adquiridos |
| ANALYSIS | IDLE | - | - | Reset |
| ANALYSIS | ACQUISITION | `xml_path`, `ph2_acf_dir` | `check_noisy_below_max` | Sistema sano, continuar |
| ANALYSIS | CALIBRATION | `xml_path`, `ph2_acf_dir` | `check_noisy_above_max` | Muchos píxeles ruidosos, recalibrar |

*Nota: `root_file_available` está marcado como placeholder (`condition=None`) para inyección futura.

### Transiciones NO Permitidas (Crítico)

- **CALIBRATION → ACQUISITION**: ❌ PROHIBIDO
  - Motivo: Debe pasar por ANALYSIS para validar que la calibración fue exitosa
  
- **ACQUISITION → CALIBRATION**: ❌ PROHIBIDO
  - Motivo: Debe pasar por ANALYSIS para detectar si hay píxeles ruidosos

---

## Flujo de Trabajo Típico

### Secuencia Normal

```
1. IDLE
   │
   ├── SystemConfig.configure(xml_path=..., ph2_acf_dir=...)
   │
   ▼
2. IDLE ──▶ CALIBRATION
   │         │
   │         ├── Ejecutar calibración (Ph2_ACF)
   │         ├── Se genera Run000010_SCurve.root
   │         │
   │         ▼
3. CALIBRATION ──▶ ANALYSIS
   │                  │
   │                  ├── SystemConfig.set_root_path("Run000010_SCurve.root")
   │                  ├── AnalysisRunner(root_manager).run()
   │                  │   ├── NoiseAnalysis → detecta 2 píxeles ruidosos
   │                  │   └── SystemConfig.set_noisy_pixels(2)
   │                  │
   │                  ├── n_noisy_pixels=2 ≤ NOISY_PIXELS_MAX=5 ✓
   │                  │
   │                  ▼
4. ANALYSIS ──▶ ACQUISITION (condición check_noisy_below_max cumplida)
   │                  │
   │                  ├── Ejecutar physics run
   │                  ├── Se genera Run000013_Physics.root
   │                  │
   │                  ▼
5. ACQUISITION ──▶ ANALYSIS
   │                  │
   │                  ├── AnalysisRunner(root_manager).run()
   │                  │   ├── HitAnalysis → analiza hits de partículas
   │                  │   ├── NoiseAnalysis → detecta 8 píxeles ruidosos
   │                  │   └── SystemConfig.set_noisy_pixels(8)
   │                  │
   │                  ├── n_noisy_pixels=8 > NOISY_PIXELS_MAX=5 ✗
   │                  │
   │                  ▼
6. ANALYSIS ──▶ CALIBRATION (condición check_noisy_above_max cumplida)
   │
   └── Volver al paso 2, recalibrar
```

### Escenario: Intento de Transición Inválida

```python
SystemConfig.set_state(SystemState.CALIBRATION)
# ... ejecutar calibración ...

# Intento de ir directo a ACQUISITION (sin pasar por ANALYSIS)
SystemConfig.set_state(SystemState.ACQUISITION)

# ❌ InvalidStateTransitionError:
# "Cannot transition from CALIBRATION to ACQUISITION. 
#  Valid transitions from CALIBRATION: ['IDLE', 'ANALYSIS']"
```

### Escenario: Condición No Cumplida

```python
# En estado ANALYSIS con n_noisy_pixels = 10

SystemConfig.set_state(SystemState.ACQUISITION)

# ❌ TransitionConditionNotMetError:
# "Cannot transition from ANALYSIS to ACQUISITION: 
#  condition 'noisy_pixels_below_threshold' not met."
```

---

## Integración con Análisis

### AnalysisRunner

El `AnalysisRunner` es el componente que conecta la máquina de estados con el análisis:

```python
class AnalysisRunner:
    def run(self) -> AnalysisResult:
        state = self.config.current_state
        
        if state == SystemState.CALIBRATION:
            # Solo análisis de ruido
            self.noise_analysis = NoiseAnalysis(self.root_manager)
            
        elif state == SystemState.ACQUISITION:
            # Análisis completo: hits + ruido
            self.hit_analysis = HitAnalysis(self.root_manager)
            self.noise_analysis = NoiseAnalysis(self.root_manager)
        
        # CRÍTICO: Actualizar SystemConfig con el conteo de píxeles ruidosos
        self.config.set_noisy_pixels(self.n_noisy_pixels)
        
        return self.results
```

### Flujo de Datos

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   RootManager   │────▶│  AnalysisRunner │────▶│   SystemConfig  │
│                 │     │                 │     │                 │
│ - arrays        │     │ - NoiseAnalysis │     │ - _n_noisy_pixels│
│ - load()        │     │ - HitAnalysis   │     │ - set_noisy_pixels()│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              │ n_noisy_pixels
                              ▼
                        ┌─────────────────┐
                        │ TransitionRule  │
                        │                 │
                        │ condition:      │
                        │ check_noisy_*() │
                        └─────────────────┘
```

### AnalysisResult

Contenedor inmutable con los resultados:

```python
@dataclass
class AnalysisResult:
    noise_analysis: NoiseAnalysis | None  # Siempre presente
    hit_analysis: HitAnalysis | None       # Solo en ACQUISITION
    n_noisy_pixels: int                    # Métrica clave para decisiones
    
    @property
    def noisy_pixels(self) -> list | None:
        """Lista de coordenadas (row, col) de píxeles ruidosos."""
        return self.noise_analysis.noisy_pixels if self.noise_analysis else None
```

---

## API de Referencia

### SystemConfig (Singleton)

#### Configuración Inicial

```python
# Obligatorio: llamar UNA vez al iniciar la aplicación
SystemConfig.setup()

# Configurar paths
SystemConfig.configure(
    ph2_acf_dir="/app/Ph2_ACF",
    xml_path="/app/CMSIT_RD53A.xml",
    root_path="/data/Run000010.root",  # Opcional
    txt_base_dir="/app/config"          # Opcional
)
```

#### Gestión de Estados

```python
# Obtener estado actual
state = SystemConfig.get_state()  # SystemState.IDLE

# Cambiar estado (con validación automática)
SystemConfig.set_state(SystemState.CALIBRATION)

# Verificar estado
if SystemConfig.is_state(SystemState.CALIBRATION):
    pass

# Requerir estado específico (lanza excepción si no coincide)
SystemConfig.require_state(SystemState.CALIBRATION, SystemState.ACQUISITION)
```

#### Gestión de Píxeles Ruidosos

```python
# Obtener/establecer conteo (normalmente lo hace AnalysisRunner)
SystemConfig.set_noisy_pixels(3)
n = SystemConfig.get_noisy_pixels()  # 3

# Verificar umbral
if SystemConfig.check_noisy_below_max():
    print("Sistema sano")
elif SystemConfig.check_noisy_above_max():
    print("Necesita recalibración")

# Cambiar umbral
SystemConfig.NOISY_PIXELS_MAX = 10
```

#### Registro de Condiciones

```python
# Para condiciones personalizadas
def my_custom_condition() -> bool:
    return some_check()

SystemConfig.register_transition_condition(
    SystemState.CALIBRATION,
    SystemState.ANALYSIS,
    my_custom_condition
)
```

### Excepciones

| Excepción | Cuándo se lanza |
|-----------|-----------------|
| `InvalidStateTransitionError` | Transición no definida en TRANSITION_RULES |
| `TransitionConditionNotMetError` | Condición dinámica retorna False |
| `InvalidStateError` | `require_state()` falla |
| `SystemNotConfiguredError` | Path requerido no configurado |

---

## Ejemplos de Uso

### Ejemplo 1: Ciclo Completo de Calibración

```python
from rd53_api.config.system_config import SystemConfig
from rd53_api.config.root.root_manager import RootManager
from rd53_api.core.system_state import SystemState
from rd53_api.analysis import AnalysisRunner

# 1. Inicialización
SystemConfig.setup()
SystemConfig.configure(
    ph2_acf_dir="/app/Ph2_ACF",
    xml_path="/app/CMSIT_RD53A.xml"
)

# 2. Iniciar calibración
SystemConfig.set_state(SystemState.CALIBRATION)

# 3. Ejecutar calibración (genera ROOT file)
# ... código de calibración con Ph2_ACF ...

# 4. Preparar análisis
SystemConfig.set_root_path("/data/Run000010_NoiseScan.root")
rm = RootManager(SystemConfig.get_root_path())
rm.load()

# 5. Transición a análisis
SystemConfig.set_state(SystemState.ANALYSIS)

# 6. Ejecutar análisis
runner = AnalysisRunner(rm)
result = runner.run()

print(f"Píxeles ruidosos detectados: {result.n_noisy_pixels}")
print(f"Umbral máximo: {SystemConfig.NOISY_PIXELS_MAX}")

# 7. Decidir siguiente paso
if result.n_noisy_pixels <= SystemConfig.NOISY_PIXELS_MAX:
    print("Calibración exitosa, procediendo a adquisición")
    SystemConfig.set_state(SystemState.ACQUISITION)
else:
    print("Demasiados píxeles ruidosos, recalibrando")
    SystemConfig.set_state(SystemState.CALIBRATION)
```

### Ejemplo 2: Monitoreo Continuo en Adquisición

```python
while True:
    # Ejecutar physics run
    SystemConfig.set_state(SystemState.ACQUISITION)
    # ... adquisición de datos ...
    
    # Analizar
    SystemConfig.set_root_path(f"/data/Run{run_number}_Physics.root")
    rm = RootManager(SystemConfig.get_root_path())
    rm.load()
    
    SystemConfig.set_state(SystemState.ANALYSIS)
    result = AnalysisRunner(rm).run()
    
    # El sistema decide automáticamente
    try:
        SystemConfig.set_state(SystemState.ACQUISITION)
        print(f"Run {run_number} OK - {result.n_noisy_pixels} noisy pixels")
    except TransitionConditionNotMetError:
        print(f"Run {run_number} FAILED - {result.n_noisy_pixels} noisy pixels")
        print("Iniciando recalibración automática...")
        SystemConfig.set_state(SystemState.CALIBRATION)
        # ... ejecutar recalibración ...
```

---

## Diagrama de Estados

```
                              ┌────────────────────────────────────┐
                              │                                    │
                              ▼                                    │
┌─────────┐    xml+ph2    ┌─────────────┐                         │
│         │──────────────▶│             │                         │
│  IDLE   │               │ CALIBRATION │                         │
│         │◀──────────────│             │                         │
└─────────┘   (siempre)   └──────┬──────┘                         │
     │                           │                                 │
     │ xml+ph2                   │ root_path                       │
     │                           │                                 │
     ▼                           ▼                                 │
┌─────────────┐           ┌─────────────┐                         │
│             │◀──────────│             │ n_noisy > MAX           │
│ ACQUISITION │ (siempre) │  ANALYSIS   │─────────────────────────┘
│             │──────────▶│             │
└─────────────┘ root_path └──────┬──────┘
     ▲                           │
     │                           │ n_noisy ≤ MAX
     │     xml+ph2               │
     └───────────────────────────┘

Leyenda:
────────▶  Transición permitida
(texto)    Requisitos/condiciones
```

---

## Configuración Avanzada

### Cambiar Umbral de Píxeles Ruidosos

```python
# Por defecto es 5
SystemConfig.NOISY_PIXELS_MAX = 10

# O en tiempo de ejecución
if high_radiation_environment:
    SystemConfig.NOISY_PIXELS_MAX = 20
```

### Inyectar Condiciones Personalizadas

```python
def check_temperature_ok() -> bool:
    """Solo permitir adquisición si la temperatura es segura."""
    return get_chip_temperature() < 40.0

# Añadir como condición adicional
# Nota: Esto REEMPLAZA la condición existente
SystemConfig.register_transition_condition(
    SystemState.ANALYSIS,
    SystemState.ACQUISITION,
    lambda: (
        SystemConfig.check_noisy_below_max() and 
        check_temperature_ok()
    )
)
```

### Reset del Sistema

```python
# Desde cualquier estado, se puede volver a IDLE
SystemConfig.set_state(SystemState.IDLE)

# Para hacer un reset completo de la configuración
SystemConfig.reset()  # Si está implementado, o recrear la instancia
```

---

## Archivos Involucrados

| Archivo | Propósito |
|---------|-----------|
| `core/system_state.py` | Definiciones de estados, reglas, excepciones |
| `config/system_config.py` | Singleton de configuración y gestión de estados |
| `analysis/analysis_runner.py` | Orquestador que actualiza `n_noisy_pixels` |
| `analysis/analysis_noise.py` | Detecta píxeles ruidosos |
| `analysis/analysis_hit.py` | Analiza hits de física |

---

## Changelog

- **2026-02-20**: Implementación inicial de la máquina de estados
  - `SystemState` enum con 4 estados
  - `TRANSITION_RULES` con validación de paths y condiciones
  - Integración con `AnalysisRunner` para actualización automática de `n_noisy_pixels`
  - `SystemConfig.setup()` para registro de condiciones
