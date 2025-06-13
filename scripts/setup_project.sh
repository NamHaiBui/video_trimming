#!/bin/bash

# Video Trimming Project Setup Script
# This script sets up the complete development environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    print_status "Checking Python version..."
    
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    elif command_exists python; then
        PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python"
        else
            print_error "Python 3.8+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python not found. Please install Python 3.8+"
        exit 1
    fi
}

# Function to setup virtual environment
setup_virtual_environment() {
    print_status "Setting up virtual environment..."
    
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        $PYTHON_CMD -m venv venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip
    print_success "Pip upgraded"
}

# Function to install Python dependencies
install_python_dependencies() {
    print_status "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        print_status "Installing production dependencies..."
        pip install -r requirements.txt
        print_success "Production dependencies installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
    
    if [ -f "requirements-dev.txt" ]; then
        print_status "Installing development dependencies..."
        pip install -r requirements-dev.txt
        print_success "Development dependencies installed"
    else
        print_warning "requirements-dev.txt not found, skipping development dependencies"
    fi
}

# Function to check system dependencies
check_system_dependencies() {
    print_status "Checking system dependencies..."
    
    # Check for required system packages
    MISSING_PACKAGES=()
    
    # Check for build tools
    if ! command_exists gcc && ! command_exists clang; then
        MISSING_PACKAGES+=("build-essential")
    fi
    
    # Check for curl/wget
    if ! command_exists curl && ! command_exists wget; then
        MISSING_PACKAGES+=("curl")
    fi
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        print_warning "Missing system packages: ${MISSING_PACKAGES[*]}"
        
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command_exists apt-get; then
                print_status "Installing missing packages with apt-get..."
                sudo apt-get update
                sudo apt-get install -y "${MISSING_PACKAGES[@]}"
            elif command_exists yum; then
                print_status "Installing missing packages with yum..."
                sudo yum install -y "${MISSING_PACKAGES[@]}"
            elif command_exists dnf; then
                print_status "Installing missing packages with dnf..."
                sudo dnf install -y "${MISSING_PACKAGES[@]}"
            else
                print_warning "Package manager not found. Please install: ${MISSING_PACKAGES[*]}"
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            if command_exists brew; then
                print_status "Installing missing packages with brew..."
                brew install "${MISSING_PACKAGES[@]}"
            else
                print_warning "Homebrew not found. Please install: ${MISSING_PACKAGES[*]}"
            fi
        fi
    else
        print_success "All system dependencies satisfied"
    fi
}

# Function to setup FFmpeg
setup_ffmpeg() {
    print_status "Setting up FFmpeg..."
    
    # Run FFmpeg setup script
    if [ -f "scripts/setup_ffmpeg.sh" ]; then
        chmod +x scripts/setup_ffmpeg.sh
        ./scripts/setup_ffmpeg.sh --install
    else
        print_warning "FFmpeg setup script not found, attempting direct installation..."
        
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command_exists apt-get; then
                sudo apt-get update
                sudo apt-get install -y ffmpeg
            elif command_exists yum; then
                sudo yum install -y ffmpeg
            elif command_exists dnf; then
                sudo dnf install -y ffmpeg
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            if command_exists brew; then
                brew install ffmpeg
            fi
        fi
    fi
    
    # Verify FFmpeg installation
    if command_exists ffmpeg && command_exists ffprobe; then
        print_success "FFmpeg installed successfully"
        ffmpeg -version | head -1
    else
        print_error "FFmpeg installation failed"
        exit 1
    fi
}

# Function to setup configuration
setup_configuration() {
    print_status "Setting up configuration..."
    
    if [ -f ".env.template" ] && [ ! -f ".env" ]; then
        print_status "Creating .env file from template..."
        cp .env.template .env
        print_success ".env file created"
        print_warning "Please edit .env file with your actual configuration values"
    elif [ -f ".env" ]; then
        print_success ".env file already exists"
    else
        print_warning "No .env.template found"
    fi
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p temp
    mkdir -p output
    mkdir -p sample
    
    print_success "Directories created"
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    
    # Test Python imports
    print_status "Testing Python imports..."
    $PYTHON_CMD -c "
import sys
try:
    import boto3
    import ffmpeg
    import joblib
    from pydub import AudioSegment
    print('✓ All Python dependencies can be imported')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
"
    
    # Test FFmpeg functionality
    if [ -f "scripts/test_ffmpeg.py" ]; then
        print_status "Testing FFmpeg functionality..."
        $PYTHON_CMD scripts/test_ffmpeg.py
    fi
    
    # Run pytest if available
    if command_exists pytest && [ -d "tests" ]; then
        print_status "Running unit tests..."
        pytest tests/ -v --tb=short || print_warning "Some tests failed"
    fi
    
    print_success "Tests completed"
}

# Function to validate environment
validate_environment() {
    print_status "Validating environment..."
    
    # Check if we can import the main module
    $PYTHON_CMD -c "
import sys
import os
sys.path.insert(0, 'src')
try:
    from utils.config import get_ffmpeg_path, get_ffprobe_path
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    print(f'✓ FFmpeg found at: {ffmpeg_path}')
    print(f'✓ FFprobe found at: {ffprobe_path}')
except Exception as e:
    print(f'✗ Environment validation failed: {e}')
    sys.exit(1)
"
    
    print_success "Environment validation passed"
}

# Main setup function
main() {
    echo "============================================"
    echo "Video Trimming Project Setup"
    echo "============================================"
    echo
    
    # Change to project directory if script is run from elsewhere
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_DIR"
    
    print_status "Project directory: $(pwd)"
    
    # Run setup steps
    check_python_version
    check_system_dependencies
    setup_virtual_environment
    install_python_dependencies
    setup_ffmpeg
    setup_configuration
    create_directories
    validate_environment
    run_tests
    
    echo
    echo "============================================"
    print_success "Setup completed successfully!"
    echo "============================================"
    echo
    echo "Next steps:"
    echo "1. Edit .env file with your AWS credentials and configuration"
    echo "2. Run 'source venv/bin/activate' to activate the virtual environment"
    echo "3. Run 'make test' to run the full test suite"
    echo "4. Run 'make run' to start the application"
    echo
}

# Run main function
main "$@"
