.PHONY: help setup test lint format clean up down logs build

.DEFAULT_GOAL := help

VENV := venv
COMPOSE := docker compose -f docker-compose.yml

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create venv and install all dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/playwright install chromium
	mkdir -p downloads logs

test: ## Run tests with coverage
	$(VENV)/bin/pytest tests/ -v --cov=. --cov-report=term

lint: ## Run linting checks (flake8, mypy, black)
	$(VENV)/bin/flake8 *.py tests/ --max-line-length=100
	$(VENV)/bin/mypy *.py --ignore-missing-imports
	$(VENV)/bin/black --check *.py tests/

format: ## Auto-format code (black + isort)
	$(VENV)/bin/black *.py tests/
	$(VENV)/bin/isort *.py tests/

clean: ## Remove temporary files and caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/ htmlcov/

up: ## Start all services (docker compose)
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

build: ## Build and start all services
	$(COMPOSE) up --build -d

logs: ## Show service logs
	$(COMPOSE) logs -f
