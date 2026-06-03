@echo off
REM =============================================================================
REM  run_windows.bat  —  Arrancar el contenedor en Windows (Docker Desktop)
REM
REM  PREREQUISITO: VcXsrv corriendo con estas opciones:
REM    - Multiple windows  (o Fullscreen)
REM    - Display number: 0
REM    - Start no client
REM    - [x] Disable access control   <-- IMPORTANTE para que Docker conecte
REM
REM  Descarga VcXsrv: https://sourceforge.net/projects/vcxsrv/
REM =============================================================================

SET IMAGE=lab-framework:latest
SET PROJECT_DIR=%CD%

REM Obtener la IP del host Windows vista desde WSL2/Docker
REM  "host.docker.internal" funciona automáticamente en Docker Desktop
SET DISPLAY_ADDR=host.docker.internal:0.0

docker run -it --rm ^
    --name lab-container ^
    -v "%PROJECT_DIR%:/app" ^
    -e DISPLAY=%DISPLAY_ADDR% ^
    -e LIBGL_ALWAYS_INDIRECT=1 ^
    -e QT_X11_NO_MITSHM=1 ^
    "%IMAGE%"

REM NOTA: --privileged y /dev/bus/usb NO se usan en Windows porque
REM Docker Desktop no expone USB directamente. Para hardware real usa el lab.
