#!/usr/bin/env python3
"""
Erweiterte Utilities für Web Video Downloader
Umfasst Monitoring, Analyse, Performance-Tracking und Debug-Tools
"""

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import psutil
import structlog
from pydantic import BaseModel
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table


# ============================
# PERFORMANCE MONITORING
# ============================

@dataclass
class PerformanceMetrics:
    """Performance-Metriken für Download-Vorgänge"""
    
    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    network_bytes_sent: int
    network_bytes_recv: int
    disk_io_read: int
    disk_io_write: int
    active_downloads: int
    download_speed_mbps: float = 0.0


class PerformanceMonitor:
    """Überwacht System-Performance während Downloads"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__ + ".PerformanceMonitor")
        self.metrics_history: List[PerformanceMetrics] = []
        self.start_time = time.time()
        self.process = psutil.Process()
    
    def capture_metrics(self, active_downloads: int = 0) -> PerformanceMetrics:
        """Erfasst aktuelle System-Metriken"""
        try:
            # System-Metriken
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            network = psutil.net_io_counters()
            disk_io = psutil.disk_io_counters()
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_mb=memory.used / 1024 / 1024,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                disk_io_read=disk_io.read_bytes,
                disk_io_write=disk_io.write_bytes,
                active_downloads=active_downloads
            )
            
            self.metrics_history.append(metrics)
            
            # Nur letzte 1000 Metriken behalten
            if len(self.metrics_history) > 1000:
                self.metrics_history = self.metrics_history[-1000:]
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Fehler beim Erfassen der Metriken: {e}")
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_mb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                disk_io_read=0,
                disk_io_write=0,
                active_downloads=active_downloads
            )
    
    def get_average_metrics(self, minutes: int = 5) -> Dict[str, float]:
        """Berechnet Durchschnitts-Metriken der letzten N Minuten"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {}
        
        return {
            'avg_cpu_percent': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
            'avg_memory_mb': sum(m.memory_mb for m in recent_metrics) / len(recent_metrics),
            'max_active_downloads': max(m.active_downloads for m in recent_metrics),
            'total_metrics_count': len(recent_metrics)
        }
    
    def export_metrics(self, filepath: Path):
        """Exportiert Metriken zu JSON-Datei"""
        try:
            data = [asdict(metric) for metric in self.metrics_history]
            
            # Datetime zu String konvertieren
            for item in data:
                item['timestamp'] = item['timestamp'].isoformat()
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Metriken exportiert zu {filepath}")
            
        except Exception as e:
            self.logger.error(f"Fehler beim Exportieren der Metriken: {e}")


# ============================
# VIDEO ANALYSIS TOOLS
# ============================

