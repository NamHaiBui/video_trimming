#!/bin/bash

# Create SQS queue in LocalStack
echo "Creating SQS queue in LocalStack..."

# Set LocalStack endpoint
ENDPOINT_URL="http://localhost:4566"
QUEUE_NAME="video-processing-queue"

# Create the queue
aws --endpoint-url=$ENDPOINT_URL sqs create-queue --queue-name $QUEUE_NAME --region us-east-1

# Get queue URL
QUEUE_URL=$(aws --endpoint-url=$ENDPOINT_URL sqs get-queue-url --queue-name $QUEUE_NAME --region us-east-1 --output text)

echo "Queue created successfully!"
echo "Queue URL: $QUEUE_URL"
echo ""
echo "Set this environment variable:"
echo "export SQS_QUEUE_URL='$QUEUE_URL'"
