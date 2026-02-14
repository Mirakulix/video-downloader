#!/usr/bin/env python3
"""
Setup Script für Web Video Downloader
Automatisiert Installation und Konfiguration
"""

import asyncio
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import click


def run_command(command: str, shell: bool = True) -> tuple[bool, str]:
    """Führt Shell-Kommando aus und gibt Erfolg + Output zurück"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timeout nach 5 Minuten"
    except Exception as e:
        return False, str(e)


def check_python_version() -> bool:
    """Überprüft Python-Version (min. 3.9)"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        click.echo(f"✅ Python {version.major}.{version.minor}.{version.micro} erkannt")
        return True
    else:
        click.echo(f"❌ Python 3.9+ erforderlich, gefunden: {version.major}.{version.minor}")
        return False


def install_nordvpn() -> bool:
    """Installiert NordVPN CLI falls nicht vorhanden"""
    system = platform.system().lower()

    # Prüfe ob NordVPN bereits installiert ist
    success, _ = run_command("nordvpn --version")
    if success:
        click.echo("✅ NordVPN CLI bereits installiert")
        return True

    click.echo("📦 Installiere NordVPN CLI...")

    if system == "linux":
        # Ubuntu/Debian Installation
        commands = [
            "curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh | sh",
            "sh <(curl -sSf [https://downloads.nordcdn.com/apps/linux/install.sh](https://downloads.nordcdn.com/apps/linux/install.sh))",
            "sudo usermod -aG nordvpn $USER"
        ]
    elif system == "darwin":  # macOS
        commands = [
            "brew install --cask nordvpn"
        ]
    else:
        click.echo("⚠️ Automatische NordVPN-Installation nur für Linux/macOS")
        click.echo("Bitte installieren Sie NordVPN manuell: https://nordvpn.com/download/")
        return False

    for cmd in commands:
        success, output = run_command(cmd)
        if not success:
            click.echo(f"❌ Fehler bei: {cmd}")
            click.echo(f"Output: {output}")
            return False

    click.echo("✅ NordVPN CLI installiert")
    click.echo("⚠️ Bitte melden Sie sich mit 'nordvpn login' an")
    return True


def install_ffmpeg() -> bool:
    """Installiert FFmpeg falls nicht vorhanden"""
    success, _ = run_command("ffmpeg -version")
    if success:
        click.echo("✅ FFmpeg bereits installiert")
        return True

    click.echo("📦 Installiere FFmpeg...")
    system = platform.system().lower()

    if system == "linux":
        success, output = run_command("sudo apt update && sudo apt install -y ffmpeg")
    elif system == "darwin":
        success, output = run_command("brew install ffmpeg")
    elif system == "windows":
        click.echo("⚠️ Bitte installieren Sie FFmpeg manuell für Windows")
        click.echo("Download: https://ffmpeg.org/download.html")
        return False
    else:
        return False

    if success:
        click.echo("✅ FFmpeg installiert")
    else:
        click.echo(f"❌ FFmpeg-Installation fehlgeschlagen: {output}")

    return success


def install_python_dependencies() -> bool:
    """Installiert Python-Dependencies aus requirements.txt"""
    click.echo("📦 Installiere Python-Dependencies...")

    # Virtual Environment erstellen falls nicht vorhanden
    venv_path = Path("venv")
    if not venv_path.exists():
        click.echo("🔧 Erstelle Virtual Environment...")
        success, output = run_command(f"{sys.executable} -m venv venv")
        if not success:
            click.echo(f"❌ Virtual Environment fehlgeschlagen: {output}")
            return False

    # Pip upgrade
    if platform.system().lower() == "windows":
        pip_cmd = "venv\\Scripts\\pip.exe"
    else:
        pip_cmd = "venv/bin/pip"

    success, output = run_command(f"{pip_cmd} install --upgrade pip")
    if not success:
        click.echo(f"❌ Pip upgrade fehlgeschlagen: {output}")
        return False

    # Requirements installieren
    success, output = run_command(f"{pip_cmd} install -r requirements.txt")
    if not success:
        click.echo(f"❌ Requirements-Installation fehlgeschlagen: {output}")
        return False

    # Playwright Browser installieren
    if platform.system().lower() == "windows":
        playwright_cmd = "venv\\Scripts\\playwright.exe"
    else:
        playwright_cmd = "venv/bin/playwright"

    success, output = run_command(f"{playwright_cmd} install chromium")
    if not success:
        click.echo(f"❌ Playwright Browser-Installation fehlgeschlagen: {output}")
        return False

    click.echo("✅ Python-Dependencies installiert")
    return True


