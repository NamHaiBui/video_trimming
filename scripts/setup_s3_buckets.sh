#!/bin/bash

# S3 Bucket Creation Script Wrapper
# This script ensures all required S3 buckets are created for the video trimming application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Video Trimming Project - S3 Bucket Setup"
print_status "Project directory: $PROJECT_DIR"

# Check if Python script exists
PYTHON_SCRIPT="$SCRIPT_DIR/create_s3_buckets.py"
if [ ! -f "$PYTHON_SCRIPT" ]; then
    print_error "Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if .env file exists
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    print_error ".env file not found: $ENV_FILE"
    print_error "Please create a .env file with your bucket configurations"
    exit 1
fi

print_status "Loading environment from: $ENV_FILE"

# Check for Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

# Check for required Python packages
print_status "Checking Python dependencies..."
python3 -c "import boto3, dotenv" 2>/dev/null || {
    print_error "Required Python packages not found"
    print_error "Please install: pip install boto3 python-dotenv"
    exit 1
}

# Run the Python script
print_status "Running S3 bucket creation script..."
cd "$PROJECT_DIR"

if python3 "$PYTHON_SCRIPT" "$@"; then
    print_success "S3 bucket setup completed successfully!"
else
    print_error "S3 bucket setup failed"
    exit 1
fi
