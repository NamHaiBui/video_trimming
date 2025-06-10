# Multi-stage Docker build for Video Trimming Project
# Stage 1: Build stage with all dependencies
FROM python:3.11-slim as builder

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: FFmpeg installation
FROM python:3.11-slim as ffmpeg-stage

# Install FFmpeg and required system libraries
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ffprobe \
    && rm -rf /var/lib/apt/lists/*

# Verify FFmpeg installation
RUN ffmpeg -version && ffprobe -version

# Stage 3: Production image
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    FFMPEG_PATH="/usr/bin/ffmpeg" \
    FFPROBE_PATH="/usr/bin/ffprobe" \
    TEMP_DIR="/tmp/video_processing" \
    LOG_LEVEL="INFO"

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create necessary directories
RUN mkdir -p /app /app/src /app/logs /app/temp /app/output \
    && chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY .env.template ./

# Copy additional files
COPY requirements.txt Makefile pyproject.toml ./

# Make scripts executable
RUN chmod +x scripts/*.sh scripts/*.py

# Create .env file from template
RUN cp .env.template .env

# Change ownership to app user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.utils.config import get_ffmpeg_path; get_ffmpeg_path()" || exit 1

# Default command
CMD ["python", "src/main.py"]

# Development stage
FROM production as development

# Switch back to root for development dependencies
USER root

# Install development dependencies
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Install additional development tools
RUN apt-get update && apt-get install -y \
    git \
    vim \
    curl \
    wget \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Copy test files
COPY tests/ ./tests/

# Switch back to app user
USER appuser

# Development command
CMD ["bash"]
