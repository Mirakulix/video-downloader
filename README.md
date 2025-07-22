# 🎥 Web Video Downloader

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Ein fortschrittlicher Python Web Video Downloader mit NordVPN-Integration, Browser-Automatisierung und intelligenter Video-Extraktion. Entwickelt für den sicheren Download von Videos mit konfigurierbaren Site-spezifischen Selektoren.

## 🚀 Features

### 🔥 Kernfunktionalitäten
- **🎯 Multi-Site Support** - Konfigurierbare Selektoren für verschiedene Video-Plattformen
- **🔒 NordVPN Integration** - Automatische IP-Rotation in zufälligen Intervallen
- **🤖 Browser-Automatisierung** - Playwright-basierte Interaktion mit JavaScript-Heavy Sites
- **⚡ yt-dlp Integration** - Beste Video-Qualität durch bewährte Extraction-Engine
- **🧠 Intelligente Erkennung** - Automatische Video-URL-Erkennung und -Analyse

### 🛠 Erweiterte Features
- **👤 Human Behavior Simulation** - Realistische Delays und Scroll-Patterns
- **🔐 Login-Automatisierung** - CSRF-Token-aware Authentifizierung
- **📊 Performance-Monitoring** - Real-time System-Metriken und Analytics
- **📈 Download-Historie** - SQLite-basierte Tracking und Statistiken
- **🔄 Error Recovery** - Intelligente Fehlerbehandlung mit automatischen Retry-Strategien
- **⚡ Async Architecture** - Parallele Downloads mit Concurrency-Kontrolle

## 📋 Anforderungen

### System-Anforderungen
- **Python 3.9+** (empfohlen: Python 3.11+)
- **NordVPN CLI** (optional, für VPN-Features)
- **FFmpeg** (für Video-Processing)
- **Chromium Browser** (wird automatisch von Playwright installiert)

### Unterstützte Betriebssysteme
- ✅ Linux (Ubuntu 20.04+, Debian 11+)
- ✅ macOS (10.15+)
- ✅ Windows 10/11 (mit WSL2 empfohlen)

## 🔧 Installation

### 🚀 Quick Start (Automatisch)

```bash
# Repository klonen
git clone https://github.com/your-username/web-video-downloader.git
cd web-video-downloader

# Automatisches Setup ausführen
python setup.py
```

### 📋 Manuelle Installation

1. **Python-Dependencies installieren:**
```bash
# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/macOS
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Playwright Browser installieren
playwright install chromium
```

2. **System-Dependencies:**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

3. **NordVPN CLI (optional):**

**Linux:**
```bash
curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh | sh
sudo usermod -aG nordvpn $USER
nordvpn login
```

**macOS:**
```bash
brew install --cask nordvpn
```

### 🐳 Docker Installation

```bash
# Container bauen
docker build -t web-video-downloader .

# Container ausführen
docker run -v $(pwd)/downloads:/app/downloads \
           -v $(pwd)/config.json:/app/config.json \
           web-video-downloader https://example.com/video
```

## ⚙️ Konfiguration

### 📝 Basis-Konfiguration

Erstelle eine `config.json`:

```json
{
  "sites": {
    "example-video-site.com": {
      "video_button": [".play-btn", "button[data-play]"],
      "download_link": ["a[href*='.mp4']", ".download-link"],
      "login_username": "your-username@example.com",
      "login_password": "your-password",
      "human_delay_min": 1.5,
      "human_delay_max": 3.0
    }
  },
  "output_directory": "./downloads",
  "nordvpn_enabled": true,
  "ip_rotation_interval_min": 300,
  "ip_rotation_interval_max": 1800,
  "headless": false,
  "concurrent_downloads": 3,
  "log_level": "INFO"
}
```

### 🔧 Site-spezifische Konfiguration

Für jede Website können Sie individuelle Selektoren definieren:

```json
{
  "sites": {
    "your-video-platform.com": {
      "video_button": [
        "button.play-video",
        ".video-play-btn",
        "a[data-action='play']"
      ],
      "download_link": [
        "a[href*='.mp4']",
        "a.download-btn",
        "button[data-download-url]"
      ],
      "login_url": "https://your-video-platform.com/login",
      "login_username_field": "input[name='email']",
      "login_password_field": "input[name='password']",
      "login_submit_button": "button[type='submit']",
      "wait_after_login": 5,
      "custom_headers": {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9"
      }
    }
  }
}
```

## 🚀 Verwendung

### 💻 Kommandozeile

```bash
# Aktiviere Virtual Environment
source venv/bin/activate

# Einzelne URL
python video_downloader.py https://example.com/video

# Mehrere URLs
python video_downloader.py \
  https://site1.com/video1 \
  https://site2.com/video2 \
  https://site3.com/video3

# Mit spezifischer Konfiguration
python video_downloader.py --config my_config.json https://example.com/video

# Headless-Modus (ohne GUI)
python video_downloader.py --headless https://example.com/video

# VPN deaktivieren
python video_downloader.py --no-vpn https://example.com/video

# Output-Verzeichnis überschreiben
python video_downloader.py --output /path/to/downloads https://example.com/video
```

### 🐍 Python API

```python
import asyncio
from video_downloader import WebVideoDownloader

async def main():
    # Downloader initialisieren
    async with WebVideoDownloader('config.json') as downloader:
        # URLs definieren
        urls = [
            'https://your-platform.com/video1',
            'https://your-site.com/video2'
        ]
        
        # Downloads starten
        results = await downloader.download_multiple_urls(urls)
        
        # Ergebnisse verarbeiten
        for result in results:
            if result.success:
                print(f"✅ {result.url} -> {result.filepath}")
            else:
                print(f"❌ {result.url}: {result.error}")

# Ausführen
asyncio.run(main())
```

