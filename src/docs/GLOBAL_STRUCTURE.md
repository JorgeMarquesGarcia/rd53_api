# GLOBAL STRUCTURE - RD53 API
**Última actualización: 2 de junio de 2026**

---

rd53_api/
│
├── __init__.py
│
├── acquisition/
│   ├── __init__.py
│   ├── maps/
│   │   ├── __init__.py
│   │   ├── base_map.py
│   │   │   └── """Clase abstracta base para mapas de adquisición extendiendo interfaz BaseMap (entrada: ninguna, salida: SettingsDict)"""
│   │   ├── acquisition_map.py
│   │   │   └── """Mapa de adquisición base con triggers (10), binary save habilitado, latencia (39), cero inyección, trigger source (6), HitOr habilitado (entrada: ninguna, salida: dict de ajustes de adquisición)"""
│   │   └── physics_map.py
│   │       └── """Mapa de adquisición de datos de física con triggers configurables y voltaje de umbral lineal (350) para detección de partículas reales (entrada: ninguna, salida: PhysicsMap con parámetros)"""
│   └── scans/
│       ├── __init__.py
│       ├── acquisition_scan.py
│       │   └── """Clase abstracta base para escaneos multi-chip de adquisición con ejecución en Terminal y configuración XML (entrada: lista de chips, timeout, scan_time, salida: output del comando DAQ)"""
│       └── physics.py
│           └── """Escaneo de adquisición de datos de física para detección de partículas reales usando PhysicsMap en chips configurados (entrada: lista de chips, scan_time, salida: datos de adquisición y output del comando)"""
│
├── analysis/
│   ├── __init__.py
│   ├── analysis_base.py
│   │   └── """Clase abstracta base filtrando eventos vacíos y extrayendo chips activos de datos de detectores (entrada: RootManager con datos, salida: clean_data con arrays de eventos/hits)"""
│   ├── analysis_hit.py
│   │   └── """Analiza impactos de partículas aplicando filtrado de trigger y detección de coincidencias entre planos (entrada: RootManager, salida: array de hits filtrados y coordenadas 3D)"""
│   ├── analysis_latency.py
│   │   └── """Analiza datos de escaneo de latencia calculando estadísticas de posición en grupo y recalculando latencia media (entrada: RootManager + ntrig count, salida: estadísticas de posición y estimaciones de latencia)"""
│   ├── analysis_noise.py
│   │   └── """Identifica píxeles ruidosos filtrando eventos multi-hit con valores bajos de Time-over-Threshold (entrada: RootManager, salida: lista de tuplas (row, col) de píxeles ruidosos)"""
│   └── analysis_runner.py
│       └── """Orquesta ejecución de análisis basado en estado del sistema (CALIBRATION ejecuta NoiseAnalysis, ACQUISITION ejecuta HitAnalysis+NoiseAnalysis) (entrada: RootManager + estado del sistema, salida: AnalysisResult con análisis)"""
│
├── calibration/
│   ├── __init__.py
│   ├── maps/
│   │   ├── __init__.py
│   │   ├── base_map.py
│   │   │   └── """Clase abstracta base para mapas de configuración con interfaz to_dict() devolviendo diccionarios de ajustes (entrada: ninguna, salida: SettingsDict con mapeos)"""
│   │   ├── calibration_map.py
│   │   │   └── """Mapa de calibración base con latencia=139, clock delay=280, trigger source, HitOr enable, TDAC reset (entrada: ninguna, salida: dict de ajustes de calibración base)"""
│   │   ├── latency_map.py
│   │   │   └── """Configuración de escaneo de latencia con propiedades para count de eventos (100), rango de latencia (100-140), rango de columnas (128-263) (entrada: ninguna, salida: LatencyScanMap con parámetros validados)"""
│   │   ├── noisescan_map.py
│   │   │   └── """Mapa de escaneo de ruido con event count grande (1e6), burst size (1e4), triggers (10), cero inyección (entrada: ninguna, salida: NoiseScanMap con ajustes de escaneo)"""
│   │   ├── pixelalive_map.py
│   │   │   └── """Mapa de calibración pixel alive con eventos (100), ajustes VCAL (med=100, high=600), rango de columnas, ocupancia alta (0.9) (entrada: ninguna, salida: PixelAliveMap con parámetros)"""
│   │   ├── scurve_map.py
│   │   │   └── """Mapa de escaneo S-curve con event count (100), barrido VCAL (0-255 pasos), triggers (10), inyección habilitada (entrada: ninguna, salida: SCurveMap con parámetros de barrido)"""
│   │   ├── threqu_map.py
│   │   │   └── """Mapa de ecualización de umbral con event count (100), rango VCAL (100-600), inyección habilitada (entrada: ninguna, salida: ThresholdEqualizationMap con ajustes)"""
│   │   └── thrmin_map.py
│   │       └── """Mapa de minimización de umbral con event count grande (1e7), rango de umbral (350-400), target ToT (2000), ocupancia target (1e-6) (entrada: ninguna, salida: ThresholdMinimizationMap)"""
│   └── scans/
│       ├── __init__.py
│       ├── calibration_scan.py
│       │   └── """Clase abstracta base ejecutando escaneos de calibración a través de Terminal con configuración XML (entrada: hybrid_id, rd53_id, map settings, salida: output del comando DAQ)"""
│       ├── latency.py
│       │   └── """Ejecuta escaneo de calibración de latencia usando configuración LatencyScanMap (entrada: parámetros de escaneo, salida: resultados de escaneo de latencia)"""
│       ├── noise.py
│       │   └── """Ejecuta escaneo de ruido usando NoiseScanMap para identificar píxeles ruidosos (entrada: parámetros de escaneo, salida: resultados de escaneo de ruido)"""
│       ├── pixel_alive.py
│       │   └── """Ejecuta escaneo pixel alive usando PixelAliveMap para verificar responsividad de píxeles (entrada: parámetros de escaneo, salida: resultados de escaneo)"""
│       ├── scurve.py
│       │   └── """Ejecuta escaneo S-curve usando SCurveMap para medir curvas de respuesta de píxeles (entrada: parámetros de escaneo, salida: resultados de escaneo S-curve)"""
│       ├── threqu.py
│       │   └── """Ejecuta escaneo de ecualización de umbral usando ThresholdEqualizationMap (entrada: parámetros de escaneo, salida: resultados de ecualización)"""
│       └── thrmin.py
│           └── """Ejecuta escaneo de minimización de umbral usando ThresholdMinimizationMap (entrada: parámetros de escaneo, salida: resultados de minimización)"""
│
├── chip/
│   ├── __init__.py
│   └── register_map.py
│       └── """Enumeraciones para configuraciones del chip RD53A (umbrales, ganancias, latencia) con representaciones de strings (entrada: ninguna, salida: mapeos de nombres de registros/configuraciones)"""
│
├── config/
│   ├── __init__.py
│   ├── base_config_manager.py
│   │   └── """Clase abstracta base definiendo interfaz para todos los gestores de archivos de configuración con load/save/dirty-state tracking (entrada: rutas de archivos, salida: datos de configuración)"""
│   ├── system_config.py
│   │   └── """Singleton gestionando estado del sistema (IDLE, CALIBRATION, ACQUISITION, ANALYSIS) y rutas de configuración con validación de transiciones (entrada: paths y solicitudes de estado, salida: estado validado y rutas)"""
│   ├── acquisition_config.py
│   │   └── """Helper estático configurando ajustes de adquisición (directorio Ph2_ACF, ruta XML) en SystemConfig singleton (entrada: ph2_acf_dir, xml_path, salida: SystemConfig configurado con XmlManager)"""
│   ├── analysis_config.py
│   │   └── """Helper estático configurando ajustes de análisis (ruta archivo ROOT) en SystemConfig singleton (entrada: root_path, salida: SystemConfig configurado con ruta ROOT)"""
│   ├── calibration_config.py
│   │   └── """Helper estático configurando ajustes de calibración en SystemConfig singleton (entrada: base_dir, chip_id, salida: SystemConfig configurado con TxtManager)"""
│   ├── root/
│   │   ├── __init__.py
│   │   └── root_manager.py
│   │       └── """Carga archivos ROOT de datos de detectores con detección automática de archivos más recientes (entrada: ruta ROOT, salida: arrays con datos de eventos/hits)"""
│   ├── txt/
│   │   ├── __init__.py
│   │   └── txt_manager.py
│   │       └── """Gestiona archivos TXT de configuración de registros: lectura de máscaras de píxeles y estados (entrada: ruta TXT + base_dir, salida: Mask con estados de píxeles)"""
│   └── xml/
│       ├── __init__.py
│       └── xml_manager.py
│           └── """Gestiona archivos XML de configuración RD53A: lectura/escritura con auto-guardado (entrada: ruta XML, salida: árbol de configuración con ajustes de chip)"""
│
├── core/
│   ├── __init__.py
│   ├── base_map.py
│   │   └── """Clase abstracta base para todos los mapas de configuración (calibración & adquisición) con interfaz to_dict() (entrada: ninguna, salida: SettingsDict con mapeos)"""
│   ├── decorators.py
│   │   └── """Decorador asegurando que los recursos están cargados antes de la ejecución de operaciones (entrada: función, salida: función envuelta con pre-chequeo)"""
│   ├── exceptions.py
│   │   └── """Define jerarquía de excepciones personalizadas para errores de XML/TXT/ROOT, análisis y violaciones de estado del sistema (entrada: detalles de error, salida: mensajes de excepción contextuales)"""
│   ├── mask.py
│   │   └── """Representación de máscara de píxeles para detector RD53A (192 filas × 400 columnas) con arrays de registros enable/disable/hitBUS/injEN/TDAC (entrada: ninguna, salida: objeto Mask con estados de control de píxeles)"""
│   └── num_manager.py
│       └── """Gestor de número de ejecución para leer/escribir RunNumber.txt con soporte de output formateado (entrada: ruta de archivo, salida: número de ejecución como int o string formateado)"""
│
├── docs/
│   ├── GLOBAL_STRUCTURE.md
│   │   └── """Estructura completa y documentación del proyecto rd53_api (entrada: ninguna, salida: documento markdown con jerarquía de componentes)"""
│   ├── STATE_MACHINE.md
│   │   └── """Documentación de máquina de estados del sistema con diagramas y transiciones (entrada: ninguna, salida: documento markdown con especificación de estados)"""
│   ├── StateMachine_architecture.md
│   │   └── """Arquitectura técnica de la máquina de estados con ejemplos de uso (entrada: ninguna, salida: documento markdown detallado)"""
│   ├── StateMachine_architecture.docx [NUEVO]
│   │   └── """Versión Word de arquitectura de máquina de estados (entrada: ninguna, salida: documento Word)"""
│   ├── StateMachine_architecture.pdf [NUEVO]
│   │   └── """Versión PDF de arquitectura de máquina de estados (entrada: ninguna, salida: documento PDF)"""
│   ├── StateMachine_architecture.png [NUEVO]
│   │   └── """Diagrama visual de arquitectura de máquina de estados (entrada: ninguna, salida: imagen PNG)"""
│   └── version_rev.txt
│       └── """Registro de versiones y revisiones del proyecto (entrada: ninguna, salida: historial de versiones)"""
│
├── backup/
│   ├── plot.py
│   └── plot1.py
│
├── gui/
│   ├── __init__.py
│   ├── app.py
│   │   └── """Punto de entrada principal de aplicación QT (entrada: ninguna, salida: aplicación QT ejecutable)"""
│   ├── main_window.py
│   │   └── """Ventana principal QMainWindow con tabs para configuración, calibración y adquisición (entrada: ninguna, salida: ventana principal con interfaz integrada)"""
│   └── tabs/
│       ├── __init__.py
│       ├── config_tab.py
│       │   └── """Tab de configuración del sistema con selección de rutas y parámetros (entrada: SystemConfig, salida: UI de configuración)"""
│       ├── calibration_tab.py
│       │   └── """Tab de calibración con control de escaneos (PixelAlive, SCurve, Latency, Noise) (entrada: SystemConfig, salida: UI de calibración)"""
│       └── acquisition_tab.py
│           └── """Tab de adquisición de datos con triggers y control de física (entrada: SystemConfig, salida: UI de adquisición)"""
│
├── plots/
│   └── [9 archivos PNG de coincidencias - NUEVO]
│       ├── Coincidence_20260512_061215.png
│       ├── Coincidence_20260512_061838.png
│       ├── Coincidence_20260512_112235.png
│       ├── Coincidence_20260513_090916.png
│       ├── Coincidence_20260513_091108.png
│       ├── Coincidence_20260514_072610.png
│       ├── Coincidence_20260514_072642.png
│       ├── Coincidence_20260514_073406.png
│       └── Coincidence_20260514_081754.png
│           └── """Visualizaciones de trayectorias de coincidencia con vista 2D/3D de detectores y análisis de eventos"""
│
├── plotter/
│   ├── __init__.py
│   ├── heatmap.py
│   │   └── """Plotter genérico para TH2F de Column vs Row del chip RD53A con logging integral. Soporta máscaras de región activa con colormaps específicos y límites visuales (entrada: root_path, canvas_path, col_start, col_end, salida: FigureCanvas matplotlib)"""
│   ├── histogram1d.py
│   │   └── """Plotter para histogramas TH1F del chip RD53A. Dibuja barras con línea de media y banda ±σ sombreada con logging de control (entrada: root_path, canvas_path, salida: FigureCanvas con estadísticas)"""
│   ├── plotter_base.py
│   │   └── """Clase abstracta base para todos los plotters de RD53A con registry automático. Métodos helpers para extracción de ROOT (TH1/TH2) y conversión a numpy arrays. Logging integral de todo el flujo (entrada: root_path, canvas_path, salida: FigureCanvas)"""
│   ├── plotter_trajectory.py
│   │   └── """Plotter para visualización de trayectorias de partículas con detección automática de geometría del detector (entrada: datos de trayectorias, lista de chips activos, salida: figura 3D matplotlib)"""
│   ├── scurve.py
│   │   └── """Plotter especializado para SCurves (TH2F Efficiency vs ΔVCal). Dibuja mapa de calor 2D + perfil medio con banda ±σ y barras de error (entrada: root_path, canvas_path, salida: FigureCanvas con perfil)"""
│   └── trajectory_interactive.py
│       └── """Visualización interactiva 3D de detector con animación de trayectorias de partículas y resaltado de planos de sensor (entrada: array plot_coord_data, lista active_chips, salida: figura matplotlib 3D animada)"""
│
├── remote/
│   ├── __init__.py
│   └── terminal.py
│       └── """Gestor de sesión Terminal usando pexpect para ejecución de comandos bash con detección de errores y control de timeout (entrada: comandos bash, salida: output del comando, soporta context manager)"""
│
├── results/
│   ├── __init__.py
│   ├── acquisition_result.py
│   │   └── """Contenedor de resultados de adquisición con datos y metadata (entrada: datos de evento, salida: AcquisitionResult serializable)"""
│   ├── analysis_result.py
│   │   └── """Contenedor de resultados de análisis con estadísticas y hits procesados (entrada: datos analizados, salida: AnalysisResult serializable)"""
│   ├── orchestration_result.py
│   │   └── """Contenedor de resultados de orquestación con secuencia completa de calibración/adquisición/análisis (entrada: resultados parciales, salida: OrchestrationResult)"""
│   └── scan_result.py
│       └── """Contenedor genérico de resultados de scan con datos crudos y procesados (entrada: datos de scan, salida: ScanResult)"""
│
├── test/
│   ├── __init__.py
│   ├── analysis_base_test.py
│   ├── analysis_runner_test.py
│   ├── cal_test.py
│   ├── hit_analysis_test.py
│   ├── hits_test.py
│   ├── latency_analysis_test.py
│   ├── noise_analysis_test.py
│   ├── plot_test.py
│   ├── root_test.py
│   ├── run_acquisition_real.py
│   ├── run_state_machine_inv.py
│   ├── run_state_machine.py
│   ├── run_test.py
│   ├── system_config_test.py
│   ├── system_state_test.py
│   ├── terminal_test.py
│   ├── test_plotter.py
│   ├── test_root.py
│   ├── txt_test.py
│   └── xml_test.py
│
└── workflow/
    ├── __init__.py
    ├── state_orchestrator.py
    │   └── """Orquestador de alto nivel ejecutando secuencias de calibración, callbacks de adquisición y análisis con transiciones automáticas de estado (entrada: lista CalibrationSteps, executor de adquisición, salida: OrchestrationResult con estado y resultado)"""
    └── system_state.py
        └── """Define estados del sistema (IDLE, CALIBRATION, ACQUISITION, ANALYSIS), reglas de transición con condiciones y lógica de validación de estado (entrada: transiciones de estado, salida: próximos estados válidos o error)"""

