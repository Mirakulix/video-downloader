#!/usr/bin/env python3
"""
Umfassende Test-Suite für Web Video Downloader
Tests für alle Module mit pytest, asyncio und Mock-Integration
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

import pytest
from pydantic import ValidationError

# Import der zu testenden Module
from video_downloader import (
    WebVideoDownloader, VPNManager, VideoExtractor, HumanBehaviorSimulator,
    SiteConfig, GlobalConfig, VideoInfo, DownloadResult
)
from utilities import (
    VideoAnalyzer, PerformanceMonitor, DownloadHistory,
    ErrorRecovery, RichDisplay
)


# ================================================================
# FIXTURES
# ================================================================

@pytest.fixture
def temp_config_file():
    """Erstellt temporäre Konfigurationsdatei für Tests"""
    config_data = {
        "sites": {
            "test-site.com": {
                "video_button": [".play-btn"],
                "download_link": ["a[href*='.mp4']"],
                "human_delay_min": 0.1,
                "human_delay_max": 0.2
            }
        },
        "output_directory": "./test_downloads",
        "nordvpn_enabled": False,  # VPN für Tests deaktiviert
        "headless": True,
        "timeout": 10,
        "concurrent_downloads": 1,
        "retry_attempts": 1,
        "log_level": "DEBUG"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        yield f.name
    
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_download_dir():
    """Erstellt temporäres Download-Verzeichnis"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_video_info():
    """Sample VideoInfo für Tests"""
    return VideoInfo(
        url="https://test-site.com/video.mp4",
        title="Test Video",
        duration=120,
        quality="1080p",
        direct_url="https://test-site.com/direct.mp4"
    )


@pytest.fixture
def sample_urls():
    """Sample URLs für Tests"""
    return [
        "https://test-site.com/video1.mp4",
        "https://test-site.com/video2",
        "https://youtube.com/watch?v=test123",
        "https://unknown-site.com/player/456"
    ]


# ================================================================
# CONFIGURATION TESTS
# ================================================================

class TestConfiguration:
    """Tests für Konfigurationsmodelle"""
    
    def test_site_config_valid(self):
        """Test: Gültige Site-Konfiguration"""
        config = SiteConfig(
            video_button=[".play-btn", "button.play"],
            download_link=["a[href*='.mp4']"],
            login_username="test@example.com",
            human_delay_min=1.0,
            human_delay_max=3.0
        )
        
        assert len(config.video_button) == 2
        assert config.login_username == "test@example.com"
        assert config.human_delay_min == 1.0
    
    def test_site_config_string_conversion(self):
        """Test: String zu List Konvertierung"""
        config = SiteConfig(video_button=".single-button")
        assert config.video_button == [".single-button"]
    
    def test_global_config_defaults(self):
        """Test: Standard-Werte der globalen Konfiguration"""
        config = GlobalConfig()
        
        assert config.output_directory == "./downloads"
        assert config.nordvpn_enabled == True
        assert config.headless == False
        assert config.concurrent_downloads == 3
        assert len(config.user_agents) > 0
    
    def test_global_config_validation(self):
        """Test: Validierung der globalen Konfiguration"""
        with pytest.raises(ValidationError):
            GlobalConfig(concurrent_downloads=-1)  # Negative Werte nicht erlaubt


# ================================================================
# VPN MANAGER TESTS
# ================================================================

class TestVPNManager:
    """Tests für VPN-Manager"""
    
    def test_vpn_manager_disabled(self):
        """Test: VPN-Manager mit deaktiviertem VPN"""
        vpn = VPNManager(enabled=False)
        assert not vpn.enabled
        assert vpn.current_server is None
    
    @pytest.mark.asyncio
    async def test_vpn_connect_disabled(self):
        """Test: VPN-Verbindung bei deaktiviertem VPN"""
        vpn = VPNManager(enabled=False)
        result = await vpn.connect_to_random_server()
        assert result == True  # Sollte True zurückgeben auch wenn deaktiviert
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_vpn_connect_success(self, mock_subprocess):
        """Test: Erfolgreiche VPN-Verbindung"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stderr = ""
        
        vpn = VPNManager(enabled=True)
        result = await vpn.connect_to_random_server()
        
        assert result == True
        assert vpn.current_server is not None
        mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('subprocess.run')
    async def test_vpn_connect_failure(self, mock_subprocess):
        """Test: Fehlgeschlagene VPN-Verbindung"""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Connection failed"
        
        vpn = VPNManager(enabled=True)
        result = await vpn.connect_to_random_server()
        
        assert result == False
        assert vpn.current_server is None
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.get')
    async def test_get_current_ip(self, mock_get):
        """Test: Aktuelle IP-Adresse abrufen"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"origin": "192.168.1.1"}
        mock_get.return_value.__aenter__.return_value = mock_response
        
        vpn = VPNManager()
        ip = await vpn.get_current_ip()
        
        assert ip == "192.168.1.1"


