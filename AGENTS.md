# AGENTS.md - Guidelines for AI Agents

This file provides guidance for AI agents working in this video-downloader repository.

## Project Overview

Async Python application for downloading videos from websites. Uses Playwright for browser automation, yt-dlp for video extraction, and optionally integrates NordVPN for IP rotation. CLI built with Click, configuration via Pydantic models, download history tracked in SQLite.

**Key modules (all in project root, no package directory):**
- `video_downloader.py` - Main engine with WebVideoDownloader, VPNManager, VideoExtractor, HumanBehaviorSimulator
- `cli.py` - Click command group with download, config, analyze, stats, doctor, cleanup subcommands
- `utilities.py` - PerformanceMonitor, DownloadHistory, VideoAnalyzer, ErrorRecovery, RichDisplay
- `setup.py` - Package setup with entry points
- `tests/test_video_downloader.py` - Comprehensive test suite

---

## Build/Lint/Test Commands

### Testing (via venv)
```bash
source venv/bin/activate

# All tests with coverage (minimum 80% threshold)
pytest

# Single test
pytest tests/test_video_downloader.py::TestClassName::test_name

# By marker
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m "not slow"        # Skip slow tests

# Specific directories
pytest tests/unit/ -v
pytest tests/integration/ -v
```

### Code Quality
```bash
make lint      # All linting (flake8, mypy, black --check)
make format    # Auto-format (black + isort)
make security  # Security scanning (bandit + safety)
```

### Development
```bash
make setup              # Full dev environment (venv, deps, playwright, config, hooks)
make test               # Run tests with pytest
make test-unit          # Run unit tests only
make test-integration   # Run integration tests only
make cli-doctor         # Run system diagnostics
make cli-config         # Show current configuration
```

---

## Code Style Guidelines

### Formatting
- **Line length**: Max 100 characters
- **Formatter**: Use `black` (line-length=100)
- **Import sorting**: Use `isort`
- **Run both**: `make format`

### Imports
- Standard library first
- Third-party packages second
- Local imports last
- Use isort to organize automatically

### Type Hints
- Use type hints for all function parameters and return values
- Use `Optional[X]` instead of `X | None` for Python 3.9 compatibility
- Use `List`, `Dict`, `Set` from typing module (not built-ins)

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `WebVideoDownloader`, `VPNManager`)
- **Functions/methods**: `snake_case` (e.g., `connect_to_random_server`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: prefix with `_`
- **Async functions**: prefix with `async_` or use `async def`

### Pydantic Models
- Use `BaseModel` with `Field` for validation
- Use `@validator` for custom validation
- Use `default_factory` for mutable defaults
- Convert single strings to lists with validators

### Error Handling
- Use try/except with specific exceptions
- Log errors with structlog
- Return meaningful error messages
- Use `Optional` for nullable return values

### Async Code
- Use `asyncio` throughout
- Use `async with` for context managers
- Use `AsyncMock` for async test mocking
- Decorate async tests with `@pytest.mark.asyncio`

### Testing Patterns
- Use `pytest` with fixtures
- Use `@pytest.fixture` for setup
- Use markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.asyncio`
- Use `AsyncMock`, `MagicMock`, `patch` for isolation
- Create temp directories/files with `tempfile` module

---

## Configuration

- **Config file**: `config.json` with Pydantic validation
- **Environment**: Use `.env` for sensitive data (never commit)
- **Defaults**: Use Pydantic `Field(default=...)` for defaults

---

## CLI Development

- Use Click with `@click.group()`, `@click.command()`, `@click.option()`
- Use `pass_context` decorator for shared context
- Use Rich for terminal output (tables, panels, progress bars)
- Use structlog for structured logging

---

## Dependencies (already used in project)

- `playwright` - Browser automation
- `yt-dlp` - Video extraction
- `pydantic` - Config validation
- `click` - CLI framework
- `structlog` - Structured logging
- `rich` - Terminal output
- `aiohttp` - Async HTTP
- `bs4` (BeautifulSoup) - HTML parsing
- `psutil` - System monitoring
- `pytest` - Testing
- `pytest-asyncio` - Async test support

---

## Important Notes

- All I/O is async (asyncio throughout)
- Config loaded from `config.json` with per-site selectors
- Credentials managed via `.env` files (never in code)
- VPN integration uses NordVPN CLI
- Uses SQLite for download history
