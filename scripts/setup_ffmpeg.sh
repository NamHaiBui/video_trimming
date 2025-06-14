#!/bin/bash

# FFmpeg Installation and Setup Script
# Supports Linux, macOS, and Windows (via WSL)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if [ -f /etc/debian_version ]; then
            DISTRO="debian"
        elif [ -f /etc/redhat-release ]; then
            DISTRO="redhat"
        elif [ -f /etc/arch-release ]; then
            DISTRO="arch"
        else
            DISTRO="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        DISTRO="macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
        OS="windows"
        DISTRO="windows"
    else
        OS="unknown"
        DISTRO="unknown"
    fi
    
    print_status "Detected OS: $OS ($DISTRO)"
}

# Function to check if FFmpeg is already installed
check_ffmpeg_installation() {
    print_status "Checking FFmpeg installation..."
    
    if command_exists ffmpeg && command_exists ffprobe; then
        FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -n1 | cut -d' ' -f3)
        FFPROBE_VERSION=$(ffprobe -version 2>/dev/null | head -n1 | cut -d' ' -f3)
        
        print_success "FFmpeg is already installed:"
        echo "  FFmpeg version: $FFMPEG_VERSION"
        echo "  FFprobe version: $FFPROBE_VERSION"
        echo "  FFmpeg path: $(which ffmpeg)"
        echo "  FFprobe path: $(which ffprobe)"
        return 0
    else
        print_warning "FFmpeg not found in PATH"
        return 1
    fi
}

# Function to install FFmpeg on Linux
install_ffmpeg_linux() {
    print_status "Installing FFmpeg on Linux..."
    
    case $DISTRO in
        "debian")
            print_status "Using apt package manager..."
            sudo apt-get update
            sudo apt-get install -y ffmpeg
            ;;
        "redhat")
            if command_exists dnf; then
                print_status "Using dnf package manager..."
                sudo dnf install -y ffmpeg
            elif command_exists yum; then
                print_status "Using yum package manager..."
                # Enable EPEL repository for CentOS/RHEL
                sudo yum install -y epel-release
                sudo yum install -y ffmpeg
            fi
            ;;
        "arch")
            print_status "Using pacman package manager..."
            sudo pacman -S --noconfirm ffmpeg
            ;;
        *)
            print_warning "Unsupported Linux distribution. Trying generic installation..."
            install_ffmpeg_static_linux
            ;;
    esac
}

