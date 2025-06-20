#!/usr/bin/env python3
"""
S3 Bucket Creation Script for Video Trimming Project

This script ensures all required S3 buckets are created for the video trimming application.
It reads bucket names from environment variables and creates them if they don't exist.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_status(message):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")

def print_success(message):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")

def print_warning(message):
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")

def print_error(message):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")

def get_bucket_names():
    """Get all bucket names from environment variables"""
    buckets = {
        # Source Data Buckets
        'AUDIO_BUCKET': os.getenv('AUDIO_BUCKET', 'pd-audio-storage-test'),
        'VIDEO_BUCKET': os.getenv('VIDEO_BUCKET', 'pd-video-storage-test'),
        'SUMMARY_TRANSCRIPT_BUCKET': os.getenv('SUMMARY_TRANSCRIPT_BUCKET', 'pd-summary-transcript-storage'),
        
        # Generated Content Buckets
        'VIDEO_QUOTES_CHUNK_BUCKET': os.getenv('VIDEO_QUOTES_CHUNK_BUCKET', 'pd-video-quotes-storage'),
        'CHUNK_VIDEO_BUCKET': os.getenv('CHUNK_VIDEO_BUCKET', 'pd-video-chunks-storage'),
        'VIDEO_SUMMARY_BUCKET': os.getenv('VIDEO_SUMMARY_BUCKET', 'pd-video-summary-storage'),
    }
    return buckets

def check_aws_credentials():
    """Check if AWS credentials are properly configured"""
    try:
        # Try to create a session and get caller identity
        session = boto3.Session()
        sts = session.client('sts')
        response = sts.get_caller_identity()
        print_success(f"AWS credentials validated for account: {response.get('Account')}")
        return True
    except NoCredentialsError:
        print_error("AWS credentials not found. Please configure your AWS credentials.")
        print_error("Run: aws configure")
        return False
    except Exception as e:
        print_error(f"Error checking AWS credentials: {e}")
        return False

def get_aws_region():
    """Get AWS region from environment or default"""
    region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    print_status(f"Using AWS region: {region}")
    return region

def bucket_exists(s3_client, bucket_name):
    """Check if a bucket exists and is accessible"""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            return False
        elif error_code == '403':
            print_warning(f"Access denied to bucket '{bucket_name}' - it may exist but you don't have permission")
            return True  # Assume it exists but we can't access it
        else:
            print_error(f"Error checking bucket '{bucket_name}': {e}")
            return False

def create_bucket(s3_client, bucket_name, region):
    """Create an S3 bucket"""
    try:
        if region == 'us-east-1':
            # us-east-1 is the default region and doesn't require LocationConstraint
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        
        print_success(f"Created bucket: {bucket_name}")
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'BucketAlreadyExists':
            print_warning(f"Bucket '{bucket_name}' already exists (owned by someone else)")
        elif error_code == 'BucketAlreadyOwnedByYou':
            print_success(f"Bucket '{bucket_name}' already exists and is owned by you")
        else:
            print_error(f"Error creating bucket '{bucket_name}': {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error creating bucket '{bucket_name}': {e}")
        return False
    
    return True

def set_bucket_public_access_policy(s3_client, bucket_name):
    """Set bucket policy to allow public read access for generated content"""
    # Only set public access for generated content buckets
    public_buckets = [
        'pd-video-quotes-storage',
        'pd-video-chunks-storage', 
        'pd-video-summary-storage'
    ]
    
    if not any(public_bucket in bucket_name for public_bucket in public_buckets):
        return True  # Skip non-public buckets
    
    try:
        # First, disable block public access
        s3_client.delete_public_access_block(Bucket=bucket_name)
        
        # Set bucket policy for public read access
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                }
            ]
        }
        
        import json
        s3_client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )
        
        print_success(f"Set public read policy for bucket: {bucket_name}")
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'NoSuchPublicAccessBlockConfiguration':
            # This is expected for new buckets
            pass
        else:
            print_warning(f"Could not set public access policy for '{bucket_name}': {e}")
    except Exception as e:
        print_warning(f"Unexpected error setting policy for '{bucket_name}': {e}")
    
    return True

def create_all_buckets():
    """Main function to create all required S3 buckets"""
    print_status("Starting S3 bucket creation process...")
    
    # Check AWS credentials
    if not check_aws_credentials():
        return False
    
    # Get AWS region
    region = get_aws_region()
    
    # Get bucket names
    buckets = get_bucket_names()
    
    print_status(f"Found {len(buckets)} buckets to check/create:")
    for env_var, bucket_name in buckets.items():
        print(f"  {env_var}: {bucket_name}")
    
    # Create S3 client
    try:
        s3_client = boto3.client('s3', region_name=region)
    except Exception as e:
        print_error(f"Failed to create S3 client: {e}")
        return False
    
    # Process each bucket
    success_count = 0
    total_count = len(buckets)
    
    for env_var, bucket_name in buckets.items():
        print_status(f"Processing bucket: {bucket_name}")
        
        if bucket_exists(s3_client, bucket_name):
            print_success(f"Bucket '{bucket_name}' already exists")
            success_count += 1
        else:
            print_status(f"Creating bucket: {bucket_name}")
            if create_bucket(s3_client, bucket_name, region):
                success_count += 1
                # Set public access policy for generated content buckets
                set_bucket_public_access_policy(s3_client, bucket_name)
        
        print()  # Empty line for readability
    
    # Summary
    print("=" * 50)
    print_success(f"Bucket creation complete: {success_count}/{total_count} buckets ready")
    
    if success_count == total_count:
        print_success("All S3 buckets are ready for the video trimming application!")
        return True
    else:
        print_warning(f"{total_count - success_count} buckets could not be created/verified")
        return False

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("S3 Bucket Creation Script for Video Trimming Project")
        print()
        print("This script creates all required S3 buckets for the video trimming application.")
        print("Bucket names are read from environment variables or use default values.")
        print()
        print("Usage: python create_s3_buckets.py")
        print()
        print("Environment variables:")
        buckets = get_bucket_names()
        for env_var, default_name in buckets.items():
            print(f"  {env_var} (default: {default_name})")
        return
    
    success = create_all_buckets()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