# ================================================================
# HUMAN BEHAVIOR SIMULATOR TESTS
# ================================================================

class TestHumanBehaviorSimulator:
    """Tests für Human-Behavior-Simulator"""
    
    def test_human_behavior_init(self):
        """Test: Initialisierung des Simulators"""
        simulator = HumanBehaviorSimulator()
        assert simulator.logger is not None
    
    @pytest.mark.asyncio
    async def test_random_delay(self):
        """Test: Zufällige Verzögerung"""
        simulator = HumanBehaviorSimulator()
        
        import time
        start_time = time.time()
        await simulator.random_delay(0.1, 0.2)
        elapsed = time.time() - start_time
        
        assert 0.1 <= elapsed <= 0.3  # Etwas Toleranz für Timing
    
    @pytest.mark.asyncio
    async def test_human_click_element_not_found(self):
        """Test: Klick auf nicht existierendes Element"""
        simulator = HumanBehaviorSimulator()
        
        # Mock Page mit fehlschlagenem Selector
        mock_page = AsyncMock()
        mock_page.wait_for_selector.side_effect = Exception("Element not found")
        
        result = await simulator.human_click(mock_page, ".non-existent")
        assert result == False


# ================================================================
# VIDEO EXTRACTOR TESTS
# ================================================================

class TestVideoExtractor:
    """Tests für Video-Extraktor"""
    
    def test_video_extractor_init(self, temp_download_dir):
        """Test: Initialisierung des Video-Extraktors"""
        extractor = VideoExtractor(str(temp_download_dir))
        assert extractor.output_dir == temp_download_dir
        assert temp_download_dir.exists()
    
    def test_safe_filename_generation(self, temp_download_dir):
        """Test: Sichere Dateinamen-Generierung"""
        extractor = VideoExtractor(str(temp_download_dir))
        
        # Test mit Titel
        filename = extractor._get_safe_filename(
            "https://test-site.com/video", 
            "Test Video: Special/Characters!"
        )
        assert "test-site.com" in filename
        assert "Test-Video-Special-Characters" in filename
        
        # Test ohne Titel
        filename_no_title = extractor._get_safe_filename("https://example.com/page")
        assert "example.com" in filename_no_title
    
    @pytest.mark.asyncio
    @patch('yt_dlp.YoutubeDL')
    async def test_extract_video_info_success(self, mock_ytdl, temp_download_dir):
        """Test: Erfolgreiche Video-Info-Extraktion"""
        # Mock yt-dlp Response
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = {
            'title': 'Test Video',
            'duration': 120,
            'format_id': 'best',
            'height': 1080,
            'url': 'https://test.com/direct.mp4'
        }
        
        extractor = VideoExtractor(str(temp_download_dir))
        video_info = await extractor.extract_video_info("https://test.com/video")
        
        assert video_info is not None
        assert video_info.title == "Test Video"
        assert video_info.duration == 120
        assert video_info.quality == 1080
    
    @pytest.mark.asyncio
    @patch('yt_dlp.YoutubeDL')
    async def test_extract_video_info_failure(self, mock_ytdl, temp_download_dir):
        """Test: Fehlgeschlagene Video-Info-Extraktion"""
        mock_instance = mock_ytdl.return_value.__enter__.return_value
        mock_instance.extract_info.side_effect = Exception("Extraction failed")
        
        extractor = VideoExtractor(str(temp_download_dir))
        video_info = await extractor.extract_video_info("https://invalid.com/video")
        
        assert video_info is None


# ================================================================
# VIDEO ANALYZER TESTS
# ================================================================

