"""
Web UI for Video Downloader
FastAPI backend with WebSocket live progress updates.
"""

import asyncio
import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

# Project modules are on PYTHONPATH
from utilities import DownloadHistory, PerformanceMonitor, VideoAnalyzer
from video_downloader import WebVideoDownloader

app = FastAPI(title="Video Downloader Web UI")
# In Docker the file is copied to /app/webui_app.py with templates at /app/templates/
# Locally (web-ui/app.py) templates are at web-ui/templates/
_app_dir = Path(__file__).parent
_templates_dir = _app_dir / "templates"
templates = Jinja2Templates(directory=_templates_dir)

# Shared state
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config/config.json")
DB_PATH = os.environ.get("DB_PATH", "/app/data/download_history.db")

history = DownloadHistory(db_path=DB_PATH)
analyzer = VideoAnalyzer()
monitor = PerformanceMonitor()

# Active downloads tracked by job_id
active_downloads: Dict[str, dict] = {}

# WebSocket connections
ws_connections: List[WebSocket] = []


# ---- Request/Response Models ----

class DownloadRequest(BaseModel):
    urls: List[str]

class AnalyzeRequest(BaseModel):
    urls: List[str]


# ---- WebSocket broadcast ----

async def broadcast(message: dict):
    """Send a JSON message to all connected WebSocket clients."""
    data = json.dumps(message, default=str)
    stale = []
    for ws in ws_connections:
        try:
            await ws.send_text(data)
        except Exception:
            stale.append(ws)
    for ws in stale:
        ws_connections.remove(ws)


# ---- Background download task ----

async def run_download(job_id: str, urls: List[str]):
    """Execute downloads and broadcast progress via WebSocket."""
    active_downloads[job_id] = {
        "id": job_id,
        "status": "running",
        "urls": urls,
        "total": len(urls),
        "completed": 0,
        "failed": 0,
        "current_url": None,
        "results": [],
        "started_at": datetime.now().isoformat(),
    }

    await broadcast({"type": "download_started", "job": active_downloads[job_id]})

    try:
        async with WebVideoDownloader(config_path=CONFIG_PATH) as downloader:
            for i, url in enumerate(urls):
                active_downloads[job_id]["current_url"] = url
                await broadcast({
                    "type": "download_progress",
                    "job_id": job_id,
                    "current": i + 1,
                    "total": len(urls),
                    "url": url,
                    "status": "downloading",
                })

                try:
                    result = await downloader.process_single_url(url)
                    success = result.success
                    error = result.error
                    filepath = str(result.filepath) if result.filepath else None

                    history.add_download(
                        url=url,
                        success=success,
                        title=result.video_info.title if result.video_info else None,
                        filepath=filepath,
                        filesize=result.video_info.filesize if result.video_info else None,
                        download_time=result.download_time,
                        error_message=error,
                    )
                except Exception as e:
                    success = False
                    error = str(e)
                    filepath = None
                    history.add_download(url=url, success=False, error_message=error)

                if success:
                    active_downloads[job_id]["completed"] += 1
                else:
                    active_downloads[job_id]["failed"] += 1

                active_downloads[job_id]["results"].append({
                    "url": url,
                    "success": success,
                    "error": error,
                    "filepath": filepath,
                })

                await broadcast({
                    "type": "download_progress",
                    "job_id": job_id,
                    "current": i + 1,
                    "total": len(urls),
                    "url": url,
                    "status": "done" if success else "error",
                    "error": error,
                })

    except Exception as e:
        active_downloads[job_id]["status"] = "error"
        active_downloads[job_id]["error"] = str(e)
        await broadcast({"type": "download_error", "job_id": job_id, "error": str(e)})
        return

    active_downloads[job_id]["status"] = "finished"
    active_downloads[job_id]["current_url"] = None
    await broadcast({"type": "download_finished", "job": active_downloads[job_id]})


# ---- Routes ----

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        return {"error": "No URLs provided"}

    job_id = str(uuid.uuid4())[:8]
    asyncio.create_task(run_download(job_id, urls))
    return {"job_id": job_id, "urls": urls, "count": len(urls)}


@app.get("/api/downloads")
async def get_downloads(limit: int = 50):
    """Return recent downloads from SQLite."""
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM downloads ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return {"downloads": [dict(r) for r in rows]}
    except Exception as e:
        return {"downloads": [], "error": str(e)}


@app.get("/api/stats")
async def get_stats(days: int = 30):
    return history.get_download_stats(days=days)


@app.post("/api/analyze")
async def analyze_urls(req: AnalyzeRequest):
    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        return {"error": "No URLs provided"}
    analyses = analyzer.batch_analyze(urls)
    report = analyzer.generate_analysis_report(analyses)
    return {"analyses": analyses, "report": report}


@app.get("/api/system")
async def system_metrics():
    metrics = monitor.capture_metrics(active_downloads=len(active_downloads))
    return {
        "cpu_percent": metrics.cpu_percent,
        "memory_mb": round(metrics.memory_mb, 1),
        "network_bytes_recv": metrics.network_bytes_recv,
        "network_bytes_sent": metrics.network_bytes_sent,
        "active_downloads": len(active_downloads),
        "uptime_seconds": round(metrics.timestamp.timestamp() - monitor.start_time, 1),
    }


@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": list(active_downloads.values())}


@app.websocket("/ws/progress")
async def websocket_progress(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)
    try:
        # Send current state on connect
        await ws.send_text(json.dumps({
            "type": "init",
            "jobs": list(active_downloads.values()),
        }, default=str))
        # Keep connection alive, listen for pings
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_connections:
            ws_connections.remove(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
