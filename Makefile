# ================================================================
# Web Video Downloader - Makefile für DevOps Automation
# ================================================================

.PHONY: help setup install test lint format clean build docker run stop logs shell

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip3
DOCKER_IMAGE := video-downloader
DOCKER_TAG := latest
COMPOSE_FILE := docker-compose.yml
VENV_DIR := venv

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## 📋 Show this help message
	@echo "$(GREEN)🎥 Web Video Downloader - DevOps Commands$(NC)"
	@echo "================================================"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(BLUE)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ================================================================
# Development Setup
# ================================================================

setup: ## 🚀 Complete development setup
	@echo "$(GREEN)🔧 Setting up development environment...$(NC)"
	$(MAKE) create-venv
	$(MAKE) install-deps
	$(MAKE) install-playwright
	$(MAKE) setup-config
	$(MAKE) setup-hooks
	@echo "$(GREEN)✅ Setup complete!$(NC)"

create-venv: ## 📦 Create Python virtual environment
	@echo "$(BLUE)📦 Creating virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "$(GREEN)✅ Virtual environment created$(NC)"
	@echo "$(YELLOW)💡 Activate with: source $(VENV_DIR)/bin/activate$(NC)"

install-deps: ## 📚 Install Python dependencies
	@echo "$(BLUE)📚 Installing Python dependencies...$(NC)"
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt
	$(VENV_DIR)/bin/pip install -r requirements-dev.txt
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

install-playwright: ## 🎭 Install Playwright browsers
	@echo "$(BLUE)🎭 Installing Playwright browsers...$(NC)"
	$(VENV_DIR)/bin/playwright install chromium
	$(VENV_DIR)/bin/playwright install-deps chromium
	@echo "$(GREEN)✅ Playwright browsers installed$(NC)"

setup-config: ## ⚙️ Create configuration files
	@echo "$(BLUE)⚙️ Setting up configuration...$(NC)"
	@if [ ! -f config.json ]; then \
		$(VENV_DIR)/bin/python cli.py config --create-example; \
		echo "$(GREEN)✅ Example config created$(NC)"; \
	else \
		echo "$(YELLOW)⚠️ config.json already exists$(NC)"; \
	fi
	@mkdir -p downloads logs
	@echo "$(GREEN)✅ Configuration setup complete$(NC)"

setup-hooks: ## 🪝 Setup Git hooks
	@echo "$(BLUE)🪝 Setting up Git hooks...$(NC)"
	@echo '#!/bin/bash\nmake lint' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "$(GREEN)✅ Git hooks configured$(NC)"

# ================================================================
# Development Tools
# ================================================================

install: ## 📦 Install package in development mode
	$(VENV_DIR)/bin/pip install -e .

test: ## 🧪 Run tests with pytest
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	$(VENV_DIR)/bin/pytest tests/ -v --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)✅ Tests completed$(NC)"

test-unit: ## 🔬 Run unit tests only
	@echo "$(BLUE)🔬 Running unit tests...$(NC)"
	$(VENV_DIR)/bin/pytest tests/unit/ -v

test-integration: ## 🔗 Run integration tests only
	@echo "$(BLUE)🔗 Running integration tests...$(NC)"
	$(VENV_DIR)/bin/pytest tests/integration/ -v

test-watch: ## 👀 Run tests in watch mode
	@echo "$(BLUE)👀 Running tests in watch mode...$(NC)"
	$(VENV_DIR)/bin/ptw tests/ --runner "pytest -v"

lint: ## 🔍 Run linting checks
	@echo "$(BLUE)🔍 Running linting checks...$(NC)"
	$(VENV_DIR)/bin/flake8 *.py tests/ --max-line-length=100
	$(VENV_DIR)/bin/mypy *.py --ignore-missing-imports
	$(VENV_DIR)/bin/black --check *.py tests/
	@echo "$(GREEN)✅ Linting completed$(NC)"

format: ## 🎨 Format code with black
	@echo "$(BLUE)🎨 Formatting code...$(NC)"
	$(VENV_DIR)/bin/black *.py tests/
	$(VENV_DIR)/bin/isort *.py tests/
	@echo "$(GREEN)✅ Code formatted$(NC)"

security: ## 🔒 Run security checks
	@echo "$(BLUE)🔒 Running security checks...$(NC)"
	$(VENV_DIR)/bin/bandit -r . -x tests/
	$(VENV_DIR)/bin/safety check
	@echo "$(GREEN)✅ Security checks completed$(NC)"

