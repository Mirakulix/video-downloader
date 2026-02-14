#!/usr/bin/env python3
"""
Umfassendes Beispiel für die Verwendung des Web Video Downloaders
Demonstriert alle Features: VPN-Integration, Site-Konfiguration, 
Performance-Monitoring, Analyse-Tools und erweiterte Funktionen
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import unserer Module
from video_downloader import WebVideoDownloader
from utilities import (
    VideoAnalyzer, PerformanceMonitor, DownloadHistory,
    RichDisplay, ErrorRecovery, setup_structured_logging
)


class VideoDownloaderDemo:
    """Demo-Klasse für umfassende Video-Downloader-Funktionalität"""
    
    def __init__(self):
        self.console = Console()
        self.display = RichDisplay()
        self.analyzer = VideoAnalyzer()
        self.performance_monitor = PerformanceMonitor()
        self.download_history = DownloadHistory()
        self.error_recovery = ErrorRecovery()
        
        # Setup strukturiertes Logging
        setup_structured_logging("INFO")
    
    def print_banner(self):
        """Zeigt Banner mit Programm-Info"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                   WEB VIDEO DOWNLOADER                      ║
║                    Advanced Demo Script                     ║
║                                                              ║
║  Features:                                                   ║
║  • NordVPN Integration mit IP-Rotation                      ║
║  • Browser-Automatisierung (Playwright)                    ║
║  • yt-dlp für beste Video-Qualität                         ║
║  • Performance-Monitoring                                   ║
║  • Download-Historie & Statistiken                         ║
║  • Intelligente Fehlerbehandlung                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        self.console.print(Panel(banner, style="cyan"))
    
    async def demo_url_analysis(self, urls: List[str]):
        """Demonstriert URL-Analyse-Features"""
        self.console.print("\n[bold yellow]🔍 URL-ANALYSE[/bold yellow]")
        self.console.print("Analysiere URLs vor dem Download...\n")
        
        # URLs analysieren
        analyses = self.analyzer.batch_analyze(urls)
        
        # Ergebnisse anzeigen
        self.display.display_analysis_results(analyses)
        
        # Zusammenfassungsbericht
        report = self.analyzer.generate_analysis_report(analyses)
        
        self.console.print(f"\n[bold green]📊 ANALYSE-BERICHT:[/bold green]")
        self.console.print(f"  • Gesamt URLs: {report['total_urls']}")
        self.console.print(f"  • Direkte Videos: {report['direct_videos']}")
        self.console.print(f"  • Streaming-Plattformen: {report['streaming_platforms']}")
        self.console.print(f"  • Erfolgswahrscheinlichkeit: {report['success_probability']:.1%}")
        
        return analyses, report
    
    async def demo_performance_monitoring(self):
        """Demonstriert Performance-Monitoring"""
        self.console.print("\n[bold yellow]⚡ PERFORMANCE-MONITORING[/bold yellow]")
        self.console.print("Erfasse System-Metriken während des Downloads...\n")
        
        # Baseline-Metriken erfassen
        baseline_metrics = self.performance_monitor.capture_metrics(active_downloads=0)
        self.console.print(f"[green]Baseline CPU: {baseline_metrics.cpu_percent:.1f}%[/green]")
        self.console.print(f"[green]Baseline RAM: {baseline_metrics.memory_mb:.1f} MB[/green]")
        
        return baseline_metrics
    
    async def demo_download_with_monitoring(self, urls: List[str], config_path: str):
        """Führt Downloads mit umfassendem Monitoring durch"""
        self.console.print("\n[bold yellow]🚀 DOWNLOAD MIT MONITORING[/bold yellow]")
        
        results = []
        
        # Downloader mit Context Manager
        async with WebVideoDownloader(config_path) as downloader:
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                # Für jede URL einzeln verarbeiten (für besseres Monitoring)
                for i, url in enumerate(urls, 1):
                    task = progress.add_task(f"Download {i}/{len(urls)}: {url[:50]}...", total=1)
                    
                    # Performance vor Download
                    pre_metrics = self.performance_monitor.capture_metrics(active_downloads=1)
                    
                    try:
                        # Download ausführen
                        result = await downloader.process_single_url(url)
                        results.append(result)
                        
                        # Performance nach Download
                        post_metrics = self.performance_monitor.capture_metrics(active_downloads=0)
                        
                        # In Historie speichern
                        self.download_history.add_download(
                            url=url,
                            success=result.success,
                            title=result.video_info.title if result.video_info else None,
                            filepath=str(result.filepath) if result.filepath else None,
                            download_time=result.download_time,
                            error_message=result.error if not result.success else None,
                            ip_address=await downloader.vpn_manager.get_current_ip()
                        )
                        
                        # Status anzeigen
                        if result.success:
                            self.console.print(f"  ✅ [green]{url}[/green] - {result.download_time:.2f}s")
                        else:
                            self.console.print(f"  ❌ [red]{url}[/red] - {result.error}")
                            
                            # Fehleranalyse und Recovery-Vorschlag
                            error_category = self.error_recovery.categorize_error(result.error or "")
                            recovery_action = self.error_recovery.suggest_recovery_action(error_category, 1)
                            self.console.print(f"     💡 Vorschlag: {recovery_action.get('action', 'Manual intervention')}")
                        
                    except Exception as e:
                        self.console.print(f"  💥 [red]Unerwarteter Fehler bei {url}: {e}[/red]")
                        results.append(type('Result', (), {'url': url, 'success': False, 'error': str(e)})())
                    
                    progress.update(task, completed=1)
                    
                    # Kurze Pause zwischen Downloads für realistisches Verhalten
                    await asyncio.sleep(2)
        
        return results
    
    async def demo_statistics_and_history(self):
        """Zeigt Download-Statistiken und Historie"""
        self.console.print("\n[bold yellow]📈 DOWNLOAD-STATISTIKEN[/bold yellow]")
        
        # Statistiken der letzten 30 Tage
        stats = self.download_history.get_download_stats(days=30)
        
        if stats:
            self.display.display_download_stats(stats)
        else:
            self.console.print("[yellow]Keine Download-Historie gefunden[/yellow]")
        
        # Performance-Metriken exportieren
        metrics_file = Path("performance_metrics.json")
        self.performance_monitor.export_metrics(metrics_file)
        self.console.print(f"\n[blue]📊 Performance-Metriken exportiert nach: {metrics_file}[/blue]")
    
    def demo_configuration_management(self, config_path: str):
        """Zeigt Konfigurationsmanagement"""
        self.console.print("\n[bold yellow]⚙️ KONFIGURATIONSMANAGEMENT[/bold yellow]")
        
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.console.print(f"[green]📝 Konfiguration geladen aus: {config_path}[/green]")
            self.console.print(f"  • Konfigurierte Sites: {len(config.get('sites', {}))}")
            self.console.print(f"  • VPN aktiviert: {config.get('nordvpn_enabled', False)}")
            self.console.print(f"  • Output-Verzeichnis: {config.get('output_directory', './downloads')}")
            self.console.print(f"  • Parallele Downloads: {config.get('concurrent_downloads', 3)}")
            
            # Beispiel für Site-Konfiguration hinzufügen
            if not config.get('sites'):
                example_site = {
                    "example-video-site.com": {
                        "video_button": [".play-btn", "button[data-play]"],
                        "download_link": ["a[href*='.mp4']", ".download-link"],
                        "human_delay_min": 1.5,
                        "human_delay_max": 3.0
                    }
                }
                config['sites'].update(example_site)
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.console.print("[blue]➕ Beispiel-Site-Konfiguration hinzugefügt[/blue]")
        else:
            self.console.print(f"[red]❌ Konfigurationsdatei nicht gefunden: {config_path}[/red]")
    
    def create_sample_urls(self) -> List[str]:
        """Erstellt Beispiel-URLs für Demo (nur Platzhalter für eigene Services)"""
        return [
            "https://your-video-platform.com/video/123",
            "https://your-streaming-service.de/content/456", 
            "https://your-media-site.com/player/789"
        ]
    
    async def interactive_mode(self):
        """Interaktiver Modus für Benutzer-Input"""
        self.console.print("\n[bold yellow]🎛️ INTERAKTIVER MODUS[/bold yellow]")
        self.console.print("Geben Sie URLs ein (eine pro Zeile, leere Zeile zum Beenden):")
        
        urls = []
        while True:
            try:
                url = input("URL: ").strip()
                if not url:
                    break
                if url.startswith(('http://', 'https://')):
                    urls.append(url)
                    self.console.print(f"[green]✅ Hinzugefügt: {url}[/green]")
                else:
                    self.console.print("[red]❌ Ungültige URL (muss mit http:// oder https:// beginnen)[/red]")
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Abgebrochen durch Benutzer[/yellow]")
                break
        
        return urls
    
    async def run_complete_demo(self, config_path: str = "config.json", interactive: bool = False):
        """Führt komplette Demo-Session aus"""
        self.print_banner()
        
        # Konfiguration prüfen/erstellen
        self.demo_configuration_management(config_path)
        
        # URLs sammeln
        if interactive:
            urls = await self.interactive_mode()
            if not urls:
                self.console.print("[yellow]Keine URLs eingegeben. Verwende Beispiel-URLs.[/yellow]")
                urls = self.create_sample_urls()
        else:
            urls = self.create_sample_urls()
            self.console.print(f"\n[blue]📝 Verwende {len(urls)} Beispiel-URLs für Demo[/blue]")
        
        if not urls:
            self.console.print("[red]❌ Keine URLs zum Verarbeiten gefunden[/red]")
            return
        
        # URL-Analyse
        analyses, report = await self.demo_url_analysis(urls)
        
        # Performance-Monitoring Setup
        baseline = await self.demo_performance_monitoring()
        
        # Downloads mit Monitoring durchführen
        results = await self.demo_download_with_monitoring(urls, config_path)
        
        # Ergebnisse anzeigen
        self.display.display_progress_summary(results)
        
        # Statistiken zeigen
        await self.demo_statistics_and_history()
        
        # Abschlussmeldung
        self.console.print("\n" + "="*60)
        self.console.print("[bold green]🎉 DEMO ABGESCHLOSSEN![/bold green]")
        self.console.print("Alle Features wurden erfolgreich demonstriert.")
        self.console.print(f"Downloads gespeichert in: {Path('downloads').absolute()}")
        self.console.print(f"Logs verfügbar in: video_downloader.log")
        self.console.print("="*60)