### 🎮 Interaktiver Demo-Modus

```bash
# Vollständige Demo mit allen Features
python example_usage.py --interactive

# Demo mit spezifischen URLs
python example_usage.py --urls https://site1.com/video https://site2.com/video
```

## 📊 Monitoring & Analytics

### 📈 Performance-Monitoring

```python
from utilities import PerformanceMonitor

monitor = PerformanceMonitor()

# Metriken erfassen
metrics = monitor.capture_metrics(active_downloads=2)
print(f"CPU: {metrics.cpu_percent}%")
print(f"RAM: {metrics.memory_mb:.1f} MB")

# Durchschnittswerte
avg_metrics = monitor.get_average_metrics(minutes=10)
print(f"Durchschnittliche CPU: {avg_metrics['avg_cpu_percent']:.1f}%")
```

### 🗄️ Download-Historie

```python
from utilities import DownloadHistory

history = DownloadHistory()

# Statistiken anzeigen
stats = history.get_download_stats(days=30)
print(f"Erfolgsrate: {stats['success_rate']:.1f}%")
print(f"Gesamt-Downloads: {stats['total_downloads']}")
```

### 📋 URL-Analyse

```python
from utilities import VideoAnalyzer

analyzer = VideoAnalyzer()

# URLs analysieren
urls = ['https://example.com/video1', 'https://example.com/video2']
analyses = analyzer.batch_analyze(urls)

# Bericht generieren
report = analyzer.generate_analysis_report(analyses)
print(f"Erfolgswahrscheinlichkeit: {report['success_probability']:.1%}")
```

## 🔒 Sicherheit & Best Practices

### 🛡️ Sicherheitsrichtlinien

- **Nur eigene Services**: Verwenden Sie diesen Downloader ausschließlich für eigene Websites und autorisierte Plattformen
- **Rate-Limiting**: Implementierte Verzögerungen respektieren Server-Ressourcen
- **VPN-Rotation**: Schützt Ihre IP-Adresse durch automatische Rotation
- **Secure Storage**: Sensible Daten in `.env`-Dateien speichern

### 🔐 Credential-Management

Erstellen Sie eine `.env`-Datei für sensible Daten:

```bash
# .env
NORDVPN_USERNAME=your_nordvpn_username
NORDVPN_PASSWORD=your_nordvpn_password

# Site-spezifische Credentials
SITE1_USERNAME=your_username
SITE1_PASSWORD=your_password
```

## 🧪 Testing

### 🔬 Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage
pytest --cov=. --cov-report=html

# Spezifische Tests
pytest tests/test_video_downloader.py
pytest tests/test_vpn_manager.py
```

### 🐛 Debugging

```bash
# Debug-Modus aktivieren
export DEBUG=1
python video_downloader.py --log-level=DEBUG https://example.com/video

# Browser sichtbar machen für Debugging
python video_downloader.py --no-headless https://example.com/video
```

## 🐳 Docker Deployment

### 📦 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  video-downloader:
    build: .
    volumes:
      - ./downloads:/app/downloads
      - ./config.json:/app/config.json
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=INFO
    restart: unless-stopped
```

```bash
# Deployment
docker-compose up -d

# Logs verfolgen
docker-compose logs -f
```

## 📝 Logs & Troubleshooting

### 📋 Log-Dateien

- `video_downloader.log` - Haupt-Logdatei
- `performance_metrics.json` - Performance-Daten
- `download_history.db` - SQLite-Datenbank mit Download-Historie

### 🔍 Häufige Probleme

**Problem: NordVPN-Verbindung schlägt fehl**
```bash
# NordVPN-Status prüfen
nordvpn status

# Neu anmelden
nordvpn logout
nordvpn login
```

**Problem: Browser startet nicht**
```bash
# Playwright Browser neu installieren
playwright install chromium --force
```

**Problem: Downloads schlagen fehl**
```bash
# Debug-Modus aktivieren
python video_downloader.py --log-level=DEBUG --no-headless <URL>
```

## 🤝 Contributing

### 📋 Development Setup

```bash
# Development-Dependencies installieren
pip install -r requirements-dev.txt

# Pre-commit Hooks einrichten
pre-commit install

# Code formatieren
black .
flake8 .
mypy .
```

### 🔄 Pull Request Process

1. Fork das Repository
2. Erstelle einen Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committe deine Änderungen (`git commit -m 'Add AmazingFeature'`)
4. Push zum Branch (`git push origin feature/AmazingFeature`)
5. Öffne einen Pull Request

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

## ⚠️ Disclaimer

Dieser Video-Downloader ist ausschließlich für den Gebrauch mit **eigenen Websites und autorisierten Video-Plattformen** bestimmt. 

**Wichtige Hinweise:**
- Respektieren Sie Urheberrechte und Nutzungsbedingungen
- Verwenden Sie den Downloader nur für eigene Services
- Befolgen Sie die Robots.txt und Terms of Service der jeweiligen Websites
- Der Entwickler übernimmt keine Verantwortung für missbräuchliche Nutzung

## 🙏 Danksagungen

- [Playwright](https://playwright.dev/) - Browser-Automatisierung
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video-Extraktion
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Datenvalidierung
- [Rich](https://rich.readthedocs.io/) - Terminal-Ausgabe
- [NordVPN](https://nordvpn.com/) - VPN-Services

---

**🎯 Entwickelt für professionellen Einsatz mit eigenen Video-Plattformen und Services.**
