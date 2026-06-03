# Lab Framework — Docker multiplataforma

## Estructura de archivos

```
├── Dockerfile          # Imagen única para Windows y Linux
├── requirements.txt    # Dependencias Python
├── run_linux.sh        # Arranque en el laboratorio (Linux)
└── run_windows.bat     # Arranque en Windows (Docker Desktop + VcXsrv)
```

---

## ⚠️ Prerrequisitos antes de construir

**IMPORTANTE:** Debes descargar Protobuf manualmente y colocarlo en la misma carpeta que el Dockerfile.

```bash
cd ReDocker
wget https://github.com/protocolbuffers/protobuf/releases/download/v21.12/protobuf-3.21.12.tar.gz
```

Sin `protobuf-3.21.12.tar.gz` en esta carpeta, la construcción de la imagen fallará.

---

## Construir la imagen

```bash
docker build -t lab-framework:latest .
```

La imagen es la **misma** en los dos sitios — solo cambia cómo se arranca.

---

## Uso en Linux (laboratorio)

```bash
chmod +x run_linux.sh
./run_linux.sh                        # usa el directorio actual como /app
./run_linux.sh lab-framework:latest /ruta/a/tu/proyecto
```

El script hace `xhost +local:docker` automáticamente para que el contenedor
pueda abrir ventanas en tu pantalla.

---

## Uso en Windows (Docker Desktop)

### Prerequisito: servidor X11

Instala **VcXsrv**: https://sourceforge.net/projects/vcxsrv/

Lánzalo con estas opciones:
1. **Multiple windows**
2. Display number: **0**
3. Start no client
4. ✅ **Disable access control** ← imprescindible

### Arrancar el contenedor

Haz doble clic en `run_windows.bat` o ejecuta desde PowerShell:

```powershell
.\run_windows.bat
```

---

## Variables de entorno importantes

| Variable | Valor | Propósito |
|---|---|---|
| `ROOTSYS` | `/usr` | FindROOT.cmake |
| `CACTUSROOT` | `/opt/cactus` | FindCACTUS.cmake |
| `CMAKE_PREFIX_PATH` | `$CACTUSROOT:$ROOTSYS` | CMake genérico |
| `PYTHONPATH` | `/usr/lib64/root` | PyROOT |
| `DISPLAY` | Pasado en runtime | GUI X11 |
| `QT_X11_NO_MITSHM` | `1` | Compatibilidad PyQt5 en Docker |

---

## Notas sobre hardware (USB / IPbus)

- **Linux (lab):** el script usa `--privileged` y monta `/dev/bus/usb`.
  Si no necesitas acceso a hardware desde el contenedor, elimina esas líneas.
- **Windows:** Docker Desktop **no expone USB** al contenedor.
  Para trabajar con hardware real usa siempre el lab directamente.

---

## Usuario dentro del contenedor

La imagen crea un usuario `labuser` (sin contraseña, con sudo).
Si tu `setup.sh` necesita **root** para acceder a hardware, comenta el bloque
`useradd` en el Dockerfile y el contenedor arrancará como root.
