#!/usr/bin/env python3
"""
SSL Validation Test for Video Trimming Service
Tests that all AWS services can connect without SSL errors.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.aws_clients import (
    get_sqs_client, 
    get_s3_client, 
    get_dynamodb_client,
    configure_ssl_environment
)
from utils.config import QUEUE_URL

def test_ssl_configuration():
    """Test SSL configuration for all AWS services."""
    print("🧪 Testing SSL Configuration for AWS Services")
    print("=" * 50)
    
    # Configure SSL environment
    print("🔧 Configuring SSL environment...")
    if configure_ssl_environment():
        print("✅ SSL environment configured")
    else:
        print("❌ SSL environment configuration failed")
        return False
    
    tests_passed = 0
    total_tests = 0
    
    # Test SQS
    total_tests += 1
    print("\n🔍 Testing SQS connection...")
    try:
        sqs = get_sqs_client()
        response = sqs.list_queues()
        queues = response.get('QueueUrls', [])
        print(f"✅ SQS: Connected successfully, found {len(queues)} queues")
        
        # Test specific queue if configured
        if QUEUE_URL:
            print(f"🔍 Testing specific queue: {QUEUE_URL}")
            response = sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1
            )
            messages = response.get('Messages', [])
            print(f"✅ Queue poll successful, {len(messages)} messages found")
        
        tests_passed += 1
    except Exception as e:
        print(f"❌ SQS test failed: {e}")
    
    # Test S3
    total_tests += 1
    print("\n🔍 Testing S3 connection...")
    try:
        s3 = get_s3_client()
        response = s3.list_buckets()
        buckets = response.get('Buckets', [])
        print(f"✅ S3: Connected successfully, found {len(buckets)} buckets")
        tests_passed += 1
    except Exception as e:
        print(f"❌ S3 test failed: {e}")
    
    # Test DynamoDB
    total_tests += 1
    print("\n🔍 Testing DynamoDB connection...")
    try:
        dynamodb = get_dynamodb_client()
        response = dynamodb.list_tables()
        tables = response.get('TableNames', [])
        print(f"✅ DynamoDB: Connected successfully, found {len(tables)} tables")
        tests_passed += 1
    except Exception as e:
        print(f"❌ DynamoDB test failed: {e}")
    
    # Summary
    print(f"\n📊 Test Results: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All SSL tests passed! Your video trimming service is ready to run.")
        return True
    else:
        print("❌ Some tests failed. Please check your AWS configuration and network connectivity.")
        return False


if __name__ == "__main__":
    success = test_ssl_configuration()
    sys.exit(0 if success else 1)
