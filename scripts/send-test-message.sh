#!/bin/bash

# Send test message to LocalStack SQS
ENDPOINT_URL="http://localhost:4566"
QUEUE_URL="${SQS_QUEUE_URL:-http://localhost:4566/000000000000/video-processing-queue}"

# Test message payload
MESSAGE_BODY='{
  "id": "test-episode-123",
  "podcast_title": "Test Podcast",
  "episode_title": "Test Episode"
}'

echo "Sending test message to queue: $QUEUE_URL"

aws --endpoint-url=$ENDPOINT_URL sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body "$MESSAGE_BODY" \
  --region us-east-1

echo "Test message sent successfully!"
