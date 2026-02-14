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
import shutil
import subprocess
import tempfile
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
    create_folders_from_tags: bool = False
    tag_folder_base: str = "./downloads"
    source_config_path: str = "video_source_config.json"
    videos_sources_path: str = "videos_sources.json"


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
    tags: List[str] = field(default_factory=list)
    performers: List[str] = field(default_factory=list)
    source_domain: str = ""
    categories: List[str] = field(default_factory=list)
    description: str = ""
    upload_date: Optional[str] = None
    thumbnail_url: Optional[str] = None


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
# METADATA EXTRACTOR
# ============================

class MetadataExtractor:
    """Extrahiert Metadaten (Tags, Darsteller, Titel) von Webseiten"""

    FALLBACK_TAG_SELECTORS = [
        "a.tag", ".tags a", ".tag-list a", ".tag-container a",
        "[class*='tag'] a", "meta[name='keywords']"
    ]
    FALLBACK_PERFORMER_SELECTORS = [
        ".performer a", ".performers a", ".actors a", ".actor a",
        ".performer-list a", "[class*='performer'] a", "[class*='actor'] a"
    ]
    FALLBACK_CATEGORY_SELECTORS = [
        ".category a", ".categories a", ".category-list a",
        "[class*='category'] a"
    ]
    FALLBACK_TITLE_SELECTORS = [
        "h1.video-title", "h1.title", "h1", "title"
    ]

    def __init__(self, source_config_path: str = "video_source_config.json"):
        self.logger = logging.getLogger(__name__ + ".MetadataExtractor")
        self.source_config = self._load_source_config(source_config_path)

    def _load_source_config(self, path: str) -> Dict:
        config_path = Path(path)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _get_site_selectors(self, domain: str) -> Dict:
        return self.source_config.get(domain, {})

    def _extract_text_list(self, soup: BeautifulSoup, selectors: List[str]) -> List[str]:
        results = []
        for selector in selectors:
            if selector.startswith("meta["):
                meta = soup.select_one(selector)
                if meta and meta.get("content"):
                    results.extend([t.strip() for t in meta["content"].split(",") if t.strip()])
            else:
                elements = soup.select(selector)
                for el in elements:
                    text = el.get_text(strip=True)
                    if text and text not in results:
                        results.append(text)
            if results:
                break
        return results

    def extract_from_html(self, html: str, domain: str) -> Dict:
        soup = BeautifulSoup(html, "html.parser")
        site_selectors = self._get_site_selectors(domain)

        # Title
        title_selectors = ([site_selectors["title_selector"]]
                           if "title_selector" in site_selectors
                           else self.FALLBACK_TITLE_SELECTORS)
        title = ""
        for sel in title_selectors:
            el = soup.select_one(sel)
            if el:
                title = el.get_text(strip=True)
                break

        # Tags
        tag_selectors = ([site_selectors["tags_selector"]]
                         if "tags_selector" in site_selectors
                         else self.FALLBACK_TAG_SELECTORS)
        tags = self._extract_text_list(soup, tag_selectors)

        # Performers
        perf_selectors = ([site_selectors["performers_selector"]]
                          if "performers_selector" in site_selectors
                          else self.FALLBACK_PERFORMER_SELECTORS)
        performers = self._extract_text_list(soup, perf_selectors)

        # Categories
        cat_selectors = ([site_selectors["categories_selector"]]
                         if "categories_selector" in site_selectors
                         else self.FALLBACK_CATEGORY_SELECTORS)
        categories = self._extract_text_list(soup, cat_selectors)

        # Download URLs
        download_urls = []
        dl_selectors = site_selectors.get("download_url_selectors", [])
        for sel in dl_selectors:
            for el in soup.select(sel):
                href = el.get("href")
                if href:
                    download_urls.append(href)

        return {
            "title": title,
            "tags": tags,
            "performers": performers,
            "categories": categories,
            "download_urls": download_urls,
        }

    def extract_from_ytdlp(self, info: Dict) -> Dict:
        return {
            "title": info.get("title", ""),
            "duration": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "thumbnail_url": info.get("thumbnail"),
            "description": info.get("description", ""),
            "tags": info.get("tags", []) or [],
            "categories": info.get("categories", []) or [],
            "direct_url": info.get("url"),
            "quality": info.get("height"),
            "format_id": info.get("format_id"),
            "filesize": info.get("filesize"),
        }

    def merge_metadata(self, html_meta: Dict, ytdlp_meta: Dict) -> Dict:
        merged = {}
        merged["title"] = html_meta.get("title") or ytdlp_meta.get("title", "")
        merged["tags"] = html_meta.get("tags") or ytdlp_meta.get("tags", [])
        merged["performers"] = html_meta.get("performers", [])
        merged["categories"] = html_meta.get("categories") or ytdlp_meta.get("categories", [])
        merged["description"] = ytdlp_meta.get("description", "")
        merged["upload_date"] = ytdlp_meta.get("upload_date")
        merged["thumbnail_url"] = ytdlp_meta.get("thumbnail_url")
        merged["download_urls"] = html_meta.get("download_urls", [])
        merged["direct_url"] = ytdlp_meta.get("direct_url")
        merged["quality"] = ytdlp_meta.get("quality")
        merged["format_id"] = ytdlp_meta.get("format_id")
        merged["filesize"] = ytdlp_meta.get("filesize")
        merged["duration"] = ytdlp_meta.get("duration")
        return merged


