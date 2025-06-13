#!/bin/bash

# LocalStack Setup Script for Video Trimming Project
# This script sets up LocalStack with required AWS services and uploads sample data

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

# LocalStack configuration
export LOCALSTACK_AUTH_TOKEN="ls-QEsUBiDo-0422-dUSa-hoSe-huBa14459caa"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ENDPOINT_URL="http://localhost:4566"

# Check if LocalStack is installed
check_localstack() {
    print_status "Checking LocalStack installation..."
    
    if ! command -v localstack >/dev/null 2>&1; then
        print_error "LocalStack not found. Installing LocalStack..."
        pip install localstack
    fi
    
    if ! command -v awslocal >/dev/null 2>&1; then
        print_error "awslocal not found. Installing awscli-local..."
        pip install awscli-local
    fi
    
    print_success "LocalStack tools are available"
}

# Start LocalStack
start_localstack() {
    print_status "Starting LocalStack..."
    
    # Check if LocalStack is already running
    if curl -s http://localhost:4566/_localstack/health >/dev/null 2>&1; then
        print_success "LocalStack is already running"
        return 0
    fi
    
    # Start LocalStack in background
    localstack start -d
    
    # Wait for LocalStack to be ready
    print_status "Waiting for LocalStack to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:4566/_localstack/health >/dev/null 2>&1; then
            print_success "LocalStack is ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        print_status "Attempt $attempt/$max_attempts - waiting for LocalStack..."
        sleep 2
    done
    
    print_error "LocalStack failed to start within timeout"
    return 1
}

# Create S3 buckets
create_s3_buckets() {
    print_status "Creating S3 buckets..."
    
    buckets=(
        "pd-audio-storage"
        "pd-video-storage"
        "pd-summary-transcript-storage"
        "pd-audio-quotes-storage"
        "pd-video-quotes-storage"
        "pd-video-chunks-storage"
        "pd-audio-chunks-storage"
        "pd-audio-summary-storage"
        "pd-video-summary-storage"
    )
    
    for bucket in "${buckets[@]}"; do
        print_status "Creating bucket: $bucket"
        awslocal s3 mb s3://$bucket || print_warning "Bucket $bucket might already exist"
    done
    
    # List created buckets
    print_status "Listing created buckets:"
    awslocal s3 ls
    
    print_success "S3 buckets created"
}

# Create DynamoDB tables
create_dynamodb_tables() {
    print_status "Creating DynamoDB tables..."
    
    # Create PodcastEpisodeStore table (metadata table)
    print_status "Creating PodcastEpisodeStore table..."
    awslocal dynamodb create-table \
        --table-name PodcastEpisodeStore \
        --attribute-definitions \
            AttributeName=podcast_title,AttributeType=S \
            AttributeName=episode_title,AttributeType=S \
            AttributeName=id,AttributeType=S \
        --key-schema \
            AttributeName=podcast_title,KeyType=HASH \
            AttributeName=episode_title,KeyType=RANGE \
        --global-secondary-indexes \
            IndexName=episodeUUID,KeySchema='[{AttributeName=id,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=5}' \
        --billing-mode PAY_PER_REQUEST || print_warning "PodcastEpisodeStore table might already exist"
    
    # Create TranscriptQuoteStore table
    print_status "Creating TranscriptQuoteStore table..."
    awslocal dynamodb create-table \
    --table-name TranscriptQuoteStore \
    --attribute-definitions \
        AttributeName=podcast_title,AttributeType=S \
        AttributeName="episode_title#quote_rank",AttributeType=S \
    --key-schema \
        AttributeName=podcast_title,KeyType=HASH \
        AttributeName="episode_title#quote_rank",KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST || print_warning "TranscriptQuoteStore table might already exist"

# Create TranscriptChunkStore table
    print_status "Creating TranscriptChunkStore table..."
    awslocal dynamodb create-table \
    --table-name TranscriptChunkStore \
    --attribute-definitions \
        AttributeName=podcast_title,AttributeType=S \
        AttributeName="episode_title#chunk_no",AttributeType=S \
    --key-schema \
        AttributeName=podcast_title,KeyType=HASH \
        AttributeName="episode_title#chunk_no",KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST || print_warning "TranscriptChunkStore table might already exist"
    # Wait for tables to be active
    print_status "Waiting for tables to be active..."
    sleep 5
    
    # List created tables
    print_status "Listing created tables:"
    awslocal dynamodb list-tables
    
    print_success "DynamoDB tables created"
}

