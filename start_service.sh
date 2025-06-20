#!/bin/bash
# Startup script for Video Trimming Service with SSL configuration

echo "🚀 Starting Video Trimming Service..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
    source venv/bin/activate
fi

# Configure SSL environment
echo "🔧 Configuring SSL environment..."
source setup_ssl_env.sh

# Check if SSL setup was successful
if [ $? -ne 0 ]; then
    echo "❌ SSL setup failed. Exiting..."
    exit 1
fi

# Start the main application
echo "🎬 Starting video trimming service..."
python src/main.py "$@"