# ============================
# SMART FILENAME GENERATOR
# ============================

class SmartFilenameGenerator:
    """Generiert intelligente Dateinamen aus Metadaten"""

    MAX_LENGTH = 200

    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SmartFilenameGenerator")

    def _sanitize(self, text: str) -> str:
        safe = re.sub(r'[^\w\s-]', '', text).strip()
        safe = re.sub(r'[-\s]+', '-', safe)
        return safe

    def generate(self, title: str, tags: List[str], performers: List[str],
                 source_domain: str) -> str:
        sorted_tags = sorted(set(t.lower() for t in tags if t))
        sorted_performers = sorted(set(p.lower() for p in performers if p))

        tag_part = "-".join(self._sanitize(t) for t in sorted_tags) if sorted_tags else ""
        perf_part = "-".join(self._sanitize(p) for p in sorted_performers) if sorted_performers else ""
        title_part = self._sanitize(title) if title else ""
        source_part = self._sanitize(source_domain.replace("www.", "")) if source_domain else ""

        parts = [p for p in [tag_part, perf_part, title_part, source_part] if p]
        filename = "_".join(parts)

        if len(filename) > self.MAX_LENGTH:
            # Truncate: max 5 tags, 1 performer, drop source
            short_tags = sorted_tags[:5]
            short_perfs = sorted_performers[:1]
            tag_part = "-".join(self._sanitize(t) for t in short_tags)
            perf_part = "-".join(self._sanitize(p) for p in short_perfs) if short_perfs else ""
            parts = [p for p in [tag_part, perf_part, title_part] if p]
            filename = "_".join(parts)

        if len(filename) > self.MAX_LENGTH:
            filename = filename[:self.MAX_LENGTH]

        return filename or f"video_{int(time.time())}"


# ============================
# RESUMABLE DOWNLOADER
# ============================

class ResumableDownloader:
    """HTTP-Download mit Resume-Fähigkeit via Range-Header"""

    CHUNK_SIZE = 1024 * 1024  # 1MB
    MAX_RETRIES = 5

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__ + ".ResumableDownloader")

    async def download(self, url: str, filename: str,
                       headers: Optional[Dict[str, str]] = None) -> Optional[Path]:
        final_path = self.output_dir / filename
        part_path = self.output_dir / f"{filename}.part"

        existing_size = part_path.stat().st_size if part_path.exists() else 0
        request_headers = dict(headers or {})

        for attempt in range(self.MAX_RETRIES):
            try:
                if existing_size > 0:
                    request_headers["Range"] = f"bytes={existing_size}-"

                timeout = aiohttp.ClientTimeout(total=3600, connect=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=request_headers) as response:
                        if response.status == 416:
                            # Range not satisfiable - file already complete
                            if part_path.exists():
                                shutil.move(str(part_path), str(final_path))
                            return final_path

                        if response.status not in (200, 206):
                            self.logger.error(f"HTTP {response.status} for {url}")
                            return None

                        if response.status == 200:
                            existing_size = 0

                        mode = "ab" if response.status == 206 else "wb"
                        with open(part_path, mode) as f:
                            async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                                f.write(chunk)

                shutil.move(str(part_path), str(final_path))
                self.logger.info(f"Download complete: {final_path}")
                return final_path

            except Exception as e:
                wait = min(2 ** attempt, 60)
                self.logger.warning(f"Download attempt {attempt+1} failed: {e}, retry in {wait}s")
                existing_size = part_path.stat().st_size if part_path.exists() else 0
                await asyncio.sleep(wait)

        self.logger.error(f"Download failed after {self.MAX_RETRIES} retries: {url}")
        return None


# ============================
# METADATA WRITER
# ============================

