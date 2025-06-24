#!/bin/bash
# ECS Deployment Script with SSL Configuration for Video Trimming Service

set -e

# Configuration
REGION="us-east-1"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
REPOSITORY_NAME="video-trimming"
SERVICE_NAME="video-trimming-service"
CLUSTER_NAME="video-processing-cluster"
IMAGE_TAG="${1:-latest}"

echo "🚀 Starting ECS deployment for Video Trimming Service"
echo "   Account ID: $ACCOUNT_ID"
echo "   Region: $REGION"
echo "   Repository: $REPOSITORY_NAME"
echo "   Image Tag: $IMAGE_TAG"

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI."
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please configure AWS CLI."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Create ECR repository if it doesn't exist
echo "🔧 Setting up ECR repository..."
aws ecr describe-repositories --repository-names $REPOSITORY_NAME --region $REGION 2>/dev/null || {
    echo "Creating ECR repository: $REPOSITORY_NAME"
    aws ecr create-repository --repository-name $REPOSITORY_NAME --region $REGION
}

# Get ECR login token
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build Docker image with SSL configuration
echo "🔨 Building Docker image with SSL configuration..."
docker build -t $REPOSITORY_NAME:$IMAGE_TAG .

# Tag image for ECR
echo "🏷️ Tagging image for ECR..."
docker tag $REPOSITORY_NAME:$IMAGE_TAG $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG

# Push image to ECR
echo "📤 Pushing image to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:$IMAGE_TAG

# Update task definition with new image and SSL config
echo "🔄 Updating ECS task definition..."
TASK_DEFINITION_JSON=$(cat ecs-task-definition.json | \
    sed "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" | \
    sed "s/:latest/:$IMAGE_TAG/g")

# Register the new task definition
NEW_TASK_DEFINITION_ARN=$(echo "$TASK_DEFINITION_JSON" | \
    aws ecs register-task-definition --region $REGION --cli-input-json file:///dev/stdin --query 'taskDefinition.taskDefinitionArn' --output text)

echo "✅ New task definition registered: $NEW_TASK_DEFINITION_ARN"

# Check if ECS cluster exists
echo "🔍 Checking ECS cluster..."
if ! aws ecs describe-clusters --clusters $CLUSTER_NAME --region $REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "Creating ECS cluster: $CLUSTER_NAME"
    aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $REGION --capacity-providers FARGATE --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1
fi

# Check if ECS service exists
echo "🔍 Checking ECS service..."
if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "🔄 Updating existing ECS service..."
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $NEW_TASK_DEFINITION_ARN \
        --region $REGION
else
    echo "🆕 Creating new ECS service..."
    # Create service using the service definition
    if [ -f "ecs-service-definition.json" ]; then
        SERVICE_DEFINITION_JSON=$(cat ecs-service-definition.json | \
            sed "s/YOUR_ACCOUNT_ID/$ACCOUNT_ID/g" | \
            sed "s/YOUR_TASK_DEFINITION_ARN/${NEW_TASK_DEFINITION_ARN//\//\\/}/g")
        
        echo "$SERVICE_DEFINITION_JSON" | \
            aws ecs create-service --region $REGION --cli-input-json file:///dev/stdin
    else
        echo "⚠️ ecs-service-definition.json not found. Creating basic service..."
        aws ecs create-service \
            --cluster $CLUSTER_NAME \
            --service-name $SERVICE_NAME \
            --task-definition $NEW_TASK_DEFINITION_ARN \
            --desired-count 1 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678],securityGroups=[sg-12345678],assignPublicIp=ENABLED}" \
            --region $REGION
    fi
fi

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
aws ecs wait services-stable --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION

# Get service status
echo "📊 Getting deployment status..."
aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION --query 'services[0].{Status:status,TaskDefinition:taskDefinition,DesiredCount:desiredCount,RunningCount:runningCount}'

echo "🎉 ECS deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "   - Monitor logs: aws logs tail /ecs/video-trimming --follow --region $REGION"
echo "   - Check service: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
echo "   - Update service: ./deploy_ecs.sh [new-tag]"
echo ""
echo "🔧 SSL Configuration included:"
echo "   ✅ SSL certificate bundle paths configured"
echo "   ✅ Environment variables set in task definition"
echo "   ✅ Health check includes SSL validation"
echo "   ✅ Docker image includes SSL configuration"
