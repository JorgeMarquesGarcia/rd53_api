# Alineamiento del telescopio RD53A con rayos cósmicos
**Fecha: 14 de octubre de 2026**
**Datos de referencia:** `Run000401_Physics_Board000.root` (unas 20 h de rayos cósmicos)

---

## Índice

1. [Resumen](#1-resumen)
2. [Contexto: telescopio, trigger y análisis de hits](#2-contexto-telescopio-trigger-y-análisis-de-hits)
3. [Filtro de planos de coincidencia en la GUI](#3-filtro-de-planos-de-coincidencia-en-la-gui)
4. [El problema: trayectorias que no pasan por los impactos](#4-el-problema-trayectorias-que-no-pasan-por-los-impactos)
5. [Diagnóstico](#5-diagnóstico)
6. [Modelo de alineamiento](#6-modelo-de-alineamiento)
7. [Correcciones aplicadas, paso a paso](#7-correcciones-aplicadas-paso-a-paso)
8. [Interpretación física de los desplazamientos](#8-interpretación-física-de-los-desplazamientos)
9. [Geometría final y cambios en el código](#9-geometría-final-y-cambios-en-el-código)
10. [Historial de versiones](#10-historial-de-versiones)
11. [Limitaciones y trabajo futuro](#11-limitaciones-y-trabajo-futuro)
12. [Procedimiento para repetir el alineamiento](#12-procedimiento-para-repetir-el-alineamiento)

---

## 1. Resumen

Las trayectorias reconstruidas con la geometría nominal del telescopio no pasaban por
los impactos medidos: con tres planos, el plano central quedaba hasta 76 px (3.8 mm)
fuera de la recta ajustada. El análisis de los datos del Run000401 llevó a estas
conclusiones:

1. **Las coincidencias son partículas reales, no ruido.** Los hits de H1 y H2 caen en
   el BX del trigger, y H1 y H2 apenas tienen ruido.
2. **El plano H0 (tarjeta de un solo chip, plano de trigger) está montado girado 180°**
   respecto a los quads H1 y H2. Se dedujo de los datos y se confirmó después en el
   hardware.
3. **Las distancias entre planos no son las del diseño 3D.** Los tracks miden una
   proporción d(H0–H1)/d(H1–H2) = 0.45 ± 0.02, frente a 0.24 en el diseño.
4. **Hay un desalineo relativo en XY** equivalente a mover H0 (+27, +35) px =
   (1.35, 1.75) mm respecto a los quads.

Con las tres correcciones aplicadas por software, el RMS de los residuos de los tracks
de 3 planos baja de **25.6 px a 2.0 px** (de 1.3 mm a 0.1 mm). La mediana de la
desviación del plano central baja de 42.7 px a 1.1 px. El detector se sigue dibujando
perfectamente alineado: las correcciones solo afectan a la posición de los hits.

| Etapa | RMS residuos (px) | Desviación máx. plano central (px) | Mediana (px) |
|---|---|---|---|
| Original: sin giro, Z = 0/3/6 (u.a.) | 25.6 | 76.3 | 42.7 |
| Giro 180° de H0, Z = 0/3/6 | 12.0 | 29.0 | 20.0 |
| Giro + Z del diseño (0 / 4.6 / 23.6 mm) | 9.9 | 24.2 | 15.5 |
| Giro + Z del diseño + alineamiento de H0 (21, 31) px | 3.3 | 9.4 | 4.7 |
| Giro + Z ajustada (0 / 7.3 / 23.6 mm) | 10.2 | 26.6 | 14.3 |
| **Giro + Z ajustada + alineamiento (final)** | **2.0** | **11.2** | **1.1** |

*Métrica: residuos del ajuste por mínimos cuadrados de una recta a los tres impactos,
en los dos ejes (fila y columna), sobre los 10 tracks de 3 planos válidos (se excluye
el evento 1355, sección 7.2). 1 px = 50 µm. El máximo de la última fila es el evento
7750, que sigue siendo atípico.*

---

## 2. Contexto: telescopio, trigger y análisis de hits

### 2.1 Telescopio

| Plano | Hybrid | Tipo | Chips activos en el Run000401 |
|---|---|---|---|
| Z0 (superior) | H0 | Tarjeta de un solo chip (SCC) | chip 0 |
| Z1 | H1 | Quad (2×2 chips) | lane 0 |
| Z2 | H2 | Quad (2×2 chips) | lane 0 |

- Chip RD53A: 400 columnas × 192 filas, píxeles de 50 × 50 µm.
- Solo está habilitado el front-end **LIN**: columnas 128–263 (136 columnas), es decir,
  una zona activa de 6.8 mm (columnas) × 9.6 mm (filas) por chip.
- En la geometría nominal, el chip de H0 y la lane 0 de los quads comparten origen, y la
  zona LIN de los tres chips queda superpuesta.

### 2.2 Trigger

- Las adquisiciones usan `trigger_source = 6` (**HitOr**) con `HitOr_enable_l12 = 1`
  (`src/acquisition/maps/acquisition_map.py`).
- El análisis trata el plano 0 (H0) como plano de trigger. Los datos lo confirman: el
  87 % de los hits de H0 (5498 de 6322) caen en el BX 2 de la ventana de trigger.
- Cada trigger lee una ventana de `nTRIGxEvent` BX consecutivos (posiciones 1–4 con
  hits en este run).

### 2.3 Datos del Run000401

| Magnitud | Valor |
|---|---|
| Duración aproximada | 20 h |
| Entradas del TTree (BX) | 10310 |
| Ventanas de trigger con hits | 2007 (2004 con hits en H0) |
| Hits en H0 / H1 / H2 | 6865 / 115 / 45 |
| Píxeles ruidosos enmascarados (NoiseAnalysis) | 428, todos en H0 |
| Hits de H0 tras la máscara | 6322 |
| Tracks reconstruidos | 96 |
| … con hits en H0+H1 / H0+H2 / H0+H1+H2 | 72 / 13 / 11 |

### 2.4 Cadena de HitAnalysis (`src/analysis/analysis_hit.py`)

1. NoiseAnalysis marca los píxeles ruidosos y sus hits se descartan.
2. Las entradas de cada ventana de trigger se agrupan en un solo evento.
3. Filtro de trigger: se exige un hit en el plano 0.
4. Filtro de coincidencia: se exige al menos un hit en otro plano.
5. Filtro de ToT: se descarta el evento solo si todos sus hits tienen ToT < 2.
6. En cada plano se toma el hit de máximo ToT y se pasa a coordenadas globales con
   `to_global`.
7. El plotter ajusta una recta x(z), y(z) por mínimos cuadrados y la dibuja en 3D.

---

## 3. Filtro de planos de coincidencia en la GUI

Con 96 tracks el dibujo se saturaba. Se añadió en el *Analysis tab* (modo Acquisition),
junto a *Animate trajectories*, un selector **Coincidence planes** (2 o 3):

- Es el **número mínimo de planos con hit** que debe tener un track para dibujarse. Un
  plano es una posición Z distinta: dos chips de un mismo quad cuentan como un plano.
- Con 2 se dibujan todos los tracks (comportamiento anterior). Con 3, solo los que
  cruzan los tres planos.
- Solo afecta al dibujo: el análisis y su log no cambian. La cabecera indica, por
  ejemplo, *"11 of 96 tracks with hits in at least 3 planes"*, y lo mismo se escribe en
  el log.
- Implementación: `track_planes()` y `N_PLANES` en `src/gui/tabs/analysis_tab.py`.

Este filtro aisló los 11 tracks de 3 planos con los que se hizo todo el alineamiento.

---

## 4. El problema: trayectorias que no pasan por los impactos

Con tres puntos, la recta de mínimos cuadrados solo pasa por ellos si son colineales.
Con tres planos equiespaciados, los residuos tienen siempre la forma (a, −2a, a): la
recta pasa "por en medio". En los datos originales la desviación del plano central
llegaba a 76 px (3.8 mm), con signos aleatorios de un track a otro.

Esa desviación es muy grande comparada con las fuentes de error esperables:

| Fuente | Orden de magnitud |
|---|---|
| Resolución del píxel (50 µm / √12) | ~0.3 px (14 µm) |
| Usar el píxel de máximo ToT en lugar del centroide del cluster | ~±1 px |
| Dispersión múltiple de un muón de ~GeV en el material del telescopio | ~1 px |
| **Desviación observada** | **hasta 76 px** |

---

## 5. Diagnóstico

### 5.1 ¿Coincidencias por ruido? No

La primera hipótesis era que un chip ruidoso produjera coincidencias accidentales. Se
descartó por tres motivos:

- **Tiempo.** Los hits de H1 y H2 caen en el BX del trigger o justo después.
  El ruido aleatorio se repartiría uniformemente por toda la ventana.

  | Posición en la ventana (BX) | 1 | 2 | 3 | 4 |
  |---|---|---|---|---|
  | H0 (trigger) | 309 | **5498** | 511 | 4 |
  | H1 | 8 | **54** | **43** | 10 |
  | H2 | 5 | **39** | 1 | 0 |

  Diferencia de BX entre el hit de máximo ToT de H1/H2 y el de H0: ΔBX = 0 en 52
  casos, +1 en 47, −1 en 2 y +2 en 6. El +1 BX corresponde a hits de ToT bajo:
  es el *time walk* del front-end LIN.
- **Ocupación.** H1 y H2 tienen 115 y 45 hits en 20 h y ningún píxel ruidoso. H0 sí es
  ruidoso (428 píxeles enmascarados), pero como es el plano de trigger tiene hit en
  todas las ventanas por construcción, así que su ruido no fabrica coincidencias con
  H1/H2.
- **Topología.** En las ventanas con track, los hits de H0 forman clusters compactos
  (extensión mediana de 1 px), es decir, impactos reales.

### 5.2 Correlación de posiciones entre planos

En un telescopio bien descrito, la posición del impacto en un plano se correlaciona con
la del siguiente:

| Pareja | Nº tracks | corr. columna–columna | corr. fila–fila |
|---|---|---|---|
| H0–H1 | 83 | −0.12 | −0.25 |
| H0–H2 | 24 | −0.22 | −0.38 |
| **H1–H2** | 11 | **+0.71** | **+0.78** |

- H1 y H2 ven la misma partícula en posiciones coherentes.
- H0 no se correlaciona con ninguno; incluso sale algo negativo. La dispersión de la
  diferencia de posiciones H0–H1 (58 px en columnas, 79 en filas) es la misma que si
  las posiciones fueran independientes (56 y 78 px).
- Conclusión: las coordenadas de H0 están en un sistema de referencia equivocado.

### 5.3 Orientación de H0

Se probaron las cuatro orientaciones posibles de H0 con los 11 tracks de 3 planos,
dejando libres la proporción de distancias y un desplazamiento:

| Orientación de H0 | RMS del ajuste (px) |
|---|---|
| Tal cual (geometría nominal) | 79.8 |
| Espejo en filas | 46.0 |
| Espejo en columnas | 69.4 |
| **Giro de 180° (espejo en los dos ejes)** | **13.6** |

- Quitando los dos tracks atípicos (eventos 1355 y 7750), con H0 girado los 9 restantes
  quedan rectos con 1.5 px de RMS (~75 µm).
- **Test de control:** se repartieron al azar los hits de H0 entre tracks. En 2000
  permutaciones, ninguna bajó de 13.6 px (mediana 58 px). La mejora no es casualidad.
- **Giro, no volteo:** si la placa estuviera dada la vuelta (cara abajo), se invertiría
  un solo eje. Los datos prefieren claramente el giro de 180° en su plano, con los dos
  ejes invertidos.

**Confirmación:** al revisar el montaje se comprobó que el plano superior (H0) está
girado 180°. Como el montaje no se puede cambiar, la corrección se hace por software.

---

## 6. Modelo de alineamiento

### 6.1 Rectas y "kink"

Cada track es una recta en cada eje: x(z) = a + b·z, por separado en filas y en
columnas. Con tres planos en z₀ < z₁ < z₂, toda la información sobre el alineamiento
está en la desviación del plano central respecto a la recta que une los planos
exteriores (*kink*):

$$\kappa = x_1 - \left[(1-f)\,x_0 + f\,x_2\right], \qquad f = \frac{z_1 - z_0}{z_2 - z_0}$$

Los residuos del ajuste por mínimos cuadrados son proporcionales a κ.

### 6.2 Qué se puede medir con tres planos

- **Escala en Z.** Escalar todo el eje Z deja las rectas igual de rectas. Solo se mide
  la proporción f (o d₀₁/d₁₂), no las distancias absolutas.
- **Desplazamientos en XY.** Un desplazamiento s_i del plano i cambia el kink en

  $$\Delta\kappa = -(1-f)\,s_0 + s_1 - f\,s_2 = \mathbf{c}\cdot\mathbf{s}, \qquad \mathbf{c} = \left(-(1-f),\ 1,\ -f\right)$$

  Las combinaciones s_i = α + β·z_i (traslación común e inclinación común de todo el
  telescopio) no cambian κ: no se pueden medir. Con tres planos solo se mide **una
  combinación** de los tres desplazamientos por eje, es decir, el desalineo relativo.

### 6.3 Ajustes

- **Desplazamiento de un plano con f fija.** Solución cerrada por eje: el
  desplazamiento de H0 que anula el kink medio es s₀ = ⟨κ⟩ / (1 − f).
- **Proporción f con desplazamiento fijo.** Mínimos cuadrados lineales:
  f = Σ(x₂ − x₀)(x₁ − x₀) / Σ(x₂ − x₀)², usando los dos ejes a la vez.
- **Ajuste conjunto.** Alternando los dos pasos anteriores hasta que dejan de cambiar,
  se llega al mínimo conjunto de mínimos cuadrados en (f, s).
- **Incertidumbres:** *bootstrap* sobre los tracks (2000–5000 remuestreos).
- **Validación:** *leave-one-out*. Se ajusta con todos los tracks menos uno y se mide
  el kink del que queda fuera, rotando cuál se deja fuera.

---

## 7. Correcciones aplicadas, paso a paso

### 7.1 Giro de H0 y distancias del diseño 3D

- H0 se gira 180° dentro de su propio rectángulo: el píxel local (fila, col) pasa a
  (191 − fila, 399 − col) antes de sumar el origen del chip.
- Distancias entre planos tomadas del diseño 3D: H0–H1 = 4.6 mm, H1–H2 = 19 mm. Las
  posiciones Z pasan a estar en mm (0 / 4.6 / 23.6), frente a las unidades arbitrarias
  equiespaciadas de antes (0 / 3 / 6).
- Resultado: RMS de 25.6 a 9.9 px. Las desviaciones restantes del plano central
  (10–17 px) tenían **el mismo signo en todos los tracks**, lo que delata un desalineo
  constante.

### 7.2 Alineamiento residual en XY, con las distancias del diseño

- Se ajustó el desplazamiento de H0 con la solución cerrada de la sección 6.3, con
  rechazo iterativo de tracks atípicos (umbral de 3σ).
- Solo se rechazó el **evento 1355**: su hit de H0 llega un BX antes que los de H1/H2
  (BX 1 frente a BX 2), así que probablemente es otro hit.
- Resultado: H0 (+21, +31) px = (1.05, 1.55) mm en (fila, columna), con ±3 px
  (bootstrap). RMS de 9.9 a 3.3 px.

### 7.3 Distancias Z ajustadas con los tracks y alineamiento fino

En lugar de las distancias del diseño se ajustó la proporción f con los tracks,
alternando con el alineamiento en XY hasta converger. Se mantuvo la distancia total
H0–H2 del diseño (23.6 mm), porque la escala absoluta no es medible.

| Pasada | f | d₀₁ / d₁₂ (mm) | Desplazamiento extra de H0 (fila, col) px | RMS (px) |
|---|---|---|---|---|
| Diseño | 0.195 | 4.60 / 19.00 | — | 3.28 |
| 1 | 0.277 | 6.55 / 17.05 | (4.4, 2.8) | 2.10 |
| 2 | 0.299 | 7.07 / 16.53 | (5.8, 3.7) | 1.97 |
| 3 | 0.307 | 7.24 / 16.36 | (6.3, 4.1) | 1.96 |
| Convergencia | 0.311 | **7.34 / 16.26** | (6.5, 4.2) | **1.96** |

- Proporción medida: d₀₁/d₁₂ = **0.45 ± 0.02**, frente a 0.24 en el diseño.
- Intervalo del 95 % para d₀₁ (bootstrap, con 23.6 mm de total): [6.80, 7.61] mm. Los
  4.6 mm del diseño quedan excluidos.
- Alineamiento de H0 correspondiente: (+27.6, +35.3) px ≈ (1.38, 1.76) mm.
- **Validación leave-one-out** (kink del track no usado en el ajuste):

  | Modelo | Media (px) | Mediana (px) |
  |---|---|---|
  | Z del diseño + alineamiento ajustado | 9.4 | 8.7 |
  | Z ajustada + alineamiento ajustado | 4.1 | 2.2 |

  Mejoran 9 de los 10 tracks; solo empeora el 7750. La mejora se mantiene en tracks que el ajuste no ha visto,
  así que no es un sobreajuste por tener un parámetro libre más.
- Valores redondeados en el código: **d₀₁ = 7.3 mm, d₁₂ = 16.3 mm** y H0 (+27, +35) px.
  Incertidumbre: ±1 px en filas y ±3 px en columnas. La columna depende del evento
  7750: sale 35 con él y 32 sin él.

### 7.4 Alineamiento invisible para el usuario

Requisito: en los plots el detector debe verse perfectamente alineado.

- **Dibujo y hits separados.** Los chips se dibujan en su posición nominal. El
  alineamiento solo se suma al situar los hits (`to_global`, `to_local`).
- **Reparto del desalineo.** Si toda la corrección se pone en H0, 11 de sus 96 impactos
  quedan fuera del chip dibujado, hasta 25 px (1.25 mm), y se nota. Como solo se mide
  el desalineo relativo (sección 6.2), se reparte entre los tres planos con la solución
  de **mínima norma**, que es la que menos aleja cada impacto de su píxel nominal:

  $$\mathbf{s} = \frac{K}{\mathbf{c}\cdot\mathbf{c}}\,\mathbf{c}, \qquad K = -(1-f)\,S_{H0}$$

  Con f = 7.3/23.6 y S_H0 = (27.4, 35.2) px:

  | Plano | Alineamiento (fila, col) px | mm |
  |---|---|---|
  | H0 | (+8, +11) | (+0.40, +0.55) |
  | H1 | (−12, −15) | (−0.60, −0.75) |
  | H2 | (+4, +5) | (+0.20, +0.25) |

- Resultado: los residuos de los tracks son idénticos a los de poner toda la corrección
  en H0. Solo 7 de 203 impactos quedan fuera de su chip dibujado, como mucho 10 px
  (0.5 mm), menos que el tamaño del marcador en pantalla.

---

## 8. Interpretación física de los desplazamientos

### 8.1 El cubo del diseño 3D

Para garantizar la coincidencia, en el diseño 3D se alineó la zona LIN de cada chip con
un prisma de sección 11.8 × 6.818 mm. La zona LIN mide 9.6 × 6.8 mm:

- **Filas:** 11.8 − 9.6 = **2.2 mm de holgura**. El LIN de cada chip pudo quedar en
  cualquier punto de ese margen.
- **Columnas:** 6.818 − 6.8 ≈ **0.02 mm**: prácticamente sin holgura.

### 8.2 Desplazamiento LIN a LIN medido

Expresando el ajuste como desplazamiento de la zona LIN de H0 respecto a la de los
quads (toda la corrección atribuida a H0):

| Hipótesis | Columnas | Filas | RMS del kink (px) |
|---|---|---|---|
| Distancias ajustadas, desplazamiento libre | +2.16 mm | +1.38 mm | 4.3 |
| Distancias del diseño, desplazamiento libre | +1.93 mm | +1.04 mm | 7.4 |
| Columnas forzadas a 0 (lo que implica el cubo) | 0 | +1.59 mm | **21.3** |

- **Filas: compatible con el cubo.** 1.0–1.4 mm cabe en los 2.2 mm de holgura, y el
  giro de H0 pone su LIN en el lado opuesto de esa holgura respecto a los quads.
- **Columnas: el cubo no lo explica.** Forzar columnas alineadas multiplica el RMS por
  cinco: los datos piden un desplazamiento de ~2 mm en columnas.

### 8.3 Explicación propuesta: giro alrededor de un eje descentrado

Un giro de 180° alrededor de un eje vertical equivale a un giro alrededor del centro
del LIN más una traslación igual al **doble** de la distancia entre el eje y el centro
del LIN. Los desplazamientos medidos, ~(2.0, 1.2) mm en (columna, fila), encajan si el
centro del LIN de H0 está a unos **(1.0, 0.6) mm** del eje sobre el que quedó girada la
placa (por ejemplo, el centro de sus taladros de montaje). Contribuyen:

- El LIN no está centrado en el chip (columnas 128–263, frente al centro en la 200):
  aporta 0.4 mm en columnas.
- La periferia del chip está en un solo lado, lo que descentra la matriz en filas.
- La posición del chip sobre la PCB de la tarjeta.

Comprobación pendiente: medir en el diseño 3D la distancia entre el centro del LIN de
H0 y el eje de giro de su placa.

### 8.4 Distancias en Z

La discrepancia en d₀₁ (7.3 mm medida frente a 4.6 mm de diseño, con el total fijo) no
se explica con el cubo. Una posibilidad a verificar es que las distancias del diseño se
midan entre superficies de montaje y no entre los planos de los sensores (cara de la
PCB en la que va el chip, grosor del módulo quad, separadores). Como solo se mide la
proporción, otras lecturas son igual de compatibles con los tracks: si H1–H2 = 19 mm es
exacto, H0–H1 sería 8.6 mm; si H0–H1 = 4.6 mm es exacto, H1–H2 sería 10.2 mm. Elegir una
u otra solo cambia el dibujo, no la rectitud de los tracks.

---

## 9. Geometría final y cambios en el código

### 9.1 Parámetros (`src/chip/detector_geometry.py`)

| Parámetro | Valor | Origen |
|---|---|---|
| Giro de H0 (`rotation`) | 180° | Datos (sección 5.3) + confirmación en hardware |
| `Z_GAP_LAYER_0_1` | 7.3 mm | Ajuste con tracks (diseño: 4.6 mm) |
| `Z_GAP_LAYER_1_2` | 16.3 mm | Ajuste con tracks (diseño: 19.0 mm) |
| `LAYER_ALIGNMENT[0]` (H0) | (+8, +11) px | Ajuste con tracks, reparto de mínima norma |
| `LAYER_ALIGNMENT[1]` (H1) | (−12, −15) px | Ídem |
| `LAYER_ALIGNMENT[2]` (H2) | (+4, +5) px | Ídem |

### 9.2 API de geometría

| Función | Qué devuelve | ¿Incluye alineamiento? |
|---|---|---|
| `nominal_origin(h, lane)` | Origen nominal del chip (donde se dibuja) | No |
| `chip_origin(h, lane)` | Origen para situar los hits | Sí |
| `to_global(h, lane, row, col)` | Coordenada global de un píxel (giro + origen + alineamiento) | Sí |
| `to_local(h, lane, row, col)` | Inversa exacta de `to_global` | Sí |
| `chip_bounds(h, lane)` | Rectángulo del chip para dibujarlo | No |
| `z_position(h)`, `z_range()` | Posiciones Z en mm | — |

### 9.3 Ficheros modificados

| Fichero | Cambio |
|---|---|
| `src/chip/detector_geometry.py` | Campos `rotation` y `alignment` por capa; Z en mm; `to_local` y `nominal_origin`; `chip_bounds` y `detector_extent` en posición nominal |
| `src/plotter/detector_planes.py` | Margen del track (4 mm) y grosor de las láminas (0.8 mm) en mm |
| `src/plotter/trajectory_interactive.py` | Las etiquetas de los impactos usan `to_local`: siguen mostrando la coordenada local real del píxel, también en H0 girado |
| `src/analysis/analysis_hit.py` | Solo docstring |
| `src/gui/tabs/analysis_tab.py` | Selector *Coincidence planes* |

### 9.4 Qué no cambia

- Máscaras, ficheros TXT y XML, noise maps y heatmaps trabajan en coordenadas locales
  del chip y no se ven afectados.
- El log de HitAnalysis sigue escribiendo las coordenadas locales de cada hit.
- Los ficheros `.root` antiguos que se vuelvan a analizar usan automáticamente la
  geometría nueva.

---

## 10. Historial de versiones

| Commit / estado | Contenido |
|---|---|
| `77784b8` | Giro de H0, distancias del diseño (4.6 / 19 mm) y selector *Coincidence planes* |
| `ed9e80f` — tag `v1.3-detector-alignment` | Alineamiento residual de H0 (+21, +31) px con las distancias del diseño |
| Working tree (sin commit al escribir este documento) | Distancias ajustadas (7.3 / 16.3 mm), alineamiento repartido entre los tres planos y dibujo en posición nominal |

La versión con las distancias del diseño queda disponible en el tag
`v1.3-detector-alignment`.

---

## 11. Limitaciones y trabajo futuro

- **Estadística.** El alineamiento se basa en 10 tracks de 3 planos. Conviene repetirlo
  con tomas más largas y comprobar que los parámetros se mantienen dentro de su
  incertidumbre.
- **Solo tres planos.** Solo se mide el desalineo relativo; la asignación a cada plano
  es una convención. Un cuarto plano, o una referencia externa, permitiría alinear cada
  plano por separado.
- **Grados de libertad no ajustados.** Pequeñas rotaciones en el plano y las
  inclinaciones de los planos necesitan más tracks.
- **Posición del impacto.** Se usa el píxel de máximo ToT; el centroide del cluster
  mejoraría la resolución (efecto de ~±1 px).
- **Tracks atípicos.** El evento 1355 (hit de H0 un BX antes) y el 7750 (11 px de
  residuo tras el alineamiento, sin explicación).
- **Coincidencias accidentales.** `BX_TOLERANCE` en HitAnalysis (desactivado por
  defecto) permitiría exigir |ΔBX| ≤ 1 entre planos, a la vista de la sección 5.1.
- **Eficiencia de H1.** Hay 13 tracks con H0+H2 sin hit en H1, aunque H1 queda entre
  ambos. Puede indicar una eficiencia reducida de H1; queda por estudiar.
- **Verificaciones en el diseño 3D:** la distancia del centro del LIN de H0 a su eje de
  giro (sección 8.3) y el origen de las distancias en Z (sección 8.4).
- Si se cambia la mecánica del telescopio, el alineamiento debe recalcularse.

---

## 12. Procedimiento para repetir el alineamiento

1. Tomar un run largo de cósmicos y convertirlo a ROOT.
2. Ejecutar NoiseAnalysis y HitAnalysis (*HIT ANALYSIS* en el Analysis tab). En la GUI,
   *Coincidence planes = 3* muestra los tracks útiles.
3. Para cada track de 3 planos, tomar la coordenada global (fila, columna) de cada plano
   (`plot_coord`) **sin alineamiento**: poner `LAYER_ALIGNMENT` a cero, o restarlo.
4. Ajustar conjuntamente la proporción f y el desplazamiento de H0, S_H0, alternando las
   fórmulas de la sección 6.3 hasta converger. Rechazar tracks con residuos > 3σ o con
   hits de H0 fuera del BX de los demás planos.
5. Estimar las incertidumbres con bootstrap y validar con leave-one-out frente a la
   geometría anterior.
6. Pasar f a distancias manteniendo la distancia total de referencia (23.6 mm), y
   repartir S_H0 entre los tres planos con la fórmula de mínima norma (sección 7.4).
7. Actualizar `Z_GAP_LAYER_0_1`, `Z_GAP_LAYER_1_2` y `LAYER_ALIGNMENT` en
   `src/chip/detector_geometry.py`, y comprobar en la GUI que los tracks pasan por sus
   impactos.