---

## DESCRIPCIÓN GENERAL

### Propósito
**rd53_api** es una API Python completa para el control, calibración, adquisición y análisis de datos del detector RD53A. Proporciona una arquitectura modular con máquina de estados para gestionar flujos de trabajo complejos de física experimental.

### Arquitectura Principal (7 Capas)
1. **Capas de Configuración** (`config/`): Gestión centralizada de estados del sistema y archivos de configuración (XML, TXT, ROOT)
2. **Flujo de Calibración** (`calibration/`): Mapas y escaneos especializados para calibración del chip RD53A
3. **Capas de Adquisición** (`acquisition/`): Mapas y escaneos para adquisición de datos de detectores
4. **Análisis de Datos** (`analysis/`): Procesamiento y análisis de eventos, hits y trayectorias
5. **Visualización** (`plotter/`): Plotters especializados para diferentes tipos de datos (heatmaps, S-curves, trayectorias 3D)
6. **Orquestación** (`workflow/`): Máquina de estados para ejecutar secuencias complejas
7. **GUI** (`gui/`): Interfaz gráfica QT con tabs para configuración, calibración y adquisición

### Módulos Utilitarios
- **Core** (`core/`): Base abstracts, decorators, masks y gestión de excepciones
- **Remote** (`remote/`): Gestor Terminal para ejecución de comandos bash
- **Results** (`results/`): Contenedores serializables para resultados
- **Chip** (`chip/`): Enumeraciones de configuración del chip RD53A

### Flujo de Trabajo Típico
```
IDLE → CALIBRATION (Sequence: Pixel Alive → S-curve → Latency → Noise)
     → ACQUISITION (Datos de física o triggers de sincronización)
     → ANALYSIS (Hit Analysis + Noise Analysis)
     → IDLE
```

### Cambios Recientes (2 junio 2026)
- ✅ Agregada carpeta `plots/` con 9 visualizaciones de coincidencias (PNG)
- ✅ Expandida documentación en `docs/` con versiones PDF, Word e imagen PNG
- ✅ Mejorada GUI con tabs: Config, Calibration, Acquisition
- ✅ Sistema de logging integral en todos los plotters

### Estadísticas del Proyecto
| Métrica | Valor |
|---------|-------|
| **Archivos Python** | 79 |
| **Directorios principales** | 16 |
| **Subdirectorios** | 11 |
| **Niveles de profundidad** | 3 |
| **Archivos de documentación** | 7 |
| **Visualizaciones PNG** | 9 |
| **Módulos de test** | 21 |

---

**Estructura organizada para máxima escalabilidad y mantenibilidad del flujo de procesamiento de datos del detector RD53A. Último commit: 2 de junio de 2026**