# ================================================================
# CLI Commands
# ================================================================

cli-help: ## ❓ Show CLI help
	$(VENV_DIR)/bin/python cli.py --help

cli-config: ## ⚙️ Show current configuration
	$(VENV_DIR)/bin/python cli.py config --show

cli-doctor: ## 🏥 Run system diagnostics
	$(VENV_DIR)/bin/python cli.py doctor

cli-stats: ## 📊 Show download statistics
	$(VENV_DIR)/bin/python cli.py stats

# ================================================================
# Docker Commands
# ================================================================

docker-build: ## 🐳 Build Docker image
	@echo "$(BLUE)🐳 Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "$(GREEN)✅ Docker image built$(NC)"

docker-build-dev: ## 🛠️ Build development Docker image
	@echo "$(BLUE)🛠️ Building development Docker image...$(NC)"
	docker build -f Dockerfile.dev -t $(DOCKER_IMAGE):dev .
	@echo "$(GREEN)✅ Development Docker image built$(NC)"

docker-run: ## ▶️ Run Docker container
	@echo "$(BLUE)▶️ Running Docker container...$(NC)"
	docker run -it --rm \
		-v $(PWD)/downloads:/app/downloads \
		-v $(PWD)/config.json:/app/config.json:ro \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

docker-shell: ## 🐚 Open shell in Docker container
	@echo "$(BLUE)🐚 Opening shell in Docker container...$(NC)"
	docker run -it --rm \
		-v $(PWD):/app \
		--entrypoint /bin/bash \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

# ================================================================
# Docker Compose Commands
# ================================================================

up: ## 🚀 Start all services with docker-compose
	@echo "$(BLUE)🚀 Starting services...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)✅ Services started$(NC)"

build: ## 🚀 Start all services with docker-compose
	@echo "$(BLUE)🚀 Starting services...$(NC)"
	docker compose -f $(COMPOSE_FILE) up --build -d


down: ## ⏹️ Stop all services
	@echo "$(BLUE)⏹️ Stopping services...$(NC)"
	docker compose -f $(COMPOSE_FILE) down
	@echo "$(GREEN)✅ Services stopped$(NC)"

restart: ## 🔄 Restart all services
	@echo "$(BLUE)🔄 Restarting services...$(NC)"
	$(MAKE) down
	$(MAKE) up

logs: ## 📋 Show service logs
	docker compose -f $(COMPOSE_FILE) logs -f

logs-downloader: ## 📋 Show downloader logs only
	docker compose -f $(COMPOSE_FILE) logs -f video-downloader

status: ## 📊 Show service status
	docker compose -f $(COMPOSE_FILE) ps

shell: ## 🐚 Open shell in running container
	docker compose -f $(COMPOSE_FILE) exec video-downloader /bin/bash

# ================================================================
# Monitoring & Debugging
# ================================================================

web-ui: ## 🌐 Start Web UI (http://localhost:8080)
	@echo "$(BLUE)🌐 Starting Web UI...$(NC)"
	docker compose -f $(COMPOSE_FILE) --profile ui up --build
	@echo "$(GREEN)✅ Web UI available at http://localhost:8080$(NC)"

web-ui-down: ## ⏹️ Stop Web UI
	docker compose -f $(COMPOSE_FILE) --profile ui down

monitor: ## 📈 Start monitoring stack
	@echo "$(BLUE)📈 Starting monitoring stack...$(NC)"
	docker compose -f $(COMPOSE_FILE) --profile monitoring up -d
	@echo "$(GREEN)✅ Monitoring available at http://localhost:3000$(NC)"

monitor-down: ## ⏹️ Stop monitoring stack
	docker compose -f $(COMPOSE_FILE) --profile monitoring down

performance: ## ⚡ Run performance tests
	@echo "$(BLUE)⚡ Running performance tests...$(NC)"
	$(VENV_DIR)/bin/python -m pytest tests/performance/ -v
	@echo "$(GREEN)✅ Performance tests completed$(NC)"

profile: ## 📊 Profile application performance
	@echo "$(BLUE)📊 Profiling application...$(NC)"
	$(VENV_DIR)/bin/python -m cProfile -o profile.stats example_usage.py
	$(VENV_DIR)/bin/python -c "import pstats; pstats.Stats('profile.stats').sort_stats('time').print_stats(20)"

# ================================================================
# Database & Cleanup
# ================================================================

