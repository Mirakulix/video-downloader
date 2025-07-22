#!/bin/bash
set -e

# ==============================================================================
# Docker Entrypoint Script für Web Video Downloader
# Initialisiert Container-Environment und führt Gesundheitschecks durch
# ==============================================================================

# Farben für bessere Lesbarkeit
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging-Funktion
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# ==============================================================================
# ENVIRONMENT SETUP
# ==============================================================================

setup_environment() {
    log "🚀 Initialisiere Web Video Downloader Container..."
    
    # Default-Umgebungsvariablen setzen
    export CONFIG_PATH="${CONFIG_PATH:-/app/config/config.json}"
    export OUTPUT_DIR="${OUTPUT_DIR:-/app/downloads}"
    export LOG_LEVEL="${LOG_LEVEL:-INFO}"
    export PYTHONPATH="/app:${PYTHONPATH}"
    
    # Verzeichnisse erstellen falls nicht vorhanden
    mkdir -p "$(dirname "$CONFIG_PATH")" "$OUTPUT_DIR" /app/logs
    
    # Permissions überprüfen
    if [ ! -w "$OUTPUT_DIR" ]; then
        error "Download-Verzeichnis nicht beschreibbar: $OUTPUT_DIR"
        exit 1
    fi
    
    log "✅ Environment-Setup abgeschlossen"
}

# ==============================================================================
# CONFIGURATION MANAGEMENT
# ==============================================================================

setup_configuration() {
    log "⚙️ Konfiguration wird vorbereitet..."
    
    # Standard-Konfiguration erstellen falls nicht vorhanden
    if [ ! -f "$CONFIG_PATH" ]; then
        warning "Keine Konfigurationsdatei gefunden, erstelle Standard-Config..."
        
        cat > "$CONFIG_PATH" << 'EOF'
{
  "sites": {},
  "output_directory": "/app/downloads",
  "nordvpn_enabled": false,
  "ip_rotation_interval_min": 300,
  "ip_rotation_interval_max": 1800,
  "headless": true,
  "timeout": 30,
  "concurrent_downloads": 2,
  "retry_attempts": 3,
  "log_level": "INFO",
  "user_agents": [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  ]
}
EOF
        log "✅ Standard-Konfiguration erstellt: $CONFIG_PATH"
    fi
    
    # Konfiguration validieren
    if ! python -c "import json; json.load(open('$CONFIG_PATH'))" 2>/dev/null; then
        error "Ungültige JSON-Konfiguration: $CONFIG_PATH"
        exit 1
    fi
    
    log "✅ Konfiguration validiert"
}

# ==============================================================================
# DEPENDENCY CHECKS
# ==============================================================================

check_dependencies() {
    log "🔍 Überprüfe Dependencies..."
    
    # Python-Module prüfen
    local required_modules=("playwright" "yt_dlp" "aiohttp" "pydantic" "beautifulsoup4")
    
    for module in "${required_modules[@]}"; do
        if ! python -c "import $module" 2>/dev/null; then
            error "Python-Modul nicht gefunden: $module"
            return 1
        fi
    done
    
    # FFmpeg prüfen
    if ! command -v ffmpeg >/dev/null 2>&1; then
        warning "FFmpeg nicht gefunden - Video-Processing könnte eingeschränkt sein"
    fi
    
    # Playwright Browser prüfen
    if [ ! -d "/home/appuser/.cache/ms-playwright" ]; then
        warning "Playwright Browser-Cache nicht gefunden - installiere Chromium..."
        playwright install chromium
    fi
    
    log "✅ Dependency-Check abgeschlossen"
}

# ==============================================================================
# NORDVPN SETUP
# ==============================================================================

setup_nordvpn() {
    local nordvpn_enabled
    nordvpn_enabled=$(python -c "import json; print(json.load(open('$CONFIG_PATH')).get('nordvpn_enabled', False))" 2>/dev/null || echo "false")
    
    if [ "$nordvpn_enabled" = "True" ]; then
        log "🔒 NordVPN-Setup wird initialisiert..."
        
        # NordVPN-Credentials aus Environment-Variablen prüfen
        if [ -n "$NORDVPN_USERNAME" ] && [ -n "$NORDVPN_PASSWORD" ]; then
            info "NordVPN-Credentials aus Environment gefunden"
            
            # Automatisches Login versuchen (falls nicht bereits eingeloggt)
            if ! nordvpn account 2>/dev/null | grep -q "logged in"; then
                warning "Versuche NordVPN-Login..."
                echo "$NORDVPN_PASSWORD" | nordvpn login --username "$NORDVPN_USERNAME" || {
                    warning "NordVPN-Login fehlgeschlagen - VPN wird deaktiviert"
                    return 0
                }
            fi
            
            log "✅ NordVPN erfolgreich konfiguriert"
        else
            warning "NordVPN aktiviert aber keine Credentials gefunden (NORDVPN_USERNAME/NORDVPN_PASSWORD)"
            warning "VPN-Features werden möglicherweise nicht funktionieren"
        fi
    else
        info "NordVPN deaktiviert in Konfiguration"
    fi
}