class MetadataWriter:
    """Schreibt Metadaten in Videodateien via ffmpeg"""

    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".MetadataWriter")

    async def write_metadata(self, filepath: Path, title: str = "",
                             performers: Optional[List[str]] = None,
                             tags: Optional[List[str]] = None,
                             source_url: str = "") -> bool:
        if not filepath.exists():
            self.logger.error(f"File not found: {filepath}")
            return False

        metadata_args = []
        if title:
            metadata_args.extend(["-metadata", f"title={title}"])
        if performers:
            metadata_args.extend(["-metadata", f"artist={', '.join(performers)}"])
        if tags:
            metadata_args.extend(["-metadata", f"genre={', '.join(tags)}"])
        if source_url:
            metadata_args.extend(["-metadata", f"comment={source_url}"])

        if not metadata_args:
            return True

        temp_fd, temp_path = tempfile.mkstemp(suffix=filepath.suffix)
        os.close(temp_fd)

        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(filepath),
                "-c", "copy",
                *metadata_args,
                temp_path
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode == 0:
                shutil.move(temp_path, str(filepath))
                self.logger.info(f"Metadata written to {filepath}")
                return True
            else:
                self.logger.error(f"ffmpeg failed: {stderr.decode()[:200]}")
                return False
        except FileNotFoundError:
            self.logger.warning("ffmpeg not found, skipping metadata writing")
            return False
        except Exception as e:
            self.logger.error(f"Metadata writing failed: {e}")
            return False
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ============================
# TAG FOLDER ORGANIZER
# ============================

