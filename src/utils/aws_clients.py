"""
AWS client configuration utilities for LocalStack and production environments.
"""

import os
import boto3
from botocore.config import Config


def get_aws_config():
    """Get AWS configuration for LocalStack or production."""
    # Check if we're using LocalStack
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
    
    if endpoint_url:
        # LocalStack configuration
        return {
            'endpoint_url': endpoint_url,
            'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID', 'test'),
            'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY', 'test'),
            'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
            'config': Config(
                signature_version='s3v4',
                retries={'max_attempts': 3},
                max_pool_connections=10
            )
        }
    else:
        # Production configuration
        return {
            'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
            'config': Config(
                retries={'max_attempts': 3},
                max_pool_connections=10
            )
        }


def get_dynamodb_resource():
    """Get DynamoDB resource configured for LocalStack or production."""
    config = get_aws_config()
    return boto3.resource('dynamodb', **config)


def get_dynamodb_client():
    """Get DynamoDB client configured for LocalStack or production."""
    config = get_aws_config()
    return boto3.client('dynamodb', **config)


def get_s3_client():
    """Get S3 client configured for LocalStack or production."""
    config = get_aws_config()
    return boto3.client('s3', **config)


def get_s3_resource():
    """Get S3 resource configured for LocalStack or production."""
    config = get_aws_config()
    return boto3.resource('s3', **config)
