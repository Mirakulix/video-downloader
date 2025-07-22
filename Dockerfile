# Multi-stage Dockerfile für Web Video Downloader
# Optimiert für Produktions-Deployment mit minimaler Image-Größe

# ==============================================================================
# STAGE 1: Builder Stage - Dependencies und Setup
# ==============================================================================
FROM python:3.11-slim as builder

# Metadata
LABEL maintainer="your-email@example.com"
LABEL description="Web Video Downloader with NordVPN Integration"
LABEL version="1.0.0"

# Build-Argumente
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHONDONTWRITEBYTECODE=1
ARG PYTHONUNBUFFERED=1

# System-Updates und Build-Dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg2 \
    software-properties-common \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python-Environment vorbereiten
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Python-Dependencies installieren
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Playwright Browser installieren (nur Chromium für minimale Größe)
RUN playwright install-deps chromium && \
    playwright install chromium

# ==============================================================================
# STAGE 2: Runtime Stage - Produktions-Container
# ==============================================================================
FROM python:3.11-slim as runtime

# Metadata kopieren
LABEL maintainer="your-email@example.com"
LABEL description="Web Video Downloader with NordVPN Integration"

# Runtime-Argumente
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHONDONTWRITEBYTECODE=1
ARG PYTHONUNBUFFERED=1
ARG USER_ID=1000
ARG GROUP_ID=1000

# Environment-Variablen
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DISPLAY=:99 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# System-Dependencies für Runtime
RUN apt-get update && apt-get install -y \
    # FFmpeg für Video-Processing
    ffmpeg \
    # NordVPN CLI Dependencies
    curl \
    wget \
    gnupg2 \
    lsb-release \
    # Browser Runtime Dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxss1 \
    libgconf-2-4 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    # Utility tools
    procps \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# NordVPN CLI installieren
RUN curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh | sh

# Non-root User erstellen für Sicherheit
RUN groupadd -g ${GROUP_ID} appuser && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -m -s /bin/bash appuser && \
    usermod -aG nordvpn appuser

# Virtual Environment aus Builder-Stage kopieren
COPY --from=builder /opt/venv /opt/venv

# Playwright Browser Data kopieren
COPY --from=builder /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright
RUN chown -R appuser:appuser /home/appuser/.cache

# Working Directory
WORKDIR /app

# Application Code kopieren
COPY --chown=appuser:appuser . /app/

# Permissions setzen
RUN chmod +x /app/video_downloader.py && \
    chmod +x /app/example_usage.py && \
    mkdir -p /app/downloads /app/logs && \
    chown -R appuser:appuser /app

# Zu Non-root User wechseln
USER appuser

# Volumes für persistente Daten
VOLUME ["/app/downloads", "/app/logs", "/app/config"]

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import video_downloader; print('OK')" || exit 1

# Default-Konfiguration für Container
ENV CONFIG_PATH=/app/config/config.json \
    OUTPUT_DIR=/app/downloads \
    LOG_LEVEL=INFO

# Startup Script
COPY --chown=appuser:appuser docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Port für potentielle Web-UI (zukünftige Erweiterung)
EXPOSE 8080

# Entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default Command
CMD ["python", "video_downloader.py", "--help"]
