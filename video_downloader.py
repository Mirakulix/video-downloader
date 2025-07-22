# video_downloader.py
"""
Advanced Web Video Downloader with VPN Integration
Entwickelt für den sicheren Download von Videos mit NordVPN IP-Rotation
"""

import asyncio
import json
import logging
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
from urllib.parse import urljoin, urlparse

import aiohttp
import yt_dlp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page, Playwright
from pydantic import BaseModel, Field, validator


# ============================
# CONFIGURATION MODELS
# ============================

class SiteConfig(BaseModel):
    """Konfiguration für spezifische Websites"""
    
    video_button: List[str] = Field(default_factory=list, description="CSS-Selektoren für Video-Buttons")
    download_link: List[str] = Field(default_factory=list, description="CSS-Selektoren für Download-Links")
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    login_url: Optional[str] = None
    login_username_field: str = "input[name='username'], input[type='email']"
    login_password_field: str = "input[name='password'], input[type='password']"
    login_submit_button: str = "button[type='submit'], input[type='submit']"
    wait_after_login: int = 3
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    human_delay_min: float = 1.0
    human_delay_max: float = 3.0

    @validator('video_button', 'download_link', pre=True)
    def convert_strings_to_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v


class GlobalConfig(BaseModel):
    """Globale Konfiguration für den Downloader"""
    
    sites: Dict[str, SiteConfig] = Field(default_factory=dict)
    output_directory: str = "./downloads"
    nordvpn_enabled: bool = True
    ip_rotation_interval_min: int = 300  # 5 Minuten
    ip_rotation_interval_max: int = 1800  # 30 Minuten
    user_agents: List[str] = Field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ])
    headless: bool = False
    timeout: int = 30
    concurrent_downloads: int = 3
    retry_attempts: int = 3
    log_level: str = "INFO"


# ============================
# DATA CLASSES
# ============================

@dataclass
class VideoInfo:
    """Informationen über ein gefundenes Video"""
    
    url: str
    title: str = ""
    duration: Optional[int] = None
    format_id: Optional[str] = None
    filesize: Optional[int] = None
    quality: Optional[str] = None
    direct_url: Optional[str] = None


@dataclass
class DownloadResult:
    """Ergebnis eines Download-Vorgangs"""
    
    url: str
    success: bool
    filepath: Optional[Path] = None
    error: Optional[str] = None
    video_info: Optional[VideoInfo] = None
    download_time: Optional[float] = None


# ============================
# VPN MANAGER
# ============================

