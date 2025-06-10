# Video Trimming Project

A Python-based video processing pipeline for automatic chunking, quote extraction, and summarization of podcast episodes.

## 🎯 Overview

This project provides an automated video processing pipeline that:
- Downloads podcast episodes from S3 storage
- Extracts important chunks and quotes from transcripts
- Generates trimmed video segments
- Creates audio summaries
- Manages processing status in DynamoDB

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   S3 Storage    │    │   DynamoDB      │    │   Processing    │
│   - Audio       │◄──►│   - Metadata    │◄──►│   - FFmpeg      │
│   - Video       │    │   - Chunks      │    │   - Chunking    │
│   - Transcripts │    │   - Quotes      │    │   - Summarizing │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- FFmpeg (automatically installed by setup script)
- AWS credentials configured
- Virtual environment (recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd video_trimming
   ```

2. **Run the complete setup:**
   ```bash
   ./scripts/setup_project.sh
   ```

   This script will:
   - Set up virtual environment
   - Install all dependencies
   - Install and configure FFmpeg
   - Create configuration files
   - Run tests

3. **Configure environment:**
   ```bash
   cp .env.template .env
   # Edit .env with your AWS credentials and configuration
   ```

### Manual Setup (Alternative)

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install FFmpeg
./scripts/setup_ffmpeg.sh

# Run tests
make test
```

## 🎮 Usage

### Command Line

Run the main processing pipeline:

```bash
# Using the helper script
./run.sh '{"id": "episode-id", "force_summarization": true, "force_audio_chunking": true, "force_audio_quote_extraction": true}'

# Direct execution
python src/main.py '{"id": "episode-id", "force_summarization": false}'

# Using make
make run
make run-sample
```

### Docker

```bash
# Build and run with Docker
make docker-build
make docker-run

# Or with docker-compose
docker-compose up -d
```

### Development

```bash
# Activate development environment
source activate.sh

# Run tests
make test
make test-unit
make test-integration

# Code quality checks
make lint
make format
make type-check
make security-check
```

## 📁 Project Structure

```
video_trimming/
├── src/                        # Source code
│   ├── main.py                # Main application entry point
│   ├── models/                # Data models
│   ├── tools/                 # Video processing tools
│   └── utils/                 # Utility functions
├── scripts/                   # Setup and utility scripts
│   ├── setup_project.sh      # Complete project setup
│   ├── setup_ffmpeg.sh       # FFmpeg installation
│   ├── install_ffmpeg.py     # Cross-platform FFmpeg installer
│   └── test_ffmpeg.py        # FFmpeg functionality tests
├── tests/                     # Test suite
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── conftest.py          # Test configuration
├── sample/                   # Sample data files
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
├── Dockerfile               # Container definition
├── docker-compose.yml       # Local development stack
├── Makefile                 # Development tasks
└── pyproject.toml          # Project configuration
```

## 🛠️ Configuration

### Environment Variables

The project uses environment variables for configuration. Copy `.env.template` to `.env` and configure:

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# DynamoDB Tables
PODCAST_METADATA_TABLE=PodcastEpisodeStore
QUOTES_TABLE=TranscriptQuoteStore
CHUNK_TABLE=TranscriptChunkStore

# S3 Buckets
AUDIO_BUCKET=pd-audio-storage
VIDEO_BUCKET=pd-video-storage
# ... (see .env.template for full list)

# FFmpeg Configuration
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe

# Application Settings
LOG_LEVEL=INFO
MAX_CONCURRENT_PROCESSING=5
TEMP_DIR=/tmp/video_processing
```

### FFmpeg Setup

FFmpeg is automatically installed by the setup script. For manual installation:

```bash
# Check installation
./scripts/setup_ffmpeg.sh --check

# Install FFmpeg
./scripts/setup_ffmpeg.sh --install

# Test functionality
python scripts/test_ffmpeg.py
```

## 🧪 Testing

The project includes comprehensive test coverage:

```bash
# Run all tests
make test

# Run specific test types
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-slow         # Long-running tests

# Test with coverage
make test-coverage

# Test FFmpeg functionality
make ffmpeg-test
```

### Test Structure

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test component interactions
- **FFmpeg Tests**: Verify video processing capabilities
- **Mock Tests**: Use mocked AWS services for development

## 🔧 Development

### Code Quality

The project enforces code quality through:

```bash
# Linting
make lint               # Run all linting checks
flake8 src/ tests/     # Python linting
black --check src/     # Code formatting check
mypy src/              # Type checking

# Formatting
make format            # Auto-format code
black src/ tests/      # Format Python code
isort src/ tests/      # Sort imports

# Security
make security-check    # Security scanning
bandit -r src/         # Security linting
safety check           # Dependency security
```

### Pre-commit Hooks

Install pre-commit hooks for automatic code quality checks:

```bash
make pre-commit-install
make pre-commit-run
```

### Development Environment

```bash
# Start development shell
make dev-shell

# Count lines of code
make count-lines

# Check for outdated dependencies
make check-deps
```

## 📊 Monitoring

### Docker Compose with Monitoring

Enable monitoring stack:

```bash
# Start with monitoring services
docker-compose --profile monitoring up -d

# Access services
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
# MinIO: http://localhost:9001 (minioadmin/minioadmin123)
```

### Local Development Stack

- **DynamoDB Local**: Port 8001
- **LocalStack**: Port 4566 (AWS services emulation)
- **Redis**: Port 6379
- **MinIO**: Port 9000/9001

## 🚀 Deployment

### Production Deployment

1. **Build production image:**
   ```bash
   docker build --target production -t video-trimming:prod .
   ```

2. **Deploy with environment variables:**
   ```bash
   docker run -d \
     --name video-trimming-prod \
     -e AWS_ACCESS_KEY_ID=your_key \
     -e AWS_SECRET_ACCESS_KEY=your_secret \
     -e LOG_LEVEL=INFO \
     video-trimming:prod
   ```

### AWS Lambda Deployment

The application can be packaged for AWS Lambda deployment:

```bash
# Package for Lambda
zip -r lambda-package.zip src/ requirements.txt

# Deploy using AWS CLI or CDK
aws lambda create-function \
  --function-name video-trimming \
  --runtime python3.11 \
  --zip-file fileb://lambda-package.zip
```

## 🔍 Troubleshooting

### Common Issues

1. **FFmpeg not found:**
   ```bash
   ./scripts/setup_ffmpeg.sh --install
   ```

2. **AWS credentials not configured:**
   ```bash
   aws configure
   # or set environment variables in .env
   ```

3. **Permission errors:**
   ```bash
   chmod +x scripts/*.sh
   ```

4. **Dependencies issues:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python src/main.py '{"id": "test-episode"}'
```

### FFmpeg Issues

Test FFmpeg installation:

```bash
python scripts/test_ffmpeg.py
ffmpeg -version
ffprobe -version
```

## 📈 Performance

### Optimization Tips

1. **Concurrent Processing:**
   ```bash
   export MAX_CONCURRENT_PROCESSING=10
   ```

2. **Temporary Directory on SSD:**
   ```bash
   export TEMP_DIR=/fast-ssd/video_processing
   ```

3. **FFmpeg Hardware Acceleration:**
   Configure GPU acceleration in FFmpeg commands

### Monitoring Performance

Use built-in profiling:

```bash
make profile
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks: `make ci-build`
5. Submit a pull request

### Development Workflow

```bash
# Setup development environment
./scripts/setup_project.sh

# Make changes
# ... edit code ...

# Run tests and quality checks
make test
make lint
make type-check

# Format code
make format

# Commit changes
git add .
git commit -m "Your changes"
```

## 📄 License

[Specify your license here]

## 🙋 Support

For issues and questions:

1. Check the [troubleshooting section](#-troubleshooting)
2. Review existing issues
3. Create a new issue with:
   - Error messages
   - System information
   - Steps to reproduce

## 🔗 Links

- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [AWS SDK for Python (Boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Docker Documentation](https://docs.docker.com/)
- [pytest Documentation](https://docs.pytest.org/)
