#!/bin/bash
# =============================================================================
# run_docker_linux.sh — Arrancar contenedor Linux con entorno Ph2_ACF cargado
# =============================================================================

IMAGE="${1:-lab-framework:latest}"
PROJECT_DIR="$(pwd)"

# Dentro del contenedor, el directorio actual del host se monta como /app
PH2_DIR="/app"

# Permitir que el contenedor use el servidor X del host
xhost +local:docker 2>/dev/null || true
docker run -it --rm \
  --name lab-container \
  --user $(id -u):$(id -g) \
  -v "$PROJECT_DIR:/app" \
  -v /home/usuario/.rd53a_gui:/config \
  -e DISPLAY="$DISPLAY" \
  -e HOME=/config \
  -e MPLCONFIGDIR=/config/matplotlib \
  -e XDG_CACHE_HOME=/config/.cache \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --privileged \
  -v /dev/bus/usb:/dev/bus/usb \
  --network host \
  "$IMAGE" \
  /bin/bash -lc "
    cd $PH2_DIR
    source setup.sh
    cd /app
    exec /bin/bash -i
  "