# ==============================================================================
# HEALTH CHECKS
# ==============================================================================

health_check() {
    log "🏥 Führe Gesundheitschecks durch..."
    
    # Python-Import-Test
    if ! python -c "from video_downloader import WebVideoDownloader; print('✅ Import erfolgreich')" 2>/dev/null; then
        error "Hauptmodul kann nicht importiert werden"
        return 1
    fi
    
    # Konfiguration laden
    if ! python -c "
from video_downloader import WebVideoDownloader
try:
    downloader = WebVideoDownloader('$CONFIG_PATH')
    print('✅ Konfiguration erfolgreich geladen')
except Exception as e:
    print(f'❌ Konfigurationsfehler: {e}')
    exit(1)
" 2>/dev/null; then
        error "Konfiguration kann nicht geladen werden"
        return 1
    fi
    
    # Playwright Test
    if ! python -c "
import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        await browser.close()
        print('✅ Playwright funktional')

asyncio.run(test_playwright())
" 2>/dev/null; then
        warning "Playwright-Test fehlgeschlagen - Browser-Features könnten eingeschränkt sein"
    fi
    
    log "✅ Gesundheitschecks abgeschlossen"
}

# ==============================================================================
# SIGNAL HANDLERS
# ==============================================================================

cleanup() {
    log "🧹 Container-Cleanup wird durchgeführt..."
    
    # NordVPN trennen falls verbunden
    if command -v nordvpn >/dev/null 2>&1; then
        nordvpn disconnect >/dev/null 2>&1 || true
    fi
    
    # Temporäre Dateien bereinigen
    find /tmp -name "*.tmp" -type f -delete 2>/dev/null || true
    
    log "✅ Cleanup abgeschlossen"
    exit 0
}

# Signal-Handler registrieren
trap cleanup SIGTERM SIGINT

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    log "🎬 Web Video Downloader Container startet..."
    
    # Setup-Schritte ausführen
    setup_environment
    setup_configuration
    check_dependencies
    setup_nordvpn
    health_check
    
    log "🚀 Container erfolgreich initialisiert!"
    
    # Wenn keine Argumente übergeben wurden, zeige Hilfe
    if [ $# -eq 0 ]; then
        info "Keine Argumente übergeben - zeige Hilfe:"
        python video_downloader.py --help
        exit 0
    fi
    
    # Spezielle Container-Kommandos verarbeiten
    case "$1" in
        "health")
            log "🏥 Gesundheitscheck angefordert"
            health_check
            exit 0
            ;;
        "demo")
            log "🎮 Demo-Modus wird gestartet"
            shift
            exec python example_usage.py "$@"
            ;;
        "shell")
            log "🐚 Shell-Modus aktiviert"
            exec /bin/bash
            ;;
        "monitor")
            log "📊 Monitoring-Modus gestartet"
            python -c "
from utilities import PerformanceMonitor
import time

monitor = PerformanceMonitor()
print('Performance-Monitoring gestartet (Strg+C zum Beenden)...')

try:
    while True:
        metrics = monitor.capture_metrics()
        print(f'CPU: {metrics.cpu_percent:.1f}% | RAM: {metrics.memory_mb:.1f}MB | Zeit: {metrics.timestamp}')
        time.sleep(10)
except KeyboardInterrupt:
    print('Monitoring beendet')
"
            ;;
        "stats")
            log "📈 Download-Statistiken anzeigen"
            python -c "
from utilities import DownloadHistory, RichDisplay
history = DownloadHistory()
display = RichDisplay()
stats = history.get_download_stats(days=30)
if stats:
    display.display_download_stats(stats)
else:
    print('Keine Download-Historie gefunden')
"
            ;;
        *)
            # Standard-Ausführung des Video-Downloaders
            log "🎥 Video-Download wird gestartet mit Argumenten: $*"
            exec python video_downloader.py --config "$CONFIG_PATH" "$@"
            ;;
    esac
}

# Script ausführen
main "$@"