def create_config_files():
    """Erstellt Standard-Konfigurationsdateien"""
    click.echo("📝 Erstelle Konfigurationsdateien...")

    # config.json erstellen falls nicht vorhanden
    config_path = Path("config.json")
    if not config_path.exists():
        default_config = {
            "sites": {},
            "output_directory": "./downloads",
            "nordvpn_enabled": True,
            "ip_rotation_interval_min": 300,
            "ip_rotation_interval_max": 1800,
            "headless": False,
            "timeout": 30,
            "concurrent_downloads": 3,
            "retry_attempts": 3,
            "log_level": "INFO"
        }

        import json
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

        click.echo("✅ config.json erstellt")

    # Downloads-Verzeichnis erstellen
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    click.echo("✅ Downloads-Verzeichnis erstellt")

    # .env Datei für sensible Daten
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, 'w') as f:
            f.write("# Sensible Konfigurationsdaten\n")
            f.write("# NORDVPN_USERNAME=your_username\n")
            f.write("# NORDVPN_PASSWORD=your_password\n")
        click.echo("✅ .env Template erstellt")


def run_tests() -> bool:
    """Führt grundlegende Tests aus"""
    click.echo("🧪 Führe Tests aus...")

    # Import-Test
    try:
        if platform.system().lower() == "windows":
            python_cmd = "venv\\Scripts\\python.exe"
        else:
            python_cmd = "venv/bin/python"

        test_script = """
import asyncio
from video_downloader import WebVideoDownloader

async def test_import():
    print("✅ Imports erfolgreich")

    # Test VPN-Manager
    from video_downloader import VPNManager
    vpn = VPNManager(enabled=False)
    print("✅ VPN-Manager initialisiert")

    # Test Config
    config_path = "config.json"
    downloader = WebVideoDownloader(config_path)
    print("✅ Downloader initialisiert")

    print("🎉 Alle Tests bestanden!")

if __name__ == "__main__":
    asyncio.run(test_import())
"""

        # Test-Script ausführen
        success, output = run_command(f'{python_cmd} -c "{test_script}"')
        if success:
            click.echo("✅ Alle Tests bestanden")
            return True
        else:
            click.echo(f"❌ Tests fehlgeschlagen: {output}")
            return False

    except Exception as e:
        click.echo(f"❌ Test-Fehler: {e}")
        return False


def print_usage_info():
    """Zeigt Verwendungsinformationen an"""
    click.echo("\n" + "="*60)
    click.echo("🎉 INSTALLATION ABGESCHLOSSEN!")
    click.echo("="*60)

    if platform.system().lower() == "windows":
        python_cmd = "venv\\Scripts\\python.exe"
    else:
        python_cmd = "venv/bin/python"

    click.echo("\n📋 VERWENDUNG:")
    click.echo(f"  Einzelne URL:     {python_cmd} video_downloader.py https://example.com/video")
    click.echo(f"  Mehrere URLs:     {python_cmd} video_downloader.py url1 url2 url3")
    click.echo(f"  Mit Konfiguration: {python_cmd} video_downloader.py --config my_config.json url")
    click.echo(f"  Headless-Modus:   {python_cmd} video_downloader.py --headless url")

    click.echo("\n⚙️ KONFIGURATION:")
    click.echo("  - Bearbeiten Sie config.json für Site-spezifische Einstellungen")
    click.echo("  - Fügen Sie Ihre NordVPN-Anmeldedaten hinzu")
    click.echo("  - Konfigurieren Sie Site-Selektoren in config.json")

    click.echo("\n🔧 NÄCHSTE SCHRITTE:")
    click.echo("  1. NordVPN anmelden: nordvpn login")
    click.echo("  2. config.json anpassen")
    click.echo("  3. Ersten Download testen")

    click.echo("\n📝 LOGS:")
    click.echo("  - Logs werden in video_downloader.log gespeichert")
    click.echo("  - Log-Level in config.json einstellbar")


@click.command()
@click.option('--skip-vpn', is_flag=True, help='NordVPN-Installation überspringen')
@click.option('--skip-ffmpeg', is_flag=True, help='FFmpeg-Installation überspringen')
@click.option('--skip-tests', is_flag=True, help='Tests überspringen')
def main(skip_vpn: bool, skip_ffmpeg: bool, skip_tests: bool):
    """Setup-Script für Web Video Downloader"""

    click.echo("🚀 Web Video Downloader Setup")
    click.echo("="*40)

    # Schritt 1: Python-Version prüfen
    if not check_python_version():
        sys.exit(1)

    # Schritt 2: System-Dependencies
    if not skip_ffmpeg:
        if not install_ffmpeg():
            click.echo("⚠️ FFmpeg-Installation fehlgeschlagen, aber weiter...")

    if not skip_vpn:
        if not install_nordvpn():
            click.echo("⚠️ NordVPN-Installation fehlgeschlagen, aber weiter...")

    # Schritt 3: Python-Dependencies
    if not install_python_dependencies():
        click.echo("❌ Python-Dependencies-Installation fehlgeschlagen")
        sys.exit(1)

    # Schritt 4: Konfigurationsdateien
    create_config_files()

    # Schritt 5: Tests
    if not skip_tests:
        if not run_tests():
            click.echo("⚠️ Tests fehlgeschlagen, aber Installation fortgesetzt")

    # Schritt 6: Informationen anzeigen
    print_usage_info()


if __name__ == "__main__":
    main()