class VideoAnalyzer:
    """Analysiert Video-URLs und extrahiert Metadaten"""
    
    def __init__(self):
        self.logger = structlog.get_logger(__name__ + ".VideoAnalyzer")
        self.video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        self.streaming_domains = {
            'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'twitch.tv', 'facebook.com', 'instagram.com'
        }
    
    def analyze_url(self, url: str) -> Dict[str, Any]:
        """Analysiert URL und gibt Informationen zurück"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            
            analysis = {
                'url': url,
                'domain': domain,
                'path': parsed.path,
                'is_direct_video': self._is_direct_video_url(url),
                'is_streaming_platform': domain in self.streaming_domains,
                'requires_extraction': not self._is_direct_video_url(url),
                'estimated_complexity': self._estimate_complexity(url, domain),
                'suggested_method': self._suggest_extraction_method(url, domain)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"URL-Analyse fehlgeschlagen für {url}: {e}")
            return {'url': url, 'error': str(e)}
    
    def _is_direct_video_url(self, url: str) -> bool:
        """Prüft ob URL direkt auf Video-Datei zeigt"""
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in self.video_extensions)
    
    def _estimate_complexity(self, url: str, domain: str) -> str:
        """Schätzt Komplexität der Video-Extraktion"""
        if self._is_direct_video_url(url):
            return 'low'
        elif domain in self.streaming_domains:
            return 'medium'
        else:
            return 'high'
    
    def _suggest_extraction_method(self, url: str, domain: str) -> str:
        """Schlägt Extraktions-Methode vor"""
        if self._is_direct_video_url(url):
            return 'direct_download'
        elif domain in self.streaming_domains:
            return 'yt_dlp'
        else:
            return 'browser_automation'
    
    def batch_analyze(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Analysiert mehrere URLs gleichzeitig"""
        results = []
        for url in urls:
            analysis = self.analyze_url(url)
            results.append(analysis)
        
        return results
    
    def generate_analysis_report(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generiert Zusammenfassungsbericht der Analysen"""
        total_urls = len(analyses)
        direct_videos = sum(1 for a in analyses if a.get('is_direct_video', False))
        streaming_platforms = sum(1 for a in analyses if a.get('is_streaming_platform', False))
        
        complexity_distribution = {}
        method_distribution = {}
        
        for analysis in analyses:
            complexity = analysis.get('estimated_complexity', 'unknown')
            method = analysis.get('suggested_method', 'unknown')
            
            complexity_distribution[complexity] = complexity_distribution.get(complexity, 0) + 1
            method_distribution[method] = method_distribution.get(method, 0) + 1
        
        return {
            'total_urls': total_urls,
            'direct_videos': direct_videos,
            'streaming_platforms': streaming_platforms,
            'complexity_distribution': complexity_distribution,
            'method_distribution': method_distribution,
            'success_probability': self._estimate_success_probability(analyses)
        }
    
    def _estimate_success_probability(self, analyses: List[Dict[str, Any]]) -> float:
        """Schätzt Gesamt-Erfolgswahrscheinlichkeit"""
        if not analyses:
            return 0.0
        
        success_weights = {
            'direct_download': 0.95,
            'yt_dlp': 0.85,
            'browser_automation': 0.60
        }
        
        total_weight = 0.0
        for analysis in analyses:
            method = analysis.get('suggested_method', 'browser_automation')
            total_weight += success_weights.get(method, 0.50)
        
        return total_weight / len(analyses)


# ============================
# DOWNLOAD HISTORY DATABASE
# ============================

class DownloadHistory:
    """Verwaltet Download-Historie in SQLite-Datenbank"""
    
    def __init__(self, db_path: str = "download_history.db"):
        self.db_path = Path(db_path)
        self.logger = structlog.get_logger(__name__ + ".DownloadHistory")
        self._init_database()
    
    def _init_database(self):
        """Initialisiert SQLite-Datenbank"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        domain TEXT,
                        title TEXT,
                        filepath TEXT,
                        filesize INTEGER,
                        duration INTEGER,
                        download_time REAL,
                        success BOOLEAN,
                        error_message TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_url ON downloads(url);
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_domain ON downloads(domain);
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp ON downloads(timestamp);
                """)
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Datenbank-Initialisierung fehlgeschlagen: {e}")
    
    def add_download(self, 
                    url: str,
                    success: bool,
                    title: str = None,
                    filepath: str = None,
                    filesize: int = None,
                    duration: int = None,
                    download_time: float = None,
                    error_message: str = None,
                    ip_address: str = None,
                    user_agent: str = None):
        """Fügt Download-Eintrag zur Historie hinzu"""
        try:
            domain = urlparse(url).netloc.replace('www.', '')
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO downloads 
                    (url, domain, title, filepath, filesize, duration, download_time, 
                     success, error_message, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (url, domain, title, filepath, filesize, duration, download_time,
                      success, error_message, ip_address, user_agent))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Fehler beim Hinzufügen zur Download-Historie: {e}")
    
    def get_download_stats(self, days: int = 30) -> Dict[str, Any]:
        """Erstellt Download-Statistiken der letzten N Tage"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Gesamt-Statistiken
                total_result = conn.execute("""
                    SELECT 
                        COUNT(*) as total_downloads,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                        AVG(download_time) as avg_download_time,
                        SUM(filesize) as total_filesize
                    FROM downloads 
                    WHERE timestamp >= ?
                """, (cutoff_date,)).fetchone()
                
                # Top-Domains
                domain_results = conn.execute("""
                    SELECT domain, COUNT(*) as count
                    FROM downloads 
                    WHERE timestamp >= ?
                    GROUP BY domain
                    ORDER BY count DESC
                    LIMIT 10
                """, (cutoff_date,)).fetchall()
                
                # Fehler-Analyse
                error_results = conn.execute("""
                    SELECT error_message, COUNT(*) as count
                    FROM downloads 
                    WHERE timestamp >= ? AND success = 0 AND error_message IS NOT NULL
                    GROUP BY error_message
                    ORDER BY count DESC
                    LIMIT 5
                """, (cutoff_date,)).fetchall()
                
                return {
                    'period_days': days,
                    'total_downloads': total_result['total_downloads'],
                    'successful': total_result['successful'],
                    'failed': total_result['failed'],
                    'success_rate': (total_result['successful'] / total_result['total_downloads'] * 100) if total_result['total_downloads'] > 0 else 0,
                    'avg_download_time': total_result['avg_download_time'],
                    'total_filesize_gb': (total_result['total_filesize'] or 0) / 1024 / 1024 / 1024,
                    'top_domains': [dict(row) for row in domain_results],
                    'common_errors': [dict(row) for row in error_results]
                }
                
        except Exception as e:
            self.logger.error(f"Fehler beim Erstellen der Download-Statistiken: {e}")
            return {}
    
    def cleanup_old_entries(self, days: int = 90):
        """Bereinigt alte Einträge aus der Datenbank"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute("""
                    DELETE FROM downloads 
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                deleted_count = result.rowcount
                conn.commit()
                
                self.logger.info(f"{deleted_count} alte Einträge bereinigt")
                
        except Exception as e:
            self.logger.error(f"Fehler beim Bereinigen alter Einträge: {e}")


# ============================
# RICH CONSOLE OUTPUT
# ============================

class RichDisplay:
    """Verbesserte Console-Ausgabe mit Rich"""
    
    def __init__(self):
        self.console = Console()
    
    def display_analysis_results(self, analyses: List[Dict[str, Any]]):
        """Zeigt URL-Analyse-Ergebnisse in einer Tabelle"""
        table = Table(title="URL-Analyse Ergebnisse")
        
        table.add_column("URL", style="cyan", no_wrap=True, max_width=40)
        table.add_column("Domain", style="magenta")
        table.add_column("Typ", style="green")
        table.add_column("Komplexität", style="yellow")
        table.add_column("Methode", style="blue")
        
        for analysis in analyses:
            url = analysis.get('url', 'N/A')
            domain = analysis.get('domain', 'N/A')
            
            video_type = "Direkt" if analysis.get('is_direct_video') else "Extraction"
            if analysis.get('is_streaming_platform'):
                video_type = "Streaming"
            
            complexity = analysis.get('estimated_complexity', 'Unknown').title()
            method = analysis.get('suggested_method', 'Unknown').replace('_', ' ').title()
            
            table.add_row(url[:37] + "..." if len(url) > 40 else url, 
                         domain, video_type, complexity, method)
        
        self.console.print(table)
    
    def display_download_stats(self, stats: Dict[str, Any]):
        """Zeigt Download-Statistiken"""
        table = Table(title=f"Download-Statistiken ({stats.get('period_days', 'N/A')} Tage)")
        
        table.add_column("Metrik", style="cyan")
        table.add_column("Wert", style="green")
        
        table.add_row("Gesamt Downloads", str(stats.get('total_downloads', 0)))
        table.add_row("Erfolgreich", str(stats.get('successful', 0)))
        table.add_row("Fehlgeschlagen", str(stats.get('failed', 0)))
        table.add_row("Erfolgsrate", f"{stats.get('success_rate', 0):.1f}%")
        table.add_row("Ø Download-Zeit", f"{stats.get('avg_download_time', 0):.2f}s")
        table.add_row("Gesamt-Größe", f"{stats.get('total_filesize_gb', 0):.2f} GB")
        
        self.console.print(table)
        
        # Top-Domains anzeigen
        if stats.get('top_domains'):
            domain_table = Table(title="Top-Domains")
            domain_table.add_column("Domain", style="cyan")
            domain_table.add_column("Downloads", style="green")
            
            for domain_stat in stats.get('top_domains', []):
                domain_table.add_row(domain_stat.get('domain', 'N/A'), 
                                   str(domain_stat.get('count', 0)))
            
            self.console.print(domain_table)
    
    def display_progress_summary(self, results: List[Any]):
        """Zeigt Fortschritts-Zusammenfassung"""
        successful = sum(1 for r in results if getattr(r, 'success', False))
        failed = len(results) - successful
        
        self.console.print(f"\n[bold green]✅ Erfolgreich: {successful}[/bold green]")
        self.console.print(f"[bold red]❌ Fehlgeschlagen: {failed}[/bold red]")
        self.console.print(f"[bold blue]📊 Erfolgsrate: {successful/len(results)*100:.1f}%[/bold blue]")


# ============================
# ERROR RECOVERY & RETRY LOGIC
# ============================

class ErrorRecovery:
    """Erweiterte Fehlerbehandlung und Recovery-Mechanismen"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.logger = structlog.get_logger(__name__ + ".ErrorRecovery")
        self.error_patterns = {
            'network_timeout': ['timeout', 'connection', 'network'],
            'video_not_found': ['not found', '404', 'does not exist'],
            'access_denied': ['403', 'forbidden', 'access denied'],
            'rate_limited': ['rate limit', '429', 'too many requests'],
            'login_required': ['login', 'authentication', 'unauthorized']
        }
    
    def categorize_error(self, error_message: str) -> str:
        """Kategorisiert Fehler basierend auf Nachrichten"""
        error_lower = error_message.lower()
        
        for category, patterns in self.error_patterns.items():
            if any(pattern in error_lower for pattern in patterns):
                return category
        
        return 'unknown'
    
    def suggest_recovery_action(self, error_category: str, attempt: int) -> Dict[str, Any]:
        """Schlägt Recovery-Aktion basierend auf Fehler-Kategorie vor"""
        actions = {
            'network_timeout': {
                'action': 'retry_with_delay',
                'delay': min(30 * attempt, 3