class TestVideoAnalyzer:
    """Tests für Video-Analyzer"""
    
    def test_video_analyzer_init(self):
        """Test: Initialisierung des Analyzers"""
        analyzer = VideoAnalyzer()
        assert len(analyzer.video_extensions) > 0
        assert len(analyzer.streaming_domains) > 0
    
    def test_analyze_direct_video_url(self):
        """Test: Analyse einer direkten Video-URL"""
        analyzer = VideoAnalyzer()
        analysis = analyzer.analyze_url("https://example.com/video.mp4")
        
        assert analysis['is_direct_video'] == True
        assert analysis['estimated_complexity'] == 'low'
        assert analysis['suggested_method'] == 'direct_download'
    
    def test_analyze_streaming_platform(self):
        """Test: Analyse einer Streaming-Plattform"""
        analyzer = VideoAnalyzer()
        analysis = analyzer.analyze_url("https://youtube.com/watch?v=abc123")
        
        assert analysis['is_streaming_platform'] == True
        assert analysis['estimated_complexity'] == 'medium'
        assert analysis['suggested_method'] == 'yt_dlp'
    
    def test_analyze_unknown_site(self):
        """Test: Analyse einer unbekannten Site"""
        analyzer = VideoAnalyzer()
        analysis = analyzer.analyze_url("https://unknown-site.com/player/video")
        
        assert analysis['is_direct_video'] == False
        assert analysis['is_streaming_platform'] == False
        assert analysis['estimated_complexity'] == 'high'
        assert analysis['suggested_method'] == 'browser_automation'
    
    def test_batch_analyze(self, sample_urls):
        """Test: Batch-Analyse mehrerer URLs"""
        analyzer = VideoAnalyzer()
        analyses = analyzer.batch_analyze(sample_urls)
        
        assert len(analyses) == len(sample_urls)
        assert all('url' in analysis for analysis in analyses)
    
    def test_generate_analysis_report(self, sample_urls):
        """Test: Generierung des Analyse-Berichts"""
        analyzer = VideoAnalyzer()
        analyses = analyzer.batch_analyze(sample_urls)
        report = analyzer.generate_analysis_report(analyses)
        
        assert report['total_urls'] == len(sample_urls)
        assert 'success_probability' in report
        assert 0.0 <= report['success_probability'] <= 1.0
        assert 'complexity_distribution' in report
        assert 'method_distribution' in report


# ================================================================
# PERFORMANCE MONITOR TESTS
# ================================================================

class TestPerformanceMonitor:
    """Tests für Performance-Monitor"""
    
    def test_performance_monitor_init(self):
        """Test: Initialisierung des Performance-Monitors"""
        monitor = PerformanceMonitor()
        assert len(monitor.metrics_history) == 0
        assert monitor.start_time > 0
    
    def test_capture_metrics(self):
        """Test: Metriken-Erfassung"""
        monitor = PerformanceMonitor()
        metrics = monitor.capture_metrics(active_downloads=2)
        
        assert metrics.active_downloads == 2
        assert metrics.cpu_percent >= 0
        assert metrics.memory_mb >= 0
        assert len(monitor.metrics_history) == 1
    
    def test_metrics_history_limit(self):
        """Test: Begrenzung der Metriken-Historie"""
        monitor = PerformanceMonitor()
        
        # Simuliere > 1000 Metriken
        for i in range(1005):
            monitor.capture_metrics()
        
        assert len(monitor.metrics_history) == 1000  # Sollte auf 1000 begrenzt sein
    
    def test_export_metrics(self, temp_download_dir):
        """Test: Metriken-Export"""
        monitor = PerformanceMonitor()
        monitor.capture_metrics()
        
        export_file = temp_download_dir / "metrics.json"
        monitor.export_metrics(export_file)
        
        assert export_file.exists()
        
        # Validiere JSON-Struktur
        with open(export_file) as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert 'timestamp' in data[0]
        assert 'cpu_percent' in data[0]


# ================================================================
# ERROR RECOVERY TESTS
# ================================================================

