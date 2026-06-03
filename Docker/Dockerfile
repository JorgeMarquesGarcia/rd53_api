# =============================================================================
#  Imagen base: AlmaLinux 9 — x86_64
#  Compatible: Windows (Docker Desktop + VcXsrv/X410) y Linux del laboratorio
#  GUI: X11 forwarding para PyQt5 y ROOT
# =============================================================================
FROM almalinux:9

# --- LOCALE ---
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# --- VARIABLES CRÍTICAS PARA CMAKE ---
# FindROOT.cmake busca en $ROOTSYS/bin (DNF instala ROOT en /usr)
ENV ROOTSYS=/usr
# FindCACTUS.cmake usa $CACTUSROOT (ipbus instala en /opt/cactus)
ENV CACTUSROOT=/opt/cactus
ENV CMAKE_PREFIX_PATH=$CACTUSROOT:$ROOTSYS

# --- PYROOT ---
ENV PYTHONPATH=/usr/lib64/root

# --- X11 / GUI ---
# DISPLAY se pasa en tiempo de ejecución mediante docker run -e DISPLAY=...
# No se fija aquí para que sea válido tanto en Linux como en Windows
ENV QT_X11_NO_MITSHM=1
ENV LIBGL_ALWAYS_INDIRECT=1

# =============================================================================
# 1. SISTEMA BASE: EPEL + CRB
# =============================================================================
RUN dnf update -y && \
    dnf install -y curl epel-release --allowerasing && \
    dnf config-manager --set-enabled crb && \
    dnf clean all

# =============================================================================
# 2. REPOSITORIOS EXTERNOS
# =============================================================================

# A. uHAL / IPbus (CERN)
RUN curl -L https://ipbus.web.cern.ch/doc/user/html/_downloads/ipbus-sw.repo \
        -o /etc/yum.repos.d/ipbus-sw.repo

# B. Modern Erlang (RabbitMQ)
RUN cat << 'EOF' > /etc/yum.repos.d/modern_erlang.repo
[modern-erlang]
name=modern-erlang-el9
baseurl=https://yum1.novemberain.com/erlang/el/9/$basearch
repo_gpgcheck=0
enabled=1
gpgkey=https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md

[modern-erlang-noarch]
name=modern-erlang-el9-noarch
baseurl=https://yum1.novemberain.com/erlang/el/9/noarch
repo_gpgcheck=0
enabled=1
gpgkey=https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key
       https://github.com/rabbitmq/signing-keys/releases/download/2.0/rabbitmq-release-signing-key.asc
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md
EOF

RUN rpm --import https://dl.cloudsmith.io/public/rabbitmq/rabbitmq-erlang/gpg.E495BB49CC4BBE5B.key || true && \
    rpm --import https://github.com/rabbitmq/signing-keys/releases/download/3.0/rabbitmq-release-signing-key.asc || true

# =============================================================================
# 3. INSTALACIÓN DE PAQUETES
#    Dividida en capas lógicas para aprovechar la caché de Docker:
#    si cambias Python no reconstruyes ROOT, y viceversa.
# =============================================================================

# --- 3a. Erlang ---
RUN dnf makecache && \
    dnf install -y --nogpgcheck erlang && \
    dnf clean all

# --- 3b. ROOT + PyROOT ---
RUN dnf install -y \
        root \
        root-net-http \
        root-net-httpsniff \
        root-graf3d-gl \
        root-physics \
        root-montecarlo-eg \
        root-graf3d-eve \
        root-geom \
        python3-root && \
    dnf clean all

# --- 3c. Herramientas de desarrollo y compilación ---
RUN dnf install -y \
        gcc \
        gcc-c++ \
        gcc-toolset-12 \
        scl-utils \
        make \
        cmake \
        git \
        git-extras \
        git-lfs \
        wget \
        tar \
        which \
        dos2unix && \
    dnf clean all

# --- 3d. Bibliotecas de desarrollo (C++) ---
RUN dnf install -y \
        libusb-devel \
        boost-devel \
        pugixml-devel \
        json-devel \
        bzip2-devel \
        xz-devel \
        zlib-devel \
        libzstd-devel \
        zeromq-devel \
        cppzmq-devel \
        libcurl-devel \
        openssl-devel && \
    dnf clean all


# --- 3d+1. Protobuf moderno (necesario para Ph2_ACF) ---

# --- 3d+1. Protobuf moderno ---
WORKDIR /opt

COPY protobuf-3.21.12.tar.gz /opt/

RUN tar -xzf protobuf-3.21.12.tar.gz \
    && cd protobuf-3.21.12 \
    && mkdir build && cd build \
    && cmake -Dprotobuf_BUILD_TESTS=OFF .. \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && cd /opt \
    && rm -rf protobuf-3.21.12 protobuf-3.21.12.tar.gz

 
# --- 3e. Python + dependencias para pycurl, pycairo, pygobject ---
RUN dnf install -y \
        python3 \
        python3-devel \
        python3.9-pip \
        cairo-devel \
        pkgconf \
        gobject-introspection-devel \
        cairo-gobject-devel \
        glib2-devel && \
    dnf clean all

# --- 3f. Soporte X11 / GUI (PyQt5 + ROOT TBrowser) ---
RUN dnf install -y \
        xorg-x11-xauth \
        xorg-x11-server-utils \
        mesa-libGL \
        mesa-libGL-devel \
        mesa-dri-drivers \
        libxkbcommon-x11 \
        xcb-util \
        xcb-util-image \
        xcb-util-keysyms \
        xcb-util-renderutil \
        xcb-util-wm \
        libX11 \
        libXext \
        libXrender \
        libXi \
        fontconfig \
        freetype && \
    dnf clean all

# --- 3g. uHAL / controlhub ---
RUN dnf groupinstall -y uhal controlhub && \
    dnf clean all

# =============================================================================
# 4. DEPENDENCIAS PYTHON (pip)
# =============================================================================
WORKDIR /app
COPY requirements.txt .
RUN pip3.9 install --no-cache-dir -r requirements.txt

# =============================================================================
# 5. PYBIND11 (en /opt para que CMake lo encuentre)
# =============================================================================
WORKDIR /opt
RUN wget -q https://github.com/pybind/pybind11/archive/refs/tags/v2.9.2.tar.gz \
    && tar zxf v2.9.2.tar.gz \
    && rm v2.9.2.tar.gz

### Para que no coja pybind de github, sino el que acabamos de descargar (si tu CMake lo encuentra en /opt)    
RUN ln -sfn /opt/pybind11-2.9.2 /pybind11-2.9.2

# =============================================================================
# 6. USUARIO NO-ROOT (buena práctica; omite si tu setup.sh necesita root)
# =============================================================================
# Si el lab requiere root para acceder a hardware USB/IPbus, comenta este bloque.
RUN useradd -ms /bin/bash labuser && \
    echo "labuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER labuser

# =============================================================================
# 7. ARRANQUE
# =============================================================================
WORKDIR /app
CMD ["/bin/bash"]
