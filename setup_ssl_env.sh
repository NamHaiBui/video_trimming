#!/bin/bash
# SSL Environment Setup Script for Video Trimming Service
# This script sets up SSL certificate environment variables to fix SSL issues

# Get the certifi certificate bundle path
CERT_PATH=$(python -c "import certifi; print(certifi.where())" 2>/dev/null)

if [ -z "$CERT_PATH" ]; then
    echo "❌ Error: Could not find certifi certificate bundle"
    echo "Make sure certifi is installed: pip install certifi"
    exit 1
fi

if [ ! -f "$CERT_PATH" ]; then
    echo "❌ Error: Certificate bundle not found at: $CERT_PATH"
    exit 1
fi

echo "🔧 Setting up SSL environment variables..."
echo "📄 Certificate bundle: $CERT_PATH"

# Export SSL environment variables
export SSL_CERT_FILE="$CERT_PATH"
export SSL_CERT_DIR="$(dirname "$CERT_PATH")"
export REQUESTS_CA_BUNDLE="$CERT_PATH"
export CURL_CA_BUNDLE="$CERT_PATH"

# Also set for Python SSL context
export PYTHONHTTPSVERIFY=1

echo "✅ SSL environment variables configured:"
echo "   SSL_CERT_FILE=$SSL_CERT_FILE"
echo "   SSL_CERT_DIR=$SSL_CERT_DIR"
echo "   REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE"
echo "   CURL_CA_BUNDLE=$CURL_CA_BUNDLE"
echo "   PYTHONHTTPSVERIFY=$PYTHONHTTPSVERIFY"

# Test SSL configuration
echo "🧪 Testing SSL configuration..."
python -c "
import ssl
import certifi
import requests
import boto3
from src.utils.aws_clients import get_sqs_client

try:
    # Test certificate bundle
    cert_path = certifi.where()
    print(f'✅ Certificate bundle: {cert_path}')
    
    # Test SSL context
    context = ssl.create_default_context()
    print('✅ SSL context created')
    
    # Test AWS SQS client
    sqs = get_sqs_client()
    print('✅ SQS client created')
    
    # Test SQS connection
    response = sqs.list_queues()
    print(f'✅ SQS connection test: Found {len(response.get(\"QueueUrls\", []))} queues')
    
    print('🎉 All SSL tests passed!')
    
except Exception as e:
    print(f'❌ SSL test failed: {e}')
    import sys
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "🎉 SSL environment setup completed successfully!"
    echo ""
    echo "To use these settings, run:"
    echo "   source setup_ssl_env.sh"
    echo "   python src/main.py"
else
    echo "❌ SSL setup failed!"
    exit 1
fi