class TestErrorRecovery:
    """Tests für Error-Recovery"""
    
    def test_error_recovery_init(self):
        """Test: Initialisierung der Fehlerbehandlung"""
        recovery = ErrorRecovery(max_retries=5)
        assert recovery.max_retries == 5
        assert len(recovery.error_patterns) > 0
    
    def test_categorize_network_error(self):
        """Test: Kategorisierung von Netzwerk-Fehlern"""
        recovery = ErrorRecovery()
        
        category = recovery.categorize_error("Connection timeout after 30 seconds")
        assert category == 'network_timeout'
        
        category = recovery.categorize_error("Rate limit exceeded")
        assert category == 'rate_limited'
        
        category = recovery.categorize_error("Access forbidden")
        assert category == 'access_denied'
    
    def test_suggest_recovery_action(self):
        """Test: Recovery-Aktions-Vorschläge"""
        recovery = ErrorRecovery()
        
        # Netzwerk-Timeout
        action = recovery.suggest_recovery_action('network_timeout', attempt=1)
        assert action['action'] == 'retry_with_delay'
        assert action['delay'] == 30
        
        # Rate Limiting
        action = recovery.suggest_recovery_action('rate_limited', attempt=2)
        assert action['action'] == 'retry_with_delay'
        assert action['delay'] == 120
        assert action['change_ip'] == True
        
        # Video nicht gefunden
        action = recovery.suggest_recovery_action('video_not_found', attempt=1)
        assert action['action'] == 'skip'
        assert action['retry'] == False


# ================================================================
# DOWNLOAD HISTORY TESTS
# ================================================================

class TestDownloadHistory:
    """Tests für Download-Historie"""
    
    def test_download_history_init(self, temp_download_dir):
        """Test: Initialisierung der Download-Historie"""
        db_path = temp_download_dir / "test_history.db"
        history = DownloadHistory(str(db_path))
        
        assert history.db_path == db_path
        assert db_path.exists()
    
    def test_add_download_success(self, temp_download_dir):
        """Test: Erfolgreichen Download zur Historie hinzufügen"""
        db_path = temp_download_dir / "test_history.db"
        history = DownloadHistory(str(db_path))
        
        history.add_download(
            url="https://test.com/video.mp4",
            success=True,
            title="Test Video",
            filesize=1024000,
            download_time=5.5
        )
        
        # Statistiken prüfen
        stats = history.get_download_stats(days=1)
        assert stats['total_downloads'] == 1
        assert stats['successful'] == 1
        assert stats['failed'] == 0
    
    def test_add_download_failure(self, temp_download_dir):
        """Test: Fehlgeschlagenen Download zur Historie hinzufügen"""
        db_path = temp_download_dir / "test_history.db"
        history = DownloadHistory(str(db_path))
        
        history.add_download(
            url="https://test.com/invalid.mp4",
            success=False,
            error_message="Video not found"
        )
        
        stats = history.get_download_stats(days=1)
        assert stats['total_downloads'] == 1
        assert stats['successful'] == 0
        assert stats['failed'] == 1


# ================================================================
# INTEGRATION TESTS
# ================================================================

class TestWebVideoDownloaderIntegration:
    """Integration-Tests für den Haupt-Downloader"""
    
    @pytest.mark.asyncio
    async def test_downloader_initialization(self, temp_config_file):
        """Test: Initialisierung des Downloaders"""
        downloader = WebVideoDownloader(temp_config_file)
        assert downloader.config is not None
        assert downloader.vpn_manager is not None
        assert downloader.video_extractor is not None
    
    @pytest.mark.asyncio
    async def test_downloader_context_manager(self, temp_config_file):
        """Test: Context Manager des Downloaders"""
        async with WebVideoDownloader(temp_config_file) as downloader:
            assert downloader.browser is not None
            assert downloader.playwright is not None
        
        # Nach Context Manager sollten Ressourcen bereinigt sein
        assert downloader.browser is None or downloader.browser.is_connected() == False
    
    @pytest.mark.asyncio
    @patch('video_downloader.WebVideoDownloader.process_single_url')
    async def test_download_multiple_urls(self, mock_process, temp_config_file, sample_urls):
        """Test: Download mehrerer URLs"""
        # Mock für erfolgreiche Downloads
        mock_process.return_value = DownloadResult(
            url="test_url",
            success=True,
            filepath=Path("test.mp4"),
            download_time=2.5
        )
        
        async with WebVideoDownloader(temp_config_file) as downloader:
            results = await downloader.download_multiple_urls(sample_urls[:2])
        
        assert len(results) == 2
        assert all(result.success for result in results)
        assert mock_process.call_count == 2


# ================================================================
# PERFORMANCE TESTS
# ================================================================

@pytest.mark.performance
class TestPerformance:
    """Performance-Tests"""
    
    def test_url_analysis_performance(self, sample_urls):
        """Test: Performance der URL-An
