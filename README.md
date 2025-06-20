# Video Trimming Service

A containerized video processing service that automatically trims video content based on podcast transcripts. The service processes videos to create chunks, quotes, and summaries using AWS infrastructure.

## Features

- **Video Chunking**: Splits videos into meaningful segments based on transcript timestamps
- **Quote Extraction**: Creates short video clips for highlighted quotes
- **Summary Generation**: Produces condensed video summaries
- **AWS Integration**: Uses SQS for messaging, DynamoDB for metadata, and S3 for storage
- **Containerized**: Ready for deployment on AWS ECS Fargate
- **Scalable**: Configurable concurrency and resource limits

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  SQS Queue  │───▶│   ECS Task   │───▶│  Video Output   │
└─────────────┘    └──────────────┘    └─────────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │  DynamoDB    │
                   │  (Metadata)  │
                   └──────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │      S3      │
                   │  (Storage)   │
                   └──────────────┘
```

## Quick Start

### Prerequisites

- Docker installed
- AWS CLI configured with appropriate permissions
- AWS resources (SQS, DynamoDB, S3) set up

### SSL Configuration (Important!)

This service requires proper SSL certificate configuration to connect to AWS services. We've included scripts to automatically handle this:

1. **Automatic SSL Setup**: The service will automatically configure SSL certificates when starting
2. **Manual SSL Setup**: If you encounter SSL issues, run:
   ```bash
   source setup_ssl_env.sh
   ```
3. **Test SSL Configuration**: Verify SSL setup with:
   ```bash
   python test_ssl_fix.py
   ```

### Local Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd video_trimming
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and configuration
   ```

3. **Start the service** (with automatic SSL configuration):
   ```bash
   ./start_service.sh
   ```
   
   Or run manually:
   ```bash
   # Set up environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Configure SSL and start
   source setup_ssl_env.sh
   python src/main.py
   ```

### Troubleshooting SSL Issues

If you encounter SSL errors like "EOF occurred in violation of protocol (_ssl.c:2427)", the service includes several tools to diagnose and fix these issues:

1. **Run SSL diagnostics**:
   ```bash
   python scripts/fix_ssl_issues.py
   ```

2. **Test SSL configuration**:
   ```bash
   python test_ssl_fix.py
   ```

3. **Check certificate bundle**:
   ```bash
   python -c "import certifi; print(certifi.where())"
   ```

The SSL configuration tools will:
- Verify Python SSL support
- Check certificate bundle integrity
- Test AWS service connectivity
- Set appropriate environment variables

### Production Deployment

1. Build and push to ECR:
   ```bash
   make push
   ```

2. Deploy to ECS:
   ```bash
   make deploy
   ```

For detailed deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_CONCURRENT_PROCESSING` | Max concurrent jobs | `3` |
| `MAX_CONCURRENT_CHUNKS` | Max concurrent chunk processing | `1` |
| `MAX_CONCURRENT_QUOTES` | Max concurrent quote processing | `1` |
| `MAX_CONCURRENT_SUMMARIES` | Max concurrent summary processing | `1` |
| `TEMP_DIR` | Temporary file directory | `/tmp/video_processing` |
| `CHUNK_PROCESSING_TIMEOUT` | Chunk processing timeout (seconds) | `1800` |
| `QUOTE_PROCESSING_TIMEOUT` | Quote processing timeout (seconds) | `3600` |
| `SUMMARY_PROCESSING_TIMEOUT` | Summary processing timeout (seconds) | `2400` |

### AWS Resources

The service requires the following AWS resources:

#### DynamoDB Tables
- `PODCAST_METADATA_TABLE`: Episode metadata and processing status
- `QUOTES_TABLE`: Quote information and timestamps
- `CHUNK_TABLE`: Video chunk information

#### S3 Buckets
- `VIDEO_BUCKET`: Source video files
- `SUMMARY_TRANSCRIPT_BUCKET`: Transcript files
- `VIDEO_QUOTES_CHUNK_BUCKET`: Processed quote videos
- `CHUNK_VIDEO_BUCKET`: Processed chunk videos
- `VIDEO_SUMMARY_BUCKET`: Processed summary videos

#### SQS Queue
- `SQS_QUEUE_URL`: Message queue for processing requests

## Docker Commands

### Development Commands

```bash
# Build image locally
make build

# Run tests
make test

# Access container shell
make shell

# Run locally with Docker Compose
make local-run

# Stop local environment
make local-stop
```

### Production Commands

```bash
# Deploy to production
make deploy

# View logs
make logs

# Check service status
make status

# Get deployment info
make info
```

## Message Format

The service processes SQS messages with the following format:

```json
{
  "id": "episode-uuid",
  "force_video_chunking": false,
  "force_video_quote_extraction": false,
  "force_video_summary_extraction": false
}
```

## Processing Flow

1. **Message Reception**: Service polls SQS queue for processing requests
2. **Metadata Retrieval**: Fetches episode metadata from DynamoDB
3. **Video Download**: Downloads source video from S3
4. **Sequential Processing**:
   - Video chunking (if enabled)
   - Quote extraction (if enabled)  
   - Summary generation (if enabled)
5. **Upload Results**: Processed videos uploaded to respective S3 buckets
6. **Status Update**: Processing status updated in DynamoDB

## Monitoring

### Health Checks

The container includes health checks that verify:
- AWS connectivity via boto3
- Container responsiveness

### Logging

- Application logs are written to CloudWatch Logs
- Log group: `/ecs/video-trimming`
- Structured logging with appropriate log levels

### Metrics

Monitor these key metrics:
- Processing time per video
- Success/failure rates
- Resource utilization (CPU, memory)
- Queue depth and processing lag

## Troubleshooting

### Common Issues

1. **Out of Memory Errors**
   - Increase ECS task memory allocation
   - Reduce concurrent processing limits
   - Monitor temporary file cleanup

2. **Video Processing Failures**
   - Check FFmpeg installation and paths
   - Verify source video format compatibility
   - Review timestamp accuracy in source data

3. **AWS Permission Errors**
   - Verify IAM roles and policies
   - Check resource names and regions
   - Validate SSM parameter access

### Debug Mode

Enable debug logging by setting `LOG_LEVEL=DEBUG` in your environment.

## Development

### Project Structure

```
.
├── src/
│   ├── main.py                 # Application entry point
│   ├── models/                 # Data models
│   ├── tools/                  # Video processing tools
│   └── utils/                  # Utility functions
├── scripts/                    # Setup and utility scripts
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Local development
├── ecs-task-definition.json    # ECS task configuration
├── ecs-service-definition.json # ECS service configuration
└── requirements.txt            # Python dependencies
```

### Testing

Run the test suite:

```bash
# Run all tests
make test

# Run with coverage
docker run --rm --env-file .env video-trimming python -m pytest --cov=src
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Security

- Container runs as non-root user
- Sensitive configuration stored in AWS Parameter Store
- Network isolation using VPC private subnets
- IAM roles follow least privilege principle

## Performance

### Resource Requirements

- **CPU**: 2 vCPU recommended for concurrent processing
- **Memory**: 4GB minimum, 8GB recommended for large videos
- **Storage**: Ephemeral storage for temporary files
- **Network**: Sufficient bandwidth for S3 transfers

### Optimization Tips

- Use appropriate video codecs and quality settings
- Implement proper cleanup of temporary files
- Monitor and tune concurrency settings
- Consider using Fargate Spot for cost optimization

## License

[Your License Here]

## Support

For issues and questions:
- Create GitHub issues for bugs and feature requests
- Check CloudWatch logs for error details
- Review the deployment guide for setup issues
