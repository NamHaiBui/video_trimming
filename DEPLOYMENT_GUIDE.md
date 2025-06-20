# Video Trimming Service - Production Deployment Guide

This guide provides instructions for deploying the video trimming service to AWS ECS using Fargate with proper SSL configuration.

## Prerequisites

1. **AWS CLI** installed and configured
2. **Docker** installed
3. **AWS Account** with appropriate permissions
4. **ECR Repository** created for the application

## SSL Configuration (Critical for Production)

The service includes comprehensive SSL configuration to prevent certificate validation errors in AWS environments.

### SSL Features Included
- ✅ Automatic SSL certificate bundle configuration
- ✅ Proper environment variables for AWS SDK
- ✅ Docker container SSL validation
- ✅ ECS task definition SSL settings
- ✅ Health checks with SSL validation

### SSL Validation
Before deploying, validate SSL configuration:
```bash
# Validate ECS SSL configuration
python validate_ecs_ssl.py

# Test local SSL configuration
python test_ssl_fix.py
```

## AWS Resources Required

### IAM Roles

#### ECS Task Execution Role
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach the following managed policies:
- `AmazonECSTaskExecutionRolePolicy`
- `AmazonSSMReadOnlyAccess` (for parameter store secrets)

#### Video Trimming Task Role
Create a custom policy with permissions for:
- DynamoDB (read/write to your tables)
- S3 (read/write to your buckets)
- SQS (receive/delete messages from your queue)

### Infrastructure Components

1. **VPC** with private subnets
2. **ECS Cluster** (Fargate)
3. **Application Load Balancer** (optional)
4. **CloudWatch Log Group**: `/ecs/video-trimming`
5. **ECR Repository**: `video-trimming`

## Deployment Steps

### 1. Build and Push Docker Image

```bash
# Build the Docker image
docker build -t video-trimming .

# Tag for ECR
docker tag video-trimming:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/video-trimming:latest

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Push to ECR
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/video-trimming:latest
```

### 2. Configure AWS Systems Manager Parameters

Store sensitive configuration in AWS Systems Manager Parameter Store:

```bash
# SQS Queue URL
aws ssm put-parameter \
  --name "/video-trimming/sqs-queue-url" \
  --value "https://sqs.us-east-1.amazonaws.com/YOUR_ACCOUNT_ID/your-queue-name" \
  --type "SecureString"

# DynamoDB Tables
aws ssm put-parameter \
  --name "/video-trimming/podcast-metadata-table" \
  --value "PodcastEpisodeStore" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/quotes-table" \
  --value "TranscriptQuoteStore" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/chunk-table" \
  --value "TranscriptChunkStore" \
  --type "String"

# S3 Buckets
aws ssm put-parameter \
  --name "/video-trimming/video-bucket" \
  --value "your-video-bucket" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/summary-transcript-bucket" \
  --value "your-summary-transcript-bucket" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/video-quotes-chunk-bucket" \
  --value "your-video-quotes-bucket" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/chunk-video-bucket" \
  --value "your-chunk-video-bucket" \
  --type "String"

aws ssm put-parameter \
  --name "/video-trimming/video-summary-bucket" \
  --value "your-video-summary-bucket" \
  --type "String"
```

### 3. Update ECS Task Definition

Update the `ecs-task-definition.json` file:
- Replace `YOUR_ACCOUNT_ID` with your AWS account ID
- Update IAM role ARNs
- Adjust resource allocation (CPU/memory) as needed

### 4. Register Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json
```

### 5. Create or Update ECS Service

Update the `ecs-service-definition.json` file:
- Replace subnet IDs with your private subnet IDs
- Replace security group ID with appropriate security group
- Adjust service configuration as needed

```bash
aws ecs create-service \
  --cli-input-json file://ecs-service-definition.json
```

## Monitoring and Logs

### CloudWatch Logs
- Log Group: `/ecs/video-trimming`
- Logs are automatically forwarded from the container

### Health Checks
- The container includes a health check that verifies boto3 connectivity
- ECS will restart unhealthy containers automatically

### Metrics
Monitor the following CloudWatch metrics:
- ECS Service metrics (CPU, Memory utilization)
- SQS queue metrics (Messages available, processing time)
- Custom application metrics (if implemented)

## Scaling Configuration

### Auto Scaling
Configure ECS Service Auto Scaling based on:
- CPU utilization
- Memory utilization  
- SQS queue depth

### Resource Limits
Current configuration:
- **CPU**: 2048 (2 vCPU)
- **Memory**: 4096 MB (4 GB)
- **Concurrent Processing**: 3 jobs max

Adjust these based on your workload requirements.

## Security Considerations

1. **Network**: Deploy in private subnets with NAT Gateway for internet access
2. **IAM**: Use least privilege principles for task roles
3. **Secrets**: Store sensitive data in Parameter Store or Secrets Manager
4. **Logging**: Enable VPC Flow Logs and CloudTrail
5. **Container**: Application runs as non-root user

## Troubleshooting

### Common Issues

1. **Task fails to start**
   - Check IAM permissions
   - Verify ECR image accessibility
   - Review CloudWatch logs

2. **High memory usage**
   - Monitor video processing workloads
   - Consider increasing memory allocation
   - Implement memory cleanup in application

3. **SQS message processing errors**
   - Verify queue permissions
   - Check message format
   - Review dead letter queue configuration

### Log Analysis
Use CloudWatch Insights to query logs:
```sql
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

## Cost Optimization

1. **Spot Instances**: Consider using Fargate Spot for non-critical workloads
2. **Right-sizing**: Monitor resource utilization and adjust accordingly
3. **Scheduled Scaling**: Scale down during low-usage periods
4. **Storage**: Use S3 lifecycle policies to manage video storage costs

## Maintenance

1. **Regular Updates**: Keep base images and dependencies updated
2. **Monitoring**: Set up alarms for key metrics
3. **Backup**: Ensure DynamoDB and S3 data is properly backed up
4. **Testing**: Implement automated testing for deployments
