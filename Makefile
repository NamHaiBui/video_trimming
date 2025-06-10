# Makefile for Video Trimming Project
# Common development tasks and project management

.PHONY: help install install-dev test test-unit test-integration test-slow test-localstack lint format type-check security-check clean setup run docker-build docker-run docker-up docker-down localstack-setup localstack-test

# Default target
help:
	@echo "Available targets:"
	@echo "  setup           - Complete project setup (install dependencies, FFmpeg, etc.)"
	@echo "  install         - Install production dependencies"
	@echo "  install-dev     - Install development dependencies"
	@echo "  test            - Run all tests"
	@echo "  test-unit       - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-slow       - Run slow tests"
	@echo "  lint            - Run linting checks"
	@echo "  format          - Format code with black and isort"
	@echo "  type-check      - Run type checking with mypy"
	@echo "  security-check  - Run security checks"
	@echo "  clean           - Clean up temporary files"
	@echo "  run             - Run the main application"
	@echo "  docker-build    - Build Docker image"
	@echo "  test-localstack - Run LocalStack integration tests"
	@echo "  localstack-setup - Setup LocalStack services"
	@echo "  localstack-test - Test LocalStack connectivity"
	@echo "  docker-up       - Start all services with docker-compose"
	@echo "  docker-down     - Stop all services"
	@echo "  docs            - Generate documentation"

# Project setup
setup:
	@echo "Setting up project..."
	./scripts/setup_project.sh

# Dependencies
install:
	@echo "Installing production dependencies..."
	pip install -r requirements.txt

install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt

# Testing
test:
	@echo "Running all tests..."
	python -m pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	python -m pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	python -m pytest tests/integration/ -v

test-slow:
	@echo "Running slow tests..."
	python -m pytest tests/ -v -m slow

test-localstack:
	@echo "Running LocalStack integration tests..."
	python -m pytest tests/integration/test_localstack.py -v -m localstack

test-coverage:
	@echo "Running tests with coverage..."
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Code quality
lint:
	@echo "Running linting checks..."
	flake8 src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/

format:
	@echo "Formatting code..."
	black src/ tests/
	isort src/ tests/

type-check:
	@echo "Running type checks..."
	mypy src/

security-check:
	@echo "Running security checks..."
	bandit -r src/
	safety check

# Pre-commit hooks
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	pre-commit install

pre-commit-run:
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files

# Application
run:
	@echo "Running application..."
	python src/main.py '{"id": "test-episode", "force_summarization": true, "force_audio_chunking": true, "force_audio_quote_extraction": true}'

run-sample:
	@echo "Running with sample data..."
	python src/main.py '{"id": "sample-episode-123", "force_summarization": false, "force_audio_chunking": false, "force_audio_quote_extraction": false}'

# FFmpeg
ffmpeg-check:
	@echo "Checking FFmpeg installation..."
	./scripts/setup_ffmpeg.sh --check

ffmpeg-install:
	@echo "Installing FFmpeg..."
	./scripts/setup_ffmpeg.sh --install

ffmpeg-test:
	@echo "Testing FFmpeg functionality..."
	python scripts/test_ffmpeg.py

# Docker
docker-build:
	@echo "Building Docker image..."
	docker build -t video-trimming:latest .

docker-run:
	@echo "Running Docker container..."
	docker run --rm -it \
		-v $(PWD)/sample:/app/sample \
		-v $(PWD)/output:/app/output \
		-e LOG_LEVEL=INFO \
		video-trimming:latest

docker-up:
	@echo "Starting all services with docker-compose..."
	docker-compose up -d

docker-down:
	@echo "Stopping all services..."
	docker-compose down

docker-logs:
	@echo "Showing docker-compose logs..."
	docker-compose logs -f

# LocalStack
localstack-setup:
	@echo "Setting up LocalStack services..."
	python scripts/setup_localstack.py

localstack-test:
	@echo "Testing LocalStack connectivity..."
	python scripts/test_localstack_connectivity.py

localstack-restart:
	@echo "Restarting LocalStack..."
	docker-compose restart localstack

# Documentation
docs:
	@echo "Generating documentation..."
	sphinx-build -b html docs/ docs/_build/html

docs-serve:
	@echo "Serving documentation..."
	cd docs/_build/html && python -m http.server 8000

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf temp/
	rm -rf logs/*.log

clean-all: clean
	@echo "Deep cleaning..."
	rm -rf venv/
	rm -rf .env

# Development environment
dev-shell:
	@echo "Starting development shell..."
	@echo "Virtual environment activated. Type 'exit' to quit."
	bash --rcfile <(echo '. ~/.bashrc; source venv/bin/activate; echo "Development environment ready!"')

# Environment management
env-create:
	@echo "Creating .env file from template..."
	cp .env.template .env
	@echo "Please edit .env file with your configuration values"

env-check:
	@echo "Checking environment configuration..."
	python -c "import os; from src.utils.config import *; print('Environment configuration looks good!')"

# Monitoring and profiling
profile:
	@echo "Profiling application..."
	python -m cProfile -o profile.stats src/main.py '{"id": "test-episode", "force_summarization": true}'
	python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# CI/CD helpers
ci-test:
	@echo "Running CI tests..."
	python -m pytest tests/ -x -v --tb=short

ci-build:
	@echo "Running CI build..."
	$(MAKE) install-dev
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) security-check
	$(MAKE) test

# Database management (for local development)
db-setup:
	@echo "Setting up local DynamoDB..."
	# Add DynamoDB local setup commands here

db-clean:
	@echo "Cleaning local database..."
	# Add database cleanup commands here

# Utilities
count-lines:
	@echo "Counting lines of code..."
	find src/ -name "*.py" -type f -exec wc -l {} + | tail -1

check-deps:
	@echo "Checking for outdated dependencies..."
	pip list --outdated

update-deps:
	@echo "Updating dependencies..."
	pip-compile requirements.in
	pip-compile requirements-dev.in

# Help for specific targets
install-help:
	@echo "Installation targets:"
	@echo "  install     - Install production dependencies only"
	@echo "  install-dev - Install both production and development dependencies"
	@echo "  setup       - Complete project setup including FFmpeg"

test-help:
	@echo "Testing targets:"
	@echo "  test            - Run all tests"
	@echo "  test-unit       - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-slow       - Run slow/long-running tests"
	@echo "  test-coverage   - Run tests with coverage report"
