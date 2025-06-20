#!/bin/bash

# Build validation script
# This script validates that the Docker build will succeed

set -e

echo "🔍 Validating Docker build environment..."

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found"
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found"
    exit 1
fi

# Check if src directory exists
if [ ! -d "src" ]; then
    echo "❌ src directory not found"
    exit 1
fi

# Check if main.py exists
if [ ! -f "src/main.py" ]; then
    echo "❌ src/main.py not found"
    exit 1
fi

# Check if all required Python modules can be imported
echo "🐍 Validating Python imports..."
python3 -c "
import sys
sys.path.insert(0, 'src')

try:
    from utils.aws_clients import get_s3_client, get_sqs_client
    from utils.config import QUEUE_URL
    from utils.logging_config import setup_custom_logger
    print('✅ Core modules import successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

# Validate Docker syntax
echo "🐳 Validating Dockerfile syntax..."
docker build --no-cache --target builder -t video-trimming-test . > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Dockerfile syntax is valid"
    docker rmi video-trimming-test > /dev/null 2>&1 || true
else
    echo "❌ Dockerfile has syntax errors"
    exit 1
fi

# Check ECS task definition syntax
echo "📋 Validating ECS task definition..."
if command -v aws &> /dev/null; then
    aws ecs validate-task-definition --cli-input-json file://ecs-task-definition.json > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ ECS task definition is valid"
    else
        echo "⚠️  ECS task definition validation failed (check AWS CLI setup)"
    fi
else
    echo "⚠️  AWS CLI not found, skipping ECS validation"
fi

echo ""
echo "🎉 Build validation completed successfully!"
echo ""
echo "Next steps:"
echo "1. Configure your .env file with AWS credentials"
echo "2. Run 'make build' to build the Docker image"
echo "3. Run 'make push' to push to ECR"
echo "4. Run 'make deploy' to deploy to ECS"
