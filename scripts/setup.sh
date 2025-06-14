#!/bin/bash

# Simple setup wrapper for the Video Trimming Project
# This script provides an easy entry point for project setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_usage() {
    echo "Video Trimming Project Setup"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  setup               Run complete project setup"
    echo "  check-deps          Check all dependencies"
    echo "  install-ffmpeg      Install FFmpeg only"
    echo "  test-ffmpeg         Test FFmpeg functionality"
    echo "  install-python      Install Python packages only"
    echo "  create-env          Create .env file from template"
    echo "  help                Show this help message"
    echo ""
    echo "Options:"
    echo "  --dev               Include development dependencies"
    echo "  --force             Force reinstallation"
    echo "  --quiet             Quiet mode"
    echo ""
    echo "Examples:"
    echo "  $0 setup              # Complete setup"
    echo "  $0 check-deps         # Check dependencies"
    echo "  $0 install-ffmpeg     # Install FFmpeg only"
    echo "  $0 setup --dev        # Setup with dev dependencies"
}

run_setup() {
    echo -e "${BLUE}Running complete project setup...${NC}"
    cd "$PROJECT_DIR"
    exec "$SCRIPT_DIR/setup_project.sh" "$@"
}

check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"
    cd "$PROJECT_DIR"
    
    if [ -f "$SCRIPT_DIR/check_dependencies.py" ]; then
        python3 "$SCRIPT_DIR/check_dependencies.py" "$@"
    else
        echo -e "${RED}Dependency checker not found${NC}"
        exit 1
    fi
}

install_ffmpeg() {
    echo -e "${BLUE}Installing FFmpeg...${NC}"
    cd "$PROJECT_DIR"
    
    if [ -f "$SCRIPT_DIR/setup_ffmpeg.sh" ]; then
        bash "$SCRIPT_DIR/setup_ffmpeg.sh" --install "$@"
    else
        echo -e "${RED}FFmpeg installer not found${NC}"
        exit 1
    fi
}

test_ffmpeg() {
    echo -e "${BLUE}Testing FFmpeg...${NC}"
    cd "$PROJECT_DIR"
    
    if [ -f "$SCRIPT_DIR/test_ffmpeg.py" ]; then
        python3 "$SCRIPT_DIR/test_ffmpeg.py" "$@"
    else
        echo -e "${RED}FFmpeg tester not found${NC}"
        exit 1
    fi
}

install_python_packages() {
    echo -e "${BLUE}Installing Python packages...${NC}"
    cd "$PROJECT_DIR"
    
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        echo -e "${GREEN}Activating virtual environment...${NC}"
        source venv/bin/activate
    else
        echo -e "${YELLOW}No virtual environment found, using system Python${NC}"
    fi
    
    # Install packages
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo -e "${GREEN}Production packages installed${NC}"
    fi
    
    # Install dev packages if requested
    for arg in "$@"; do
        if [ "$arg" = "--dev" ]; then
            if [ -f "requirements-dev.txt" ]; then
                pip install -r requirements-dev.txt
                echo -e "${GREEN}Development packages installed${NC}"
            fi
            break
        fi
    done
}

create_env_file() {
    echo -e "${BLUE}Creating .env file...${NC}"
    cd "$PROJECT_DIR"
    
    if [ -f ".env.template" ]; then
        if [ -f ".env" ]; then
            echo -e "${YELLOW}.env file already exists${NC}"
            read -p "Overwrite? (y/N): " confirm
            if [[ $confirm =~ ^[Yy]$ ]]; then
                cp .env.template .env
                echo -e "${GREEN}.env file created from template${NC}"
                echo -e "${YELLOW}Please edit .env file with your configuration${NC}"
            fi
        else
            cp .env.template .env
            echo -e "${GREEN}.env file created from template${NC}"
            echo -e "${YELLOW}Please edit .env file with your configuration${NC}"
        fi
    else
        echo -e "${RED}.env.template not found${NC}"
        exit 1
    fi
}

# Main script logic
main() {
    if [ $# -eq 0 ]; then
        print_usage
        exit 1
    fi
    
    COMMAND="$1"
    shift
    
    case "$COMMAND" in
        setup)
            run_setup "$@"
            ;;
        check-deps|check)
            check_dependencies "$@"
            ;;
        install-ffmpeg|ffmpeg)
            install_ffmpeg "$@"
            ;;
        test-ffmpeg|test)
            test_ffmpeg "$@"
            ;;
        install-python|python)
            install_python_packages "$@"
            ;;
        create-env|env)
            create_env_file "$@"
            ;;
        help|--help|-h)
            print_usage
            ;;
        *)
            echo -e "${RED}Unknown command: $COMMAND${NC}"
            echo ""
            print_usage
            exit 1
            ;;
    esac
}

main "$@"
