FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

# Runtime deps for Playwright/Chromium + ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 \
    libcups2t64 libdrm2 libxss1 libxrandr2 libasound2t64 \
    libpangocairo-1.0-0 libcairo-gobject2 libgtk-3-0t64 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install project dependencies
COPY requirements.txt /tmp/project-requirements.txt
RUN pip install --no-cache-dir -r /tmp/project-requirements.txt

# Install web-ui dependencies
COPY web-ui/requirements.txt /tmp/webui-requirements.txt
RUN pip install --no-cache-dir -r /tmp/webui-requirements.txt

# Install Playwright Chromium
RUN playwright install-deps chromium && playwright install chromium

# Copy project source
COPY video_downloader.py utilities.py cli.py /app/
COPY config/ /app/config/

# Copy web-ui source
COPY web-ui/app.py /app/webui_app.py
COPY web-ui/templates/ /app/templates/

# Create dirs for data and downloads
RUN mkdir -p /app/downloads /app/data /app/logs

ENV PYTHONPATH=/app
ENV CONFIG_PATH=/app/config/config.json
ENV DB_PATH=/app/data/download_history.db

EXPOSE 8080

CMD ["uvicorn", "webui_app:app", "--host", "0.0.0.0", "--port", "8080"]
