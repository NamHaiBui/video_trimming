"""
AWS client configuration utilities for production environments.
"""

import os
import boto3
import ssl
import certifi
from botocore.config import Config
from urllib3.util.retry import Retry
from botocore.exceptions import SSLError, EndpointConnectionError, ConnectionError as BotocoreConnectionError
import logging
import time

# Set up logging for this module
logger = logging.getLogger(__name__)


def configure_ssl_environment():
    """Configure SSL environment variables for proper certificate handling."""
    try:
        # Get the certifi certificate bundle path
        cert_bundle = certifi.where()
        
        # Set environment variables for SSL certificate bundle
        os.environ['SSL_CERT_FILE'] = cert_bundle
        os.environ['SSL_CERT_DIR'] = os.path.dirname(cert_bundle)
        os.environ['REQUESTS_CA_BUNDLE'] = cert_bundle
        os.environ['CURL_CA_BUNDLE'] = cert_bundle
        
        logger.info(f"SSL certificate bundle configured: {cert_bundle}")
        return True
    except Exception as e:
        logger.error(f"Failed to configure SSL environment: {e}")
        return False


def get_aws_config():
    """Get AWS configuration for production with enhanced SSL handling."""
    # Configure SSL environment first
    configure_ssl_environment()
    
    return {
        'region_name': os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
        'config': Config(
            retries={
                'max_attempts': 5,
                'mode': 'adaptive'
            },
            max_pool_connections=10,
            # Connection timeout settings to handle SSL issues
            connect_timeout=60,
            read_timeout=60
        )
    }


def verify_ssl_configuration():
    """Verify SSL configuration and certificate bundle."""
    try:
        # Check if certifi bundle exists
        cert_bundle = certifi.where()
        if os.path.exists(cert_bundle):
            logger.info(f"SSL certificate bundle found: {cert_bundle}")
            return True
        else:
            logger.warning(f"SSL certificate bundle not found at: {cert_bundle}")
            return False
    except Exception as e:
        logger.error(f"Error verifying SSL configuration: {e}")
        return False


def create_aws_client_with_retries(service_name, **kwargs):
    """Create AWS client with SSL error handling and retries."""
    config = get_aws_config()
    
    # Verify SSL before creating client
    if not verify_ssl_configuration():
        logger.warning("SSL configuration issues detected")
    
    # Add SSL-specific session configuration
    session = boto3.Session()
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Try with default SSL settings first
            if service_name == 'dynamodb':
                return session.resource('dynamodb', **config)
            elif service_name == 'dynamodb-client':
                return session.client('dynamodb', **config)
            elif service_name == 's3-resource':
                return session.resource('s3', **config)
            else:  # s3, sqs, etc.
                return session.client(service_name, **config)
                
        except (SSLError, EndpointConnectionError, BotocoreConnectionError) as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {service_name}: {e}")
            
            # If this is an SSL issue, try with additional configuration
            if "SSL" in str(e) or "certificate" in str(e).lower():
                logger.info("Attempting to fix SSL configuration...")
                configure_ssl_environment()
                
                # Create a new config with SSL context
                ssl_config = config.copy()
                ssl_config['config'] = Config(
                    retries={
                        'max_attempts': 5,
                        'mode': 'adaptive'
                    },
                    max_pool_connections=10,
                    connect_timeout=60,
                    read_timeout=60,
                    # Add SSL-specific configuration
                    parameter_validation=False
                )
                
                try:
                    if service_name == 'dynamodb':
                        return session.resource('dynamodb', **ssl_config)
                    elif service_name == 'dynamodb-client':
                        return session.client('dynamodb', **ssl_config)
                    elif service_name == 's3-resource':
                        return session.resource('s3', **ssl_config)
                    else:  # s3, sqs, etc.
                        return session.client(service_name, **ssl_config)
                except Exception as ssl_retry_error:
                    logger.error(f"SSL retry also failed: {ssl_retry_error}")
            
            if attempt == max_retries - 1:
                logger.error(f"Failed to create {service_name} client after {max_retries} attempts")
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as e:
            logger.error(f"Unexpected error creating {service_name} client: {e}")
            raise


def get_dynamodb_resource():
    """Get DynamoDB resource configured for production with SSL error handling."""
    return create_aws_client_with_retries('dynamodb')


def get_dynamodb_client():
    """Get DynamoDB client configured for production with SSL error handling."""
    return create_aws_client_with_retries('dynamodb-client')


def get_s3_client():
    """Get S3 client configured for production with SSL error handling."""
    return create_aws_client_with_retries('s3')


def get_s3_resource():
    """Get S3 resource configured for production with SSL error handling."""
    return create_aws_client_with_retries('s3-resource')


def get_sqs_client():
    """Get SQS client configured for production with SSL error handling."""
    return create_aws_client_with_retries('sqs')