# Function to install static FFmpeg on Linux
install_ffmpeg_static_linux() {
    print_status "Installing official FFmpeg build for Linux..."
    
    # Create local bin directory
    mkdir -p ~/.local/bin
    
    # Download official FFmpeg build from BtbN/FFmpeg-Builds
    ARCH=$(uname -m)
    if [[ "$ARCH" == "x86_64" ]]; then
        FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
    elif [[ "$ARCH" == "i386" ]] || [[ "$ARCH" == "i686" ]]; then
        FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux32-gpl.tar.xz"
    elif [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
        FFMPEG_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
    else
        print_error "Unsupported architecture: $ARCH"
        return 1
    fi
    
    print_status "Downloading FFmpeg from $FFMPEG_URL..."
    cd /tmp
    
    if command_exists wget; then
        wget -O ffmpeg-static.tar.xz "$FFMPEG_URL"
    elif command_exists curl; then
        curl -L -o ffmpeg-static.tar.xz "$FFMPEG_URL"
    else
        print_error "Neither wget nor curl found. Cannot download FFmpeg."
        return 1
    fi
    
    print_status "Extracting FFmpeg..."
    tar -xf ffmpeg-static.tar.xz
    
    # Find the extracted directory
    FFMPEG_DIR=$(find . -maxdepth 1 -name "ffmpeg-*" -type d | head -n1)
    
    if [ -z "$FFMPEG_DIR" ]; then
        print_error "Could not find extracted FFmpeg directory"
        return 1
    fi
    
    # Copy binaries to local bin (they should be in bin/ subdirectory)
    if [ -f "$FFMPEG_DIR/bin/ffmpeg" ]; then
        cp "$FFMPEG_DIR/bin/ffmpeg" ~/.local/bin/
        cp "$FFMPEG_DIR/bin/ffprobe" ~/.local/bin/
    else
        # Fallback: look for binaries in the root directory
        cp "$FFMPEG_DIR/ffmpeg" ~/.local/bin/ 2>/dev/null || true
        cp "$FFMPEG_DIR/ffprobe" ~/.local/bin/ 2>/dev/null || true
    fi
    
    # Make executable
    chmod +x ~/.local/bin/ffmpeg ~/.local/bin/ffprobe
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        export PATH="$HOME/.local/bin:$PATH"
        print_status "Added ~/.local/bin to PATH"
    fi
    
    # Clean up
    rm -rf ffmpeg-static.tar.xz "$FFMPEG_DIR"
    
    print_success "Official FFmpeg build installed to ~/.local/bin/"
}

# Function to install FFmpeg on macOS
install_ffmpeg_macos() {
    print_status "Installing FFmpeg on macOS..."
    
    if command_exists brew; then
        print_status "Using Homebrew..."
        brew install ffmpeg
    else
        print_error "Homebrew not found. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        return 1
    fi
}

# Function to install FFmpeg on Windows (WSL)
install_ffmpeg_windows() {
    print_status "Installing FFmpeg on Windows/WSL..."
    
    if command_exists apt-get; then
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    else
        print_error "WSL with Ubuntu/Debian required for Windows installation"
        return 1
    fi
}

# Function to update environment configuration
update_env_config() {
    print_status "Updating environment configuration..."
    
    FFMPEG_PATH=$(which ffmpeg 2>/dev/null || echo "")
    FFPROBE_PATH=$(which ffprobe 2>/dev/null || echo "")
    
    if [ -n "$FFMPEG_PATH" ] && [ -n "$FFPROBE_PATH" ]; then
        # Update .env file if it exists
        if [ -f ".env" ]; then
            # Update or add FFMPEG_PATH
            if grep -q "^FFMPEG_PATH=" ".env"; then
                sed -i "s|^FFMPEG_PATH=.*|FFMPEG_PATH=$FFMPEG_PATH|" ".env"
            else
                echo "FFMPEG_PATH=$FFMPEG_PATH" >> ".env"
            fi
            
            # Update or add FFPROBE_PATH
            if grep -q "^FFPROBE_PATH=" ".env"; then
                sed -i "s|^FFPROBE_PATH=.*|FFPROBE_PATH=$FFPROBE_PATH|" ".env"
            else
                echo "FFPROBE_PATH=$FFPROBE_PATH" >> ".env"
            fi
            
            print_success "Updated .env file with FFmpeg paths"
        fi
        
        # Update .env.template if it exists
        if [ -f ".env.template" ]; then
            sed -i "s|^FFMPEG_PATH=.*|FFMPEG_PATH=$FFMPEG_PATH|" ".env.template"
            sed -i "s|^FFPROBE_PATH=.*|FFPROBE_PATH=$FFPROBE_PATH|" ".env.template"
            print_success "Updated .env.template with FFmpeg paths"
        fi
    fi
}

# Function to test FFmpeg installation
test_ffmpeg_installation() {
    print_status "Testing FFmpeg installation..."
    
    if ! command_exists ffmpeg || ! command_exists ffprobe; then
        print_error "FFmpeg or FFprobe not found in PATH"
        return 1
    fi
    
    # Test basic functionality
    print_status "Testing FFmpeg functionality..."
    
    # Create a test audio file
    TEST_DIR="/tmp/ffmpeg_test_$$"
    mkdir -p "$TEST_DIR"
    cd "$TEST_DIR"
    
    # Generate a 1-second silent audio file
    if ffmpeg -f lavfi -i "anullsrc=r=44100:cl=mono" -t 1 -f wav test_input.wav -y >/dev/null 2>&1; then
        print_success "✓ FFmpeg can generate audio"
    else
        print_error "✗ FFmpeg audio generation failed"
        cleanup_test
        return 1
    fi
    
    # Test audio processing
    if ffmpeg -i test_input.wav -af "volume=0.5" test_output.wav -y >/dev/null 2>&1; then
        print_success "✓ FFmpeg can process audio"
    else
        print_error "✗ FFmpeg audio processing failed"
        cleanup_test
        return 1
    fi
    
    # Test FFprobe
    if ffprobe -v quiet -print_format json -show_format test_output.wav >/dev/null 2>&1; then
        print_success "✓ FFprobe can analyze files"
    else
        print_error "✗ FFprobe analysis failed"
        cleanup_test
        return 1
    fi
    
    cleanup_test
    print_success "FFmpeg installation test passed!"
}

cleanup_test() {
    cd /
    rm -rf "$TEST_DIR" 2>/dev/null || true
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --check        Check if FFmpeg is installed"
    echo "  --install      Install FFmpeg"
    echo "  --test         Test FFmpeg functionality"
    echo "  --update-env   Update environment configuration"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --check                # Check installation"
    echo "  $0 --install               # Install FFmpeg"
    echo "  $0 --install --test        # Install and test"
}

# Main function
main() {
    local check_only=false
    local install_ffmpeg=false
    local test_only=false
    local update_env_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check)
                check_only=true
                shift
                ;;
            --install)
                install_ffmpeg=true
                shift
                ;;
            --test)
                test_only=true
                shift
                ;;
            --update-env)
                update_env_only=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # If no arguments, default to install
    if [ "$check_only" = false ] && [ "$install_ffmpeg" = false ] && [ "$test_only" = false ] && [ "$update_env_only" = false ]; then
        install_ffmpeg=true
    fi
    
    echo "============================================"
    echo "FFmpeg Setup Script"
    echo "============================================"
    
    detect_os
    
    if [ "$check_only" = true ] || [ "$install_ffmpeg" = true ]; then
        if check_ffmpeg_installation; then
            if [ "$check_only" = true ]; then
                exit 0
            fi
            print_status "FFmpeg already installed, skipping installation"
        elif [ "$install_ffmpeg" = true ]; then
            case $OS in
                "linux")
                    install_ffmpeg_linux
                    ;;
                "macos")
                    install_ffmpeg_macos
                    ;;
                "windows")
                    install_ffmpeg_windows
                    ;;
                *)
                    print_error "Unsupported operating system: $OS"
                    exit 1
                    ;;
            esac
            
            # Verify installation
            if check_ffmpeg_installation; then
                print_success "FFmpeg installation completed successfully"
            else
                print_error "FFmpeg installation failed"
                exit 1
            fi
        fi
    fi
    
    if [ "$update_env_only" = true ] || [ "$install_ffmpeg" = true ]; then
        update_env_config
    fi
    
    if [ "$test_only" = true ] || [ "$install_ffmpeg" = true ]; then
        test_ffmpeg_installation
    fi
    
    echo "============================================"
    print_success "FFmpeg setup completed!"
    echo "============================================"
}

# Run main function
main "$@"
