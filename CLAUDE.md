# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Async Python application for downloading videos from websites. Uses Playwright for browser automation, yt-dlp for video extraction, and optionally integrates NordVPN for IP rotation. CLI built with Click, configuration via Pydantic models, download history tracked in SQLite.

## Common Commands

```bash
# Setup
make setup                  # Full dev environment (venv, deps, playwright, config, hooks)
source venv/bin/activate    # Activate virtualenv

# Testing
pytest                      # Run all tests with coverage (80% minimum threshold)
pytest tests/test_video_downloader.py::TestClassName::test_name  # Single test
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m "not slow"        # Skip slow tests

# Code quality
make lint                   # All linting (black, isort, flake8, mypy, radon, vulture)
make format                 # Auto-format (black + isort)
make security               # Security scanning (bandit + safety)

# Docker
make docker-build           # Build image
make docker-up              # Start all services (app, postgres, redis, monitoring)
make docker-down            # Stop services
```

## Architecture

**Core modules (all in project root, no package directory):**

- **`video_downloader.py`** — Main engine. Key classes: `WebVideoDownloader` (async context manager, orchestrates browser + downloads), `VPNManager` (NordVPN control + IP rotation), `VideoExtractor` (yt-dlp wrapper), `HumanBehaviorSimulator` (anti-detection delays/scrolling). Config models: `SiteConfig`, `GlobalConfig` (Pydantic).
- **`cli.py`** — Click command group with subcommands: `download`, `config`, `analyze`, `stats`, `doctor`, `cleanup`. Uses structlog + Rich for output.
- **`utilities.py`** — `PerformanceMonitor` (CPU/memory/network tracking), `DownloadHistory` (SQLite via SQLAlchemy), `VideoAnalyzer` (URL analysis), `ErrorRecovery` (retry strategies), `RichDisplay` (terminal helpers).
- **`setup.py`** — Package setup with entry points.
- **`example_usage.py`** — Demo/examples for all features.

**Key patterns:**
- All I/O is async (asyncio throughout)
- Playwright handles browser-heavy sites; yt-dlp handles direct extraction
- Config loaded from `config.json` with per-site selectors, login configs, and global settings
- Credentials managed via `.env` files (never in code)

## Testing

- Tests in `tests/test_video_downloader.py`
- pytest with `asyncio_mode = auto` — async tests work without explicit decorators
- Heavy use of `AsyncMock`, `MagicMock`, `patch` for isolation
- Markers: `unit`, `integration`, `performance`, `security`, `e2e`, `slow`, `network`, `docker`, `vpn`, `browser`, `cli`, `smoke`
- Coverage targets: `video_downloader`, `utilities`, `cli` modules

## CI/CD

GitHub Actions pipeline runs: lint → test (matrix: Python 3.9-3.12, Ubuntu/macOS/Windows) → security → Docker build → integration tests. Coverage uploaded to Codecov. Docker images scanned with Trivy.

## Configuration

`config.json` holds site-specific selectors and global settings (output dir, VPN toggle, timeouts, concurrency limits, retry attempts). Pydantic validates all config at load time.