# Upload sample files
upload_samples() {
    print_status "Uploading sample files..."
    
    cd "$(dirname "$0")"
    

    # Upload video file
    if [ -f "sample/allin_bryanj.mp4" ]; then
        print_status "Uploading video file..."
        awslocal s3 cp sample/ouput.mp4 s3://pd-video-storage/
        print_success "Video file uploaded"
    else
        print_warning "Video file not found: sample/uncapped_GarryTan_full.mp4"
    fi
    
    # Upload summary transcript
    if [ -f "sample/summary_transcript-all-in-live-from-austin-colin-and-samir-chris-williamson-and-bryan-johnson.json" ]; then
        print_status "Uploading summary transcript..."
        awslocal s3 cp sample/summary_transcript-all-in-live-from-austin-colin-and-samir-chris-williamson-and-bryan-johnson.json s3://pd-summary-transcript-storage/
        print_success "Summary transcript uploaded"
    else
        print_warning "Summary transcript not found"
    fi
    
    # List uploaded files
    print_status "Listing uploaded files:"
    echo "Audio bucket:"
    awslocal s3 ls s3://pd-audio-storage/
    echo "Video bucket:"
    awslocal s3 ls s3://pd-video-storage/
    echo "Summary transcript bucket:"
    awslocal s3 ls s3://pd-summary-transcript-storage/
}

# Load sample data into DynamoDB (if CSV files exist)
load_sample_data() {
    print_status "Loading sample data into DynamoDB..."
    
    # This would require parsing the CSV files and converting to DynamoDB format
    # For now, we'll create a basic entry
    
    if [ -f "sample/Chunk_results.csv" ] || [ -f "sample/Quote_results.csv" ]; then
        print_status "Sample CSV files found - would need to parse and load"
        # TODO: Add CSV parsing and DynamoDB loading logic
        print_warning "CSV loading not implemented yet - manual data entry may be needed"
    fi
}

# Create LocalStack environment file
create_env_file() {
    print_status "Creating LocalStack environment file..."
    
    cat > .env.localstack << EOF
# LocalStack Environment Configuration
# Use this for local development with LocalStack

# ===========================================
# AWS Configuration for LocalStack
# ===========================================
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566

# ===========================================
# DynamoDB Tables
# ===========================================
PODCAST_METADATA_TABLE=PodcastEpisodeStore
QUOTES_TABLE=TranscriptQuoteStore
CHUNK_TABLE=TranscriptChunkStore

# ===========================================
# S3 Buckets - Source Data
# ===========================================
AUDIO_BUCKET=pd-audio-storage
VIDEO_BUCKET=pd-video-storage
SUMMARY_TRANSCRIPT_BUCKET=pd-summary-transcript-storage

# ===========================================
# S3 Buckets - Generated Content
# ===========================================
AUDIO_QUOTES_CHUNK_BUCKET=pd-audio-quotes-storage
VIDEO_QUOTES_CHUNK_BUCKET=pd-video-quotes-storage
CHUNK_VIDEO_BUCKET=pd-video-chunks-storage
AUDIO_CHUNK_BUCKET=pd-audio-chunks-storage
AUDIO_SUMMARY_BUCKET=pd-audio-summary-storage
VIDEO_SUMMARY_BUCKET=pd-video-summary-storage

# ===========================================
# Application Settings
# ===========================================
LOG_LEVEL=INFO
MAX_CONCURRENT_PROCESSING=5
TEMP_DIR=/tmp/video_processing

# ===========================================
# FFmpeg Configuration
# ===========================================
FFMPEG_PATH=/usr/bin/ffmpeg
FFPROBE_PATH=/usr/bin/ffprobe

# ===========================================
# LocalStack Configuration
# ===========================================
LOCALSTACK_AUTH_TOKEN=ls-QEsUBiDo-0422-dUSa-hoSe-huBa14459caa
EOF
    
    print_success "LocalStack environment file created: .env.localstack"
}

# Test LocalStack setup
test_setup() {
    print_status "Testing LocalStack setup..."
    
    # Test S3
    print_status "Testing S3 access..."
    awslocal s3 ls >/dev/null && print_success "S3 access working" || print_error "S3 access failed"
    
    # Test DynamoDB
    print_status "Testing DynamoDB access..."
    awslocal dynamodb list-tables >/dev/null && print_success "DynamoDB access working" || print_error "DynamoDB access failed"
    
    print_success "LocalStack setup test completed"
}

# Main execution
main() {
    echo "================================================================"
    echo "  LocalStack Setup for Video Trimming Project"
    echo "================================================================"
    
    check_localstack
    start_localstack
    create_s3_buckets
    create_dynamodb_tables
    upload_samples
    load_sample_data
    create_env_file
    test_setup
    
    echo ""
    echo "================================================================"
    echo "  Setup Complete!"
    echo "================================================================"
    echo ""
    echo "To use LocalStack configuration:"
    echo "  cp .env.localstack .env"
    echo ""
    echo "To run the application with LocalStack:"
    echo "  source venv/bin/activate"
    echo "  export AWS_ENDPOINT_URL=http://localhost:4566"
    echo "  python run_app.py"
    echo ""
    echo "LocalStack Web UI: http://localhost:4566"
    echo "To stop LocalStack: localstack stop"
    echo ""
}

# Run main function
main "$@"
