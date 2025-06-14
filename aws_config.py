
"""
AWS Configuration for real data retrieval (not LocalStack)
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv()

class AWSConfig:
    """Configuration for AWS services"""
    
    @staticmethod
    def configure_for_real_aws():
        """Configure environment for real AWS access"""
        
        # Remove LocalStack-specific settings
        localstack_vars = [
            'AWS_ENDPOINT_URL',
            'LOCALSTACK_AUTH_TOKEN'
        ]
        
        for var in localstack_vars:
            if var in os.environ:
                print(f"🔧 Removing {var} for real AWS access")
                del os.environ[var]
        
        # Ensure AWS region is set
        if not os.getenv('AWS_DEFAULT_REGION'):
            os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
            print("🔧 Set AWS_DEFAULT_REGION to us-east-1")
        
        # Verify AWS credentials are available
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        print(access_key, secret_key)
        if not access_key or not secret_key:
            print("⚠️  AWS credentials not found in environment")
            print("   Make sure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set")
            print("   Or use AWS CLI: aws configure")
            return False
        
        print("✅ AWS credentials found")
        return True
    
    @staticmethod
    def get_aws_config() -> Dict[str, Any]:
        """Get AWS configuration"""
        return {
            'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
            'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
            'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY')
        }
    
    @staticmethod
    def get_resource_names() -> Dict[str, str]:
        """Get AWS resource names"""
        return {
            # DynamoDB Tables
            'podcast_table': os.getenv('PODCAST_METADATA_TABLE', 'PodcastEpisodeStore'),
            'quotes_table': os.getenv('QUOTES_TABLE', 'TranscriptQuoteStore'),
            'chunks_table': os.getenv('CHUNK_TABLE', 'TranscriptChunkStore'),
            'summary_transcript_bucket': os.getenv('SUMMARY_TRANSCRIPT_BUCKET', 'pd-summary-transcript-storage'),
        }
    
    @staticmethod
    def print_config():
        """Print current AWS configuration"""
        print("AWS Configuration:")
        print("=" * 30)
        
        config = AWSConfig.get_aws_config()
        resources = AWSConfig.get_resource_names()
        
        print(f"Region: {config['region']}")
        print(f"Access Key: {config['access_key_id'][:10]}..." if config['access_key_id'] else "Access Key: Not set")
        print(f"Secret Key: {'*' * 10}..." if config['secret_access_key'] else "Secret Key: Not set")
        
        print("\nDynamoDB Tables:")
        print(f"  - Podcast: {resources['podcast_table']}")
        print(f"  - Quotes: {resources['quotes_table']}")
        print(f"  - Chunks: {resources['chunks_table']}")
        
        print("\nS3 Buckets (Source):")
        print(f"  - Audio: {resources['audio_bucket']}")
        print(f"  - Video: {resources['video_bucket']}")
        print(f"  - Transcripts: {resources['summary_transcript_bucket']}")
        
        print("\nS3 Buckets (Generated):")
        print(f"  - Audio Quotes: {resources['audio_quotes_bucket']}")
        print(f"  - Video Quotes: {resources['video_quotes_bucket']}")
        print(f"  - Video Chunks: {resources['chunk_video_bucket']}")
        print(f"  - Audio Chunks: {resources['audio_chunk_bucket']}")


if __name__ == '__main__':
    AWSConfig.print_config()