async def main():
    """Hauptfunktion für Demo-Script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Web Video Downloader - Demo Script")
    parser.add_argument('--config', '-c', default='config.json', 
                       help='Pfad zur Konfigurationsdatei')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interaktiver Modus für URL-Eingabe')
    parser.add_argument('--urls', nargs='*', 
                       help='Direkte URL-Eingabe für Demo')
    
    args = parser.parse_args()
    
    # Demo-Instanz erstellen
    demo = VideoDownloaderDemo()
    
    try:
        if args.urls:
            # Direkte URLs verwenden
            demo.console.print(f"[blue]🎯 Verwende {len(args.urls)} direkte URLs[/blue]")
            
            # URL-Analyse
            analyses, report = await demo.demo_url_analysis(args.urls)
            
            # Performance-Monitoring
            baseline = await demo.demo_performance_monitoring()
            
            # Downloads
            results = await demo.demo_download_with_monitoring(args.urls, args.config)
            
            # Statistiken
            await demo.demo_statistics_and_history()
            
        else:
            # Vollständige Demo
            await demo.run_complete_demo(args.config, args.interactive)
            
    except KeyboardInterrupt:
        demo.console.print("\n[yellow]⏹️ Demo durch Benutzer abgebrochen[/yellow]")
    except Exception as e:
        demo.console.print(f"\n[red]💥 Unerwarteter Fehler: {e}[/red]")
        import traceback
        traceback.print_exc()
    
    return 0


if __name__ == "__main__":
    # Eventloop für Windows-Kompatibilität
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