class VPNManager:
    """Manager für NordVPN-Verbindungen und IP-Rotation"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.current_server: Optional[str] = None
        self.last_rotation = datetime.now()
        self.logger = logging.getLogger(__name__ + ".VPNManager")
        
    async def connect_to_random_server(self) -> bool:
        """Verbindet zu einem zufälligen NordVPN-Server"""
        if not self.enabled:
            self.logger.info("VPN ist deaktiviert")
            return True
            
        try:
            # NordVPN Server-Liste abrufen
            countries = ["US", "DE", "GB", "NL", "SE", "CH", "FR", "CA"]
            country = random.choice(countries)
            
            # Verbindung herstellen
            cmd = f"nordvpn connect {country}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.current_server = country
                self.last_rotation = datetime.now()
                self.logger.info(f"VPN verbunden mit {country}")
                await asyncio.sleep(random.uniform(2, 5))  # Kurze Pause nach Verbindung
                return True
            else:
                self.logger.error(f"VPN-Verbindung fehlgeschlagen: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("VPN-Verbindung Timeout")
            return False
        except Exception as e:
            self.logger.error(f"VPN-Fehler: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Trennt die VPN-Verbindung"""
        if not self.enabled:
            return True
            
        try:
            result = subprocess.run("nordvpn disconnect", shell=True, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self.logger.info("VPN getrennt")
                return True
            return False
        except Exception as e:
            self.logger.error(f"VPN-Trennung fehlgeschlagen: {e}")
            return False
    
    async def rotate_if_needed(self, force: bool = False) -> bool:
        """Rotiert IP wenn nötig basierend auf Zeit-Intervall"""
        if not self.enabled:
            return True
            
        time_since_rotation = datetime.now() - self.last_rotation
        rotation_interval = timedelta(minutes=random.randint(300, 1800) / 60)  # 5-30 Min in zufälligen Intervallen
        
        if force or time_since_rotation > rotation_interval:
            self.logger.info(f"IP-Rotation nach {time_since_rotation}")
            await self.disconnect()
            await asyncio.sleep(random.uniform(1, 3))
            return await self.connect_to_random_server()
        
        return True
    
    async def get_current_ip(self) -> Optional[str]:
        """Ermittelt die aktuelle öffentliche IP-Adresse"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("https://httpbin.org/ip") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("origin")
        except Exception as e:
            self.logger.error(f"IP-Abfrage fehlgeschlagen: {e}")
        return None


# ============================
# HUMAN BEHAVIOR SIMULATOR
# ============================

class HumanBehaviorSimulator:
    """Simuliert menschliches Verhalten für realistisches Scraping"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".HumanBehavior")
    
    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Zufällige Verzögerung zwischen Aktionen"""
        delay = random.uniform(min_seconds, max_seconds)
        self.logger.debug(f"Zufällige Verzögerung: {delay:.2f}s")
        await asyncio.sleep(delay)
    
    async def simulate_reading(self, page: Page, min_time: float = 2.0, max_time: float = 8.0):
        """Simuliert das Lesen einer Seite"""
        reading_time = random.uniform(min_time, max_time)
        self.logger.debug(f"Simuliere Lesen für {reading_time:.2f}s")
        
        # Gelegentliches Scrollen während des "Lesens"
        scroll_times = random.randint(1, 3)
        for _ in range(scroll_times):
            await asyncio.sleep(reading_time / (scroll_times + 1))
            scroll_distance = random.randint(100, 500)
            await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
    
    async def simulate_mouse_movement(self, page: Page):
        """Simuliert natürliche Mausbewegungen"""
        # Zufällige Mausbewegung
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        await page.mouse.move(x, y)
        await self.random_delay(0.5, 1.5)
    
    async def human_click(self, page: Page, selector: str) -> bool:
        """Führt einen menschlich wirkenden Klick aus"""
        try:
            # Element finden
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                return False
            
            # Zu Element scrollen
            await element.scroll_into_view_if_needed()
            await self.random_delay(0.5, 1.0)
            
            # Hover vor Klick
            await element.hover()
            await self.random_delay(0.3, 0.8)
            
            # Klick
            await element.click()
            await self.random_delay(1.0, 2.0)
            
            return True
        except Exception as e:
            self.logger.error(f"Klick auf {selector} fehlgeschlagen: {e}")
            return False


# ============================
# VIDEO EXTRACTOR
# ============================

class VideoExtractor:
    """Extrahiert und downloadet Videos mit yt-dlp"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__ + ".VideoExtractor")
    
    def _get_safe_filename(self, url: str, title: str = "") -> str:
        """Erstellt einen sicheren Dateinamen basierend auf URL"""
        domain = urlparse(url).netloc.replace("www.", "")
        
        if title:
            # Bereinige Titel für Dateinamen
            safe_title = re.sub(r'[^\w\s-]', '', title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            filename = f"{domain}_{safe_title}"
        else:
            # Fallback auf URL-basierte Benennung
            filename = f"{domain}_{int(time.time())}"
        
        return filename[:100]  # Länge begrenzen
    
    async def extract_video_info(self, url: str) -> Optional[VideoInfo]:
        """Extrahiert Video-Informationen ohne Download"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                
                if info:
                    return VideoInfo(
                        url=url,
                        title=info.get('title', ''),
                        duration=info.get('duration'),
                        format_id=info.get('format_id'),
                        filesize=info.get('filesize'),
                        quality=info.get('height', 'unknown'),
                        direct_url=info.get('url')
                    )
        except Exception as e:
            self.logger.error(f"Video-Info-Extraktion fehlgeschlagen für {url}: {e}")
        
        return None
    
    async def download_video(self, url: str, custom_filename: str = None) -> DownloadResult:
        """Downloadet Video in bester verfügbarer Qualität"""
        start_time = time.time()
        
        try:
            # Video-Info extrahieren
            video_info = await self.extract_video_info(url)
            if not video_info:
                return DownloadResult(url=url, success=False, error="Keine Video-Informationen gefunden")
            
            # Dateiname bestimmen
            if custom_filename:
                filename = custom_filename
            else:
                filename = self._get_safe_filename(url, video_info.title)
            
            output_path = self.output_dir / f"{filename}.%(ext)s"
            
            # yt-dlp Konfiguration für beste Qualität
            ydl_opts = {
                'format': 'best[height<=1080]/best',  # Beste Qualität bis 1080p
                'outtmpl': str(output_path),
                'writeinfojson': True,  # Info-JSON speichern
                'writesubtitles': False,
                'ignoreerrors': True,
                'no_warnings': True,
                'extractaudio': False,
                'keepvideo': True,
            }
            
            # Download ausführen
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.download([url])
                )
            
            # Erfolgreich heruntergeladene Datei finden
            downloaded_files = list(self.output_dir.glob(f"{filename}.*"))
            video_files = [f for f in downloaded_files if f.suffix in ['.mp4', '.mkv', '.webm', '.avi']]
            
            if video_files:
                download_time = time.time() - start_time
                self.logger.info(f"Video erfolgreich heruntergeladen: {video_files[0]}")
                
                return DownloadResult(
                    url=url,
                    success=True,
                    filepath=video_files[0],
                    video_info=video_info,
                    download_time=download_time
                )
            else:
                return DownloadResult(url=url, success=False, error="Download-Datei nicht gefunden")
                
        except Exception as e:
            error_msg = f"Download fehlgeschlagen: {e}"
            self.logger.error(error_msg)
            return DownloadResult(url=url, success=False, error=error_msg)


# ============================
# MAIN DOWNLOADER CLASS
# ============================

class WebVideoDownloader:
    """Hauptklasse für den Web Video Downloader"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.vpn_manager = VPNManager(enabled=self.config.nordvpn_enabled)
        self.video_extractor = VideoExtractor(self.config.output_directory)
        self.human_behavior = HumanBehaviorSimulator()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.session_cookies: Dict[str, List] = {}
        
        # Logging konfigurieren
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Statistiken
        self.stats = {
            'processed_urls': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_time': 0.0
        }
    
    def _load_config(self) -> GlobalConfig:
        """Lädt Konfiguration aus JSON-Datei"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return GlobalConfig(**config_data)
        else:
            # Standard-Konfiguration erstellen
            default_config = GlobalConfig()
            self._save_config(default_config)
            return default_config
    
    def _save_config(self, config: GlobalConfig):
        """Speichert Konfiguration in JSON-Datei"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config.dict(), f, indent=2, ensure_ascii=False)
    
    def _setup_logging(self):
        """Konfiguriert das Logging-System"""
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format=log_format,
            handlers=[
                logging.FileHandler('video_downloader.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    async def __aenter__(self):
        """Async Context Manager Entry"""
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async Context Manager Exit"""
        await self.cleanup()
    
    async def start_browser(self):
        """Startet Playwright Browser"""
        self.playwright = await async_playwright().start()
        
        # Browser-Konfiguration
        browser_args = [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-images',  # Für bessere Performance
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=browser_args
        )
        
        self.logger.info("Browser gestartet")
    
    async def cleanup(self):
        """Bereinigt Ressourcen"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        await self.vpn_manager.disconnect()
        
        self.logger.info("Cleanup abgeschlossen")
    
    def _get_site_config(self, url: str) -> Optional[SiteConfig]:
        """Ermittelt Site-Konfiguration für URL"""
        domain = urlparse(url).netloc.replace("www.", "")
        return self.config.sites.get(domain)
    
    async def _create_page(self) -> Page:
        """Erstellt neue Browser-Seite mit zufälligem User-Agent"""
        user_agent = random.choice(self.config.user_agents)
        
        context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            java_script_enabled=True,
            ignore_https_errors=True
        )
        
        page = await context.new_page()
        
        # Erweiterte Stealth-Konfiguration
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        
        return page
    
    async def _handle_login(self, page: Page, site_config: SiteConfig) -> bool:
        """Führt automatisches Login durch wenn konfiguriert"""
        if not (site_config.login_username and site_config.login_password):
            return True
        
        try:
            login_url = site_config.login_url or page.url
            if page.url != login_url:
                await page.goto(login_url)
                await self.human_behavior.random_delay()
            
            # Username eingeben
            await page.fill(site_config.login_username_field, site_config.login_username)
            await self.human_behavior.random_delay(0.5, 1.0)
            
            # Password eingeben
            await page.fill(site_config.login_password_field, site_config.login_password)
            await self.human_behavior.random_delay(0.5, 1.0)
            
            # Login-Button klicken
            await self.human_behavior.human_click(page, site_config.login_submit_button)
            
            # Warten nach Login
            await asyncio.sleep(site_config.wait_after_login)
            
            self.logger.info(f"Login erfolgreich für {urlparse(page.url).netloc}")
            return True
            
        except Exception as e:
            self.logger.error(f"Login fehlgeschlagen: {e}")
            return False
    
    async def _analyze_page_for_videos(self, page: Page) -> Set[str]:
        """Analysiert Seite nach Video-URLs"""
        video_urls = set()
        
        try:
            # JavaScript ausführen um Video-Elemente zu finden
            video_elements = await page.evaluate("""
                () => {
                    const videos = [];
                    
                    // Video-Tags finden
                    document.querySelectorAll('video').forEach(video => {
             