class TagFolderOrganizer:
    """Organisiert Videos in Tag-basierte Ordner"""

    def __init__(self, base_dir: str, enabled: bool = False):
        self.base_dir = Path(base_dir)
        self.enabled = enabled
        self.logger = logging.getLogger(__name__ + ".TagFolderOrganizer")

    def _get_existing_folders(self) -> List[str]:
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]

    def _find_collision_free_path(self, folder: Path, filename: str) -> Path:
        target = folder / filename
        if not target.exists():
            return target
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while target.exists():
            target = folder / f"{stem}_{counter}{suffix}"
            counter += 1
        return target

    def organize(self, filepath: Path, tags: List[str]) -> Optional[Path]:
        if not self.enabled or not tags:
            return None

        existing_folders = self._get_existing_folders()
        folder_map = {f.lower(): f for f in existing_folders}

        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in folder_map:
                target_folder = self.base_dir / folder_map[tag_lower]
                target_path = self._find_collision_free_path(target_folder, filepath.name)
                shutil.move(str(filepath), str(target_path))
                self.logger.info(f"Moved {filepath.name} to {target_folder}")
                return target_path

        return None


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

        # New pipeline components
        self.metadata_extractor = MetadataExtractor(self.config.source_config_path)
        self.filename_generator = SmartFilenameGenerator()
        self.resumable_downloader = ResumableDownloader(self.config.output_directory)
        self.metadata_writer = MetadataWriter()
        self.tag_organizer = TagFolderOrganizer(
            self.config.tag_folder_base,
            enabled=self.config.create_folders_from_tags
        )

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
            video_elements = await page.evaluate("""
                () => {
                    const videos = [];
                    document.querySelectorAll('video').forEach(video => {
                        if (video.src) videos.push(video.src);
                        video.querySelectorAll('source').forEach(source => {
                            if (source.src) videos.push(source.src);
                        });
                    });
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.href;
                        if (href && /\\.(mp4|mkv|webm|avi|mov)$/i.test(href)) {
                            videos.push(href);
                        }
                    });
                    return videos;
                }
            """)
            video_urls.update(video_elements)
        except Exception as e:
            self.logger.error(f"Video-Analyse fehlgeschlagen: {e}")

        return video_urls

    async def _get_page_html(self, page: Page) -> str:
        """Holt den HTML-Inhalt der aktuellen Seite"""
        try:
            return await page.content()
        except Exception as e:
            self.logger.error(f"HTML-Extraktion fehlgeschlagen: {e}")
            return ""

    async def _try_download_with_official_link(self, download_urls: List[str],
                                                filename: str,
                                                page_url: str) -> Optional[Path]:
        """Versucht Download über offizielle Download-Links"""
        for dl_url in download_urls:
            if not dl_url.startswith("http"):
                dl_url = urljoin(page_url, dl_url)
            ext = Path(urlparse(dl_url).path).suffix or ".mp4"
            result = await self.resumable_downloader.download(
                dl_url, f"{filename}{ext}"
            )
            if result:
                return result
        return None

    async def _try_download_with_ytdlp(self, url: str, filename: str) -> Optional[Path]:
        """Download via yt-dlp mit bestvideo+bestaudio merge"""
        try:
            output_path = Path(self.config.output_directory) / f"{filename}.%(ext)s"
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best[height<=1080]/best',
                'outtmpl': str(output_path),
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ydl.download([url])
                )

            output_dir = Path(self.config.output_directory)
            downloaded = list(output_dir.glob(f"{filename}.*"))
            video_files = [f for f in downloaded
                           if f.suffix in ['.mp4', '.mkv', '.webm', '.avi']]
            if video_files:
                return video_files[0]
        except Exception as e:
            self.logger.warning(f"yt-dlp download failed: {e}")
        return None

    async def _try_download_direct(self, direct_url: str,
                                    filename: str) -> Optional[Path]:
        """Download via direkte URL"""
        if not direct_url:
            return None
        ext = Path(urlparse(direct_url).path).suffix or ".mp4"
        return await self.resumable_downloader.download(
            direct_url, f"{filename}{ext}"
        )

    async def process_single_url(self, url: str) -> DownloadResult:
        """Verarbeitet eine einzelne URL durch die komplette Pipeline"""
        start_time = time.time()
        domain = urlparse(url).netloc.replace("www.", "")

        try:
            # 1. Seite laden und HTML holen
            page = await self._create_page()
            site_config = self._get_site_config(url)

            if site_config:
                await self._handle_login(page, site_config)

            await page.goto(url, timeout=self.config.timeout * 1000)
            await self.human_behavior.random_delay()
            html = await self._get_page_html(page)

            # 2. Metadaten extrahieren
            html_meta = self.metadata_extractor.extract_from_html(html, domain)

            # 3. yt-dlp Info extrahieren
            ytdlp_meta = {}
            try:
                ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )
                    if info:
                        ytdlp_meta = self.metadata_extractor.extract_from_ytdlp(info)
            except Exception:
                pass

            # 4. Merge metadata
            merged = self.metadata_extractor.merge_metadata(html_meta, ytdlp_meta)

            # 5. Build VideoInfo
            video_info = VideoInfo(
                url=url,
                title=merged.get("title", ""),
                duration=merged.get("duration"),
                format_id=merged.get("format_id"),
                filesize=merged.get("filesize"),
                quality=merged.get("quality"),
                direct_url=merged.get("direct_url"),
                tags=merged.get("tags", []),
                performers=merged.get("performers", []),
                source_domain=domain,
                categories=merged.get("categories", []),
                description=merged.get("description", ""),
                upload_date=merged.get("upload_date"),
                thumbnail_url=merged.get("thumbnail_url"),
            )

            # 6. Smart filename
            filename = self.filename_generator.generate(
                video_info.title, video_info.tags,
                video_info.performers, domain
            )

            # 7. Download-Strategie
            filepath = None

            # Strategy A: Official download links
            download_urls = merged.get("download_urls", [])
            if download_urls:
                filepath = await self._try_download_with_official_link(
                    download_urls, filename, url
                )

            # Strategy B: yt-dlp
            if not filepath:
                filepath = await self._try_download_with_ytdlp(url, filename)

            # Strategy C: Direct URL from metadata
            if not filepath and merged.get("direct_url"):
                filepath = await self._try_download_direct(
                    merged["direct_url"], filename
                )

            # Strategy D: Browser-based extraction
            if not filepath:
                video_urls = await self._analyze_page_for_videos(page)
                for vid_url in video_urls:
                    filepath = await self._try_download_direct(vid_url, filename)
                    if filepath:
                        break

            await page.context.close()

            if not filepath:
                self.stats['failed_downloads'] += 1
                return DownloadResult(
                    url=url, success=False,
                    error="Kein Download-Verfahren erfolgreich",
                    video_info=video_info
                )

            # 8. Write metadata to file
            await self.metadata_writer.write_metadata(
                filepath, video_info.title,
                video_info.performers, video_info.tags, url
            )

            # 9. Tag folder organization
            new_path = self.tag_organizer.organize(filepath, video_info.tags)
            if new_path:
                filepath = new_path

            download_time = time.time() - start_time
            self.stats['successful_downloads'] += 1
            self.stats['processed_urls'] += 1

            return DownloadResult(
                url=url, success=True,
                filepath=filepath,
                video_info=video_info,
                download_time=download_time
            )

        except Exception as e:
            self.stats['failed_downloads'] += 1
            self.stats['processed_urls'] += 1
            return DownloadResult(
                url=url, success=False,
                error=str(e),
                download_time=time.time() - start_time
            )

    async def download_multiple_urls(self, urls: List[str]) -> List[DownloadResult]:
        """Verarbeitet mehrere URLs sequenziell mit Delay"""
        results = []
        for i, url in enumerate(urls):
            self.logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
            result = await self.process_single_url(url)
            results.append(result)

            if i < len(urls) - 1:
                delay = random.uniform(2.0, 5.0)
                self.logger.info(f"Delay {delay:.1f}s before next URL")
                await asyncio.sleep(delay)

        return results
             