db-reset: ## 🗄️ Reset download database
	@echo "$(BLUE)🗄️ Resetting database...$(NC)"
	$(VENV_DIR)/bin/python cli.py cleanup --days 0 --confirm
	@echo "$(GREEN)✅ Database reset$(NC)"

clean: ## 🧹 Clean temporary files
	@echo "$(BLUE)🧹 Cleaning temporary files...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	rm -f .temp_config.json
	rm -f profile.stats
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	@echo "$(GREEN)✅ Cleanup completed$(NC)"

clean-all: clean ## 🧹 Deep clean (including venv)
	@echo "$(BLUE)🧹 Deep cleaning...$(NC)"
	rm -rf $(VENV_DIR)/
	rm -rf downloads/*
	docker system prune -f
	@echo "$(GREEN)✅ Deep cleanup completed$(NC)"

# ================================================================
# Production Deployment
# ================================================================

deploy-check: ## ✅ Pre-deployment checks
	@echo "$(BLUE)✅ Running pre-deployment checks...$(NC)"
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) security
	$(MAKE) docker-build
	@echo "$(GREEN)✅ Deployment checks passed$(NC)"

backup: ## 💾 Backup configuration and data
	@echo "$(BLUE)💾 Creating backup...$(NC)"
	mkdir -p backups
	tar -czf backups/backup_$(shell date +%Y%m%d_%H%M%S).tar.gz \
		config.json downloads/ logs/ *.db 2>/dev/null || true
	@echo "$(GREEN)✅ Backup created$(NC)"

# ================================================================
# Development Shortcuts
# ================================================================

dev: ## 🛠️ Start development environment
	@echo "$(BLUE)🛠️ Starting development environment...$(NC)"
	$(MAKE) setup
	$(MAKE) cli-doctor
	@echo "$(GREEN)✅ Development environment ready$(NC)"
	@echo "$(YELLOW)💡 Run 'make cli-help' to see available commands$(NC)"

quick-test: ## ⚡ Quick test with example URLs
	@echo "$(BLUE)⚡ Running quick test...$(NC)"
	$(VENV_DIR)/bin/python cli.py analyze \
		"https://example.com/video1" \
		"https://example.com/video2" \
		--detailed

demo: ## 🎬 Run demo with example URLs
	@echo "$(BLUE)🎬 Running demo...$(NC)"
	$(VENV_DIR)/bin/python example_usage.py

# ================================================================
# CI/CD Helpers
# ================================================================

ci-test: ## 🤖 CI test pipeline
	@echo "$(BLUE)🤖 Running CI test pipeline...$(NC)"
	$(MAKE) install-deps
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) security
	@echo "$(GREEN)✅ CI pipeline completed$(NC)"

release-check: ## 🚀 Pre-release validation
	@echo "$(BLUE)🚀 Running release validation...$(NC)"
	$(MAKE) clean
	$(MAKE) setup
	$(MAKE) deploy-check
	$(MAKE) backup
	@echo "$(GREEN)✅ Release validation completed$(NC)"

# ================================================================
# Documentation
# ================================================================

docs: ## 📚 Generate documentation
	@echo "$(BLUE)📚 Generating documentation...$(NC)"
	$(VENV_DIR)/bin/python -m pydoc -w video_downloader utilities cli
	@echo "$(GREEN)✅ Documentation generated$(NC)"

# ================================================================
# System Information
# ================================================================

info: ## ℹ️ Show system information
	@echo "$(GREEN)🎥 Web Video Downloader - System Information$(NC)"
	@echo "=============================================="
	@echo "$(BLUE)Python Version:$(NC) $(shell $(PYTHON) --version)"
	@echo "$(BLUE)Docker Version:$(NC) $(shell docker --version 2>/dev/null || echo 'Not installed')"
	@echo "$(BLUE)Docker Compose:$(NC) $(shell docker-compose --version 2>/dev/null || echo 'Not installed')"
	@echo "$(BLUE)Git Version:$(NC) $(shell git --version 2>/dev/null || echo 'Not installed')"
	@echo "$(BLUE)Virtual Env:$(NC) $(if $(wildcard $(VENV_DIR)/bin/python),✅ Present,❌ Missing)"
	@echo "$(BLUE)Config File:$(NC) $(if $(wildcard config.json),✅ Present,❌ Missing)"
	@echo "$(BLUE)Downloads Dir:$(NC) $(if $(wildcard downloads/),✅ Present,❌ Missing)"
