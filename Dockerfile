# Multi-stage build for Python video processing application
FROM python:3.12-slim-bookworm AS builder

# Install system dependencies required for building
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim-bookworm

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    # Update CA certificates to latest
    && update-ca-certificates \
    # Ensure SSL certificate bundles are properly linked
    && ln -sf /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-bundle.crt \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user and directory
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /app /tmp/video_processing /app/logs /app/output
RUN chown -R appuser:appuser /app /tmp/video_processing

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY *.py ./

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables for SSL configuration
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV TEMP_DIR=/tmp/video_processing
ENV FFMPEG_PATH=/usr/bin/ffmpeg
ENV FFPROBE_PATH=/usr/bin/ffprobe

# SSL Configuration - Set certificate bundle paths
ENV SSL_CERT_FILE=/opt/venv/lib/python3.12/site-packages/certifi/cacert.pem
ENV SSL_CERT_DIR=/opt/venv/lib/python3.12/site-packages/certifi
ENV REQUESTS_CA_BUNDLE=/opt/venv/lib/python3.12/site-packages/certifi/cacert.pem
ENV CURL_CA_BUNDLE=/opt/venv/lib/python3.12/site-packages/certifi/cacert.pem
ENV PYTHONHTTPSVERIFY=1

# Health check with SSL validation
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import boto3, ssl, certifi; from src.utils.aws_clients import configure_ssl_environment; configure_ssl_environment(); sqs = boto3.client('sqs', region_name='us-east-1'); sqs.list_queues(); print('Health check passed')" || exit 1

# Default command
CMD ["python", "src/main.py"]
