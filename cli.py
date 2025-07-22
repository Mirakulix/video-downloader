#!/usr/bin/env python3
"""
Advanced CLI für Web Video Downloader
Modernes Click-basiertes Interface mit Rich-Output und umfassenden Features
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import click
import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

# Unsere Module
from video_downloader import WebVideoDownloader
from utilities import (
    VideoAnalyzer, PerformanceMonitor, DownloadHistory,
    RichDisplay, setup_structured_logging
)


class CLIContext:
    """Shared Context für CLI-Befehle"""
    
    def __init__(self):
        self.console = Console()
        self.config_path = "config.json"
        self.verbose = False
        self.quiet = False


# Global Context für Click
pass_context = click.make_pass_decorator(CLIContext, ensure=True)


@click.group()
@click.option('--config', '-c', default='config.json', 
              help='Pfad zur Konfigurationsdatei')
@click.option('--verbose', '-v', is_flag=True, 
              help='Ausführliche Ausgabe')
@click.option('--quiet', '-q', is_flag=True, 
              help='Minimale Ausgabe')
@click.version_option(version='1.0.0', prog_name='Web Video Downloader')
@pass_context
def cli(ctx: CLIContext, config: str, verbose: bool, quiet: bool):
    """
    🎥 Advanced Web Video Downloader mit VPN-Integration
    
    Automatisierter Video-Download mit Browser-Automatisierung,
    NordVPN IP-Rotation und intelligenter Site-Erkennung.
    """
    ctx.config_path = config
    ctx.verbose = verbose
    ctx.quiet = quiet
    
    # Logging konfigurieren
    log_level = "DEBUG" if verbose else "ERROR" if quiet else "INFO"
    setup_structured_logging(log_level)


@cli.command()
@click.argument('urls', nargs=-1, required=True)
@click.option('--output', '-o', default='./downloads',
              help='Output-Verzeichnis für Downloads')
@click.option('--no-vpn', is_flag=True,
              help='VPN-Funktionalität deaktivieren')
@click.option('--headless/--no-headless', default=True,
              help='Browser im Headless-Modus ausführen')
@click.option('--concurrent', '-j', default=3,
              help='Anzahl paralleler Downloads')
@click.option('--retry', '-r', default=3,
              help='Anzahl Wiederholungsversuche bei Fehlern')
@click.option('--analyze-only', is_flag=True,
              help='Nur URL-Analyse ohne Downloads')
@pass_context
def download(ctx: CLIContext, urls: tuple, output: str, no_vpn: bool, 
             headless: bool, concurrent: int, retry: int, analyze_only: bool):
    """
    📥 Videos von URLs herunterladen
    
    URLS: Eine oder mehrere Video-URLs zum Herunterladen
    
    Beispiele:
      video-dl download https://example.com/video1 https://example.com/video2
      video-dl download --no-vpn --output ./my-videos https://site.com/video
      video-dl download --analyze-only https://unknown-site.com/video
    """
    
    async def _download():
        # URL-Analyse zuerst
        analyzer = VideoAnalyzer()
        display = RichDisplay()
        
        ctx.console.print(Panel(
            f"🔍 Analysiere {len(urls)} URL(s)...",
            title="URL-Analyse",
            style="cyan"
        ))
        
        analyses = analyzer.batch_analyze(list(urls))
        display.display_analysis_results(analyses)
        
        report = analyzer.generate_analysis_report(analyses)
        ctx.console.print(f"\n[green]📊 Erfolgswahrscheinlichkeit: {report['success_probability']:.1%}[/green]")
        
        if analyze_only:
            ctx.console.print("\n[yellow]🔍 Nur Analyse durchgeführt (--analyze-only)[/yellow]")
            return
        
        # Download-Konfiguration anpassen
        config_path = Path(ctx.config_path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # CLI-Optionen überschreiben Config
        config.update({
            'output_directory': output,
            'nordvpn_enabled': not no_vpn,
            'headless': headless,
            'concurrent_downloads': concurrent,
            'retry_attempts': retry
        })
        
        # Temporäre Config speichern
        temp_config = Path('.temp_config.json')
        with open(temp_config, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        try:
            # Downloads ausführen
            ctx.console.print(Panel(
                f"🚀 Starte Download von {len(urls)} Video(s)...",
                title="Download",
                style="green"
            ))
            
            async with WebVideoDownloader(str(temp_config)) as downloader:
                results = await downloader.download_multiple_urls(list(urls))
            
            # Ergebnisse anzeigen
            display.display_progress_summary(results)
            
            # Detaillierte Ergebnisse bei Verbose
            if ctx.verbose:
                table = Table(title="Detaillierte Ergebnisse")
                table.add_column("URL", style="cyan", max_width=50)
                table.add_column("Status", style="green")
                table.add_column("Datei", style="blue")
                table.add_column("Zeit", style="yellow")
                
                for result in results:
                    status = "✅ Erfolg" if result.success else "❌ Fehler"
                    filepath = str(result.filepath.name) if result.filepath else "N/A"
                    time_str = f"{result.download_time:.2f}s" if result.download_time else "N/A"
                    
                    table.add_row(
                        result.url[:47] + "..." if len(result.url) > 50 else result.url,
                        status,
                        filepath,
                        time_str
                    )
                
                ctx.console.print(table)
        
        finally:
            # Temporäre Config löschen
            if temp_config.exists():
                temp_config.unlink()
    
    # Async ausführen
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(_download())


@cli.command()
@click.option('--days', '-d', default=30,
              help='Zeitraum in Tagen für Statistiken')
@click.option('--export', '-e', 
              help='Statistiken in JSON-Datei exportieren')
@pass_context
def stats(ctx: CLIContext, days: int, export: Optional[str]):
    """
    📊 Download-Statistiken anzeigen
    
    Zeigt detaillierte Statistiken über vergangene Downloads,
    Erfolgsraten, Top-Domains und häufige Fehler.
    """
    history = DownloadHistory()
    display = RichDisplay()
    
    ctx.console.print(Panel(
        f"📈 Lade Statistiken der letzten {days} Tage...",
        title="Statistiken",
        style="blue"
    ))
    
    stats_data = history.get_download_stats(days=days)
    
    if not stats_data:
        ctx.console.print("[yellow]📭 Keine Download-Historie gefunden[/yellow]")
        return
    
    display.display_download_stats(stats_data)
    
    # Export falls angefordert
    if export:
        export_path = Path(export)
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)
        ctx.console.print(f"[green]💾 Statistiken exportiert nach: {export_path}[/green]")


@cli.command()
@click.argument('urls', nargs=-1)
@click.option('--detailed', '-d', is_flag=True,
              help='Detaillierte Analyse mit Extraktions-Strategien')
@click.option('--json-output', '-j',
              help='Ergebnisse als JSON speichern')
@pass_context
def analyze(ctx: CLIContext, urls: tuple, detailed: bool, json_output: Optional[str]):
    """
    🔍 URLs analysieren ohne Download
    
    Analysiert Video-URLs und zeigt Extraktions-Komplexität,
    empfohlene Methoden und Erfolgswahrscheinlichkeit.
    
    URLS: URLs zum Analysieren (falls leer: interaktive Eingabe)
    """
    if not urls:
        ctx.console.print("[blue]📝 Geben Sie URLs ein (eine pro Zeile, leere Zeile zum Beenden):[/blue]")
        url_list = []
        try:
            while True:
                url = input("URL: ").strip()
                if not url:
                    break
                if url.startswith(('http://', 'https://')):
                    url_list.append(url)
                    ctx.console.print(f"[green]✅ {url}[/green]")
                else:
                    ctx.console.print("[red]❌ Ungültige URL[/red]")
        except KeyboardInterrupt:
            ctx.console.print("\n[yellow]Abgebrochen[/yellow]")
            return
        
        urls = tuple(url_list)
    
    if not urls:
        ctx.console.print("[red]❌ Keine URLs zum Analysieren[/red]")
        return
    
    analyzer = VideoAnalyzer()
    display = RichDisplay()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=ctx.console,
        transient=True
    ) as progress:
        task = progress.add_task("Analysiere URLs...", total=len(urls))
        
        analyses = []
        for url in urls:
            analysis = analyzer.analyze_url(url)
            analyses.append(analysis)
            progress.advance(task)
    
    # Ergebnisse anzeigen
    display.display_analysis_results(analyses)
    
    # Zusammenfassungsbericht
    report = analyzer.generate_analysis_report(analyses)
    
    summary_table = Table(title="Analyse-Zusammenfassung")
    summary_table.add_column("Metrik", style="cyan")
    summary_table.add_column("Wert", style="green")
    
    summary_table.add_row("Gesamt URLs", str(report['total_urls']))
    summary_table.add_row("Direkte Videos", str(report['direct_videos']))
    summary_table.add_row("Streaming-Plattformen", str(report['streaming_platforms']))
    summary_table.add_row("Erfolgswahrscheinlichkeit", f"{report['success_probability']:.1%}")
    
    ctx.console.print(summary_table)
    
    # Detaillierte Analyse
    if detailed:
        complexity_table = Table(title="Komplexitäts-Verteilung")
        complexity_table.add_column("Komplexität", style="yellow")
        complexity_table.add_column("Anzahl", style="green")
        
        for complexity, count in report['complexity_distribution'].items():
            complexity_table.add_row(complexity.title(), str(count))
        
        ctx.console.print(complexity_table)
    
    # JSON-Export
    if json_output:
        export_data = {
            'analyses': analyses,
            'report': report,
            'timestamp': str(asyncio.get_event_loop().time())
        }
        
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        ctx.console.print(f"[green]💾 Analyse exportiert nach: {json_output}[/green]")


@cli.command()
@click.option('--create-example', is_flag=True,
              help='Beispiel-Konfiguration erstellen')
@click.option('--validate', is_flag=True,
              help='Konfiguration validieren')
@click.option('--show', is_flag=True,
              help='Aktuelle Konfiguration anzeigen')
@pass_context
def config(ctx: CLIContext, create_example: bool, validate: bool, show: bool):
    """
    ⚙️ Konfiguration verwalten
    
    Erstellt, validiert oder zeigt die Downloader-Konfiguration.
    """
    config_path = Path(ctx.config_path)
    
    if create_example:
        example_config = {
            "sites": {
                "example-site.com": {
                    "video_button": [".play-btn", "button[data-play]"],
                    "download_link": ["a[href*='.mp4']", ".download-link"],
                    "login_username": "user@example.com",
                    "login_password": "secure_password",
                    "human_delay_min": 1.5,
                    "human_delay_max": 3.0
                }
            },
            "output_directory": "./downloads",
            "nordvpn_enabled": True,
            "ip_rotation_interval_min": 300,
            "ip_rotation_interval_max": 1800,
            "headless": True,
            "timeout": 30,
            "concurrent_downloads": 3,
            "retry_attempts": 3,
            "log_level": "INFO"
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        
        ctx.console.print(f"[green]✅ Beispiel-Konfiguration erstellt: {config_path}[/green]")
        return
    
    if not config_path.exists():
        ctx.console.print(f"[red]❌ Konfigurationsdatei nicht gefunden: {config_path}[/red]")
        ctx.console.print("[blue]💡 Verwenden Sie --create-example für eine Beispiel-Konfiguration[/blue]")
        return
    
    # Konfiguration laden
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        ctx.console.print(f"[red]❌ Ungültiges JSON in Konfiguration: {e}[/red]")
        return
    except Exception as e:
        ctx.console.print(f"[red]❌ Fehler beim Laden der Konfiguration: {e}[/red]")
        return
    
    if validate:
        # Validierung mit Pydantic-Modell
        try:
            from video_downloader import GlobalConfig
            GlobalConfig(**config_data)
            ctx.console.print("[green]✅ Konfiguration ist gültig[/green]")
        except Exception as e:
            ctx.console.print(f"[red]❌ Konfigurationsfehler: {e}[/red]")
        return
    
    if show:
        # Konfiguration anzeigen
        table = Table(title="Aktuelle Konfiguration")
        table.add_column("Einstellung", style="cyan")
        table.add_column("Wert", style="green")
        
        # Haupteinstellungen
        table.add_row("Output-Verzeichnis", str(config_data.get('output_directory', 'N/A')))
        table.add_row("VPN aktiviert", str(config_data.get('nordvpn_enabled', 'N/A')))
        table.add_row("Headless-Modus", str(config_data.get('headless', 'N/A')))
        table.add_row("Parallele Downloads", str(config_data.get('concurrent_downloads', 'N/A')))
        table.add_row("Timeout", f"{config_data.get('timeout', 'N/A')}s")
        table.add_row("Log-Level", str(config_data.get('log_level', 'N/A')))
        table.add_row("Konfigurierte Sites", str(len(config_data.get('sites', {}))))
        
        ctx.console.print(table)
        
        # Site-Details bei Verbose
        if ctx.verbose and config_data.get('sites'):
            sites_table = Table(title="Konfigurierte Sites")
            sites_table.add_column("Domain", style="cyan")
            sites_table.add_column("Video-Buttons", style="yellow")
            sites_table.add_column("Download-Links", style="green")
            sites_table.add_column("Login", style="blue")
            
            for domain, site_config in config_data['sites'].items():
                video_buttons = len(site_config.get('video_button', []))
                download_links = len(site_config.get('download_link', []))
                has_login = bool(site_config.get('login_username'))
                
                sites_table.add_row(
                    domain,
                    f"{video_buttons} Selektoren",
                    f"{download_links} Selektoren", 
                    "✅" if has_login else "❌"
                )
            
            ctx.console.print(sites_table)


@cli.command()
@click.option('--days', '-d', default=90,
              help='Einträge älter als N Tage löschen')
@click.option('--confirm', is_flag=True,
              help='Löschung ohne Nachfrage bestätigen')
@pass_context
def cleanup(ctx: CLIContext, days: int, confirm: bool):
    """
    🧹 Download-Historie bereinigen
    
    Löscht alte Einträge aus der Download-Historie-Datenbank.
    """
    history = DownloadHistory()
    
    if not confirm:
        response = click.confirm(f"Wirklich alle Einträge älter als {days} Tage löschen?")
        if not response:
            ctx.console.print("[yellow]🚫 Bereinigung abgebrochen[/yellow]")
            return
    
    with ctx.console.status("🧹 Bereinige alte Einträge..."):
        history.cleanup_old_entries(days=days)
    
    ctx.console.print(f"[green]✅ Historie bereinigt (Einträge älter als {days} Tage entfernt)[/green]")


@cli.command()
@pass_context  
def doctor(ctx: CLIContext):
    """
    🏥 System-Diagnose durchführen
    
    Überprüft Installation, Dependencies und Konfiguration.
    """
    ctx.console.print(Panel(
        "🔍 Führe System-Diagnose durch...",
        title="System-Check",
        style="blue"
    ))
    
    checks = []
    
    # Python-Version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_ok = sys.version_info >= (3, 9)
    checks.append(("Python Version", python_version, python_ok))
    
    # Dependencies prüfen
    try:
        import playwright
        playwright_ok = True
        playwright_version = playwright.__version__
    except ImportError:
        playwright_ok = False
        playwright_version = "Nicht installiert"
    checks.append(("Playwright", playwright_version, playwright_ok))
    
    try:
        import yt_dlp
        ytdlp_ok = True
        ytdlp_version = yt_dlp.version.__version__
    except ImportError:
        ytdlp_ok = False
        ytdlp_version = "Nicht installiert"
    checks.append(("yt-dlp", ytdlp_version, ytdlp_ok))
    
    # FFmpeg prüfen
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        ffmpeg_ok = result.returncode == 0
        ffmpeg_version = result.stdout.split('\n')[0] if ffmpeg_ok else "Fehler"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        ffmpeg_ok = False
        ffmpeg_version = "Nicht gefunden"
    checks.append(("FFmpeg", ffmpeg_version, ffmpeg_ok))
    
    # NordVPN prüfen
    try:
        result = subprocess.run(['nordvpn', '--version'], capture_output=True, text=True, timeout=5)
        nordvpn_ok = result.returncode == 0
        nordvpn_version = result.stdout.strip() if nordvpn_ok else "Fehler"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        nordvpn_ok = False
        nordvpn_version = "Nicht installiert"
    checks.append(("NordVPN CLI", nordvpn_version, nordvpn_ok))
    
    # Konfiguration prüfen
    config_path = Path(ctx.config_path)
    config_ok = config_path.exists()
    config_status = "Gefunden" if config_ok else "Nicht gefunden"
    checks.append(("Konfiguration", config_status, config_ok))
    
    # Ergebnisse anzeigen
    table = Table(title="System-Diagnose")
    table.add_column("Komponente", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Version/Info", style="blue")
    table.add_column("OK", style="green")
    
    all_ok = True
    for component, version, ok in checks:
        status_icon = "✅" if ok else "❌"
        table.add_row(component, status_icon, version, "OK" if ok else "FEHLER")
        if not ok:
            all_ok = False
    
    ctx.console.print(table)
    
    if all_ok:
        ctx.console.print("\n[green]🎉 Alle Checks erfolgreich! System ist bereit.[/green]")
    else:
        ctx.console.print("\n[red]⚠️ Einige Checks fehlgeschlagen. Bitte prüfen Sie die Installation.[/red]")
        ctx.console.print("\n[blue]💡 Hilfe:[/blue]")
        ctx.console.print("  • Python: Mindestens Version 3.9 erforderlich")
        ctx.console.print("  • Playwright: pip install playwright && playwright install chromium")
        ctx.console.print("  • yt-dlp: pip install yt-dlp")
        ctx.console.print("  • FFmpeg: https://ffmpeg.org/download.html")
               
