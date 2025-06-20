#!/usr/bin/env python3
"""
ECS SSL Configuration Validator
Validates that SSL configuration will work in ECS/Docker environment
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_docker_ssl_config():
    """Check SSL configuration in Docker context."""
    print("🐳 Testing SSL Configuration in Docker Environment")
    print("=" * 55)
    
    # Test if we can build the Docker image
    print("🔨 Testing Docker build with SSL configuration...")
    try:
        result = subprocess.run([
            "docker", "build", "-t", "video-trimming-ssl-test", "."
        ], capture_output=True, text=True, cwd=".")
        
        if result.returncode == 0:
            print("✅ Docker image builds successfully with SSL configuration")
        else:
            print(f"❌ Docker build failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Docker build test failed: {e}")
        return False
    
    # Test SSL configuration inside Docker container
    print("🧪 Testing SSL configuration inside Docker container...")
    try:
        # Run SSL test inside the container
        ssl_test_cmd = '''
python -c "
import ssl
import certifi
import os
import boto3
from src.utils.aws_clients import configure_ssl_environment

print('Container SSL Test:')
print('SSL_CERT_FILE:', os.environ.get('SSL_CERT_FILE', 'Not set'))
print('REQUESTS_CA_BUNDLE:', os.environ.get('REQUESTS_CA_BUNDLE', 'Not set'))

# Test certificate bundle
cert_path = certifi.where()
print('Certifi bundle:', cert_path)

# Test SSL configuration
configure_ssl_environment()
print('SSL environment configured')

# Test SSL context
context = ssl.create_default_context()
print('SSL context created successfully')

print('✅ Container SSL test passed')
"
'''
        
        result = subprocess.run([
            "docker", "run", "--rm", 
            "-e", "AWS_DEFAULT_REGION=us-east-1",
            "video-trimming-ssl-test",
            "sh", "-c", ssl_test_cmd
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ SSL configuration works inside Docker container")
            print("Container output:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"   {line}")
        else:
            print(f"❌ Container SSL test failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Container SSL test failed: {e}")
        return False
    
    return True

def validate_ecs_task_definition():
    """Validate ECS task definition includes SSL configuration."""
    print("\n📋 Validating ECS Task Definition SSL Configuration")
    print("=" * 55)
    
    try:
        with open('ecs-task-definition.json', 'r') as f:
            task_def = json.load(f)
        
        # Check for SSL environment variables
        container_def = task_def['containerDefinitions'][0]
        env_vars = {env['name']: env['value'] for env in container_def.get('environment', [])}
        
        required_ssl_vars = [
            'SSL_CERT_FILE',
            'SSL_CERT_DIR', 
            'REQUESTS_CA_BUNDLE',
            'CURL_CA_BUNDLE',
            'PYTHONHTTPSVERIFY'
        ]
        
        missing_vars = []
        for var in required_ssl_vars:
            if var in env_vars:
                print(f"✅ {var}: {env_vars[var]}")
            else:
                missing_vars.append(var)
                print(f"❌ {var}: Missing")
        
        if missing_vars:
            print(f"\n❌ Missing SSL environment variables: {missing_vars}")
            return False
        else:
            print("\n✅ All SSL environment variables configured in ECS task definition")
        
        # Check health check includes SSL validation
        health_check = container_def.get('healthCheck', {})
        health_cmd = ' '.join(health_check.get('command', []))
        
        if 'ssl' in health_cmd.lower() and 'configure_ssl_environment' in health_cmd:
            print("✅ Health check includes SSL validation")
        else:
            print("⚠️ Health check may not include proper SSL validation")
        
        return len(missing_vars) == 0
        
    except FileNotFoundError:
        print("❌ ecs-task-definition.json not found")
        return False
    except Exception as e:
        print(f"❌ Error validating task definition: {e}")
        return False

def validate_dockerfile():
    """Validate Dockerfile includes SSL configuration."""
    print("\n🐳 Validating Dockerfile SSL Configuration")
    print("=" * 45)
    
    try:
        with open('Dockerfile', 'r') as f:
            dockerfile_content = f.read()
        
        ssl_checks = [
            ('ca-certificates', 'CA certificates package installed'),
            ('update-ca-certificates', 'CA certificates updated'),
            ('SSL_CERT_FILE', 'SSL_CERT_FILE environment variable set'),
            ('REQUESTS_CA_BUNDLE', 'REQUESTS_CA_BUNDLE environment variable set'),
            ('PYTHONHTTPSVERIFY', 'PYTHONHTTPSVERIFY environment variable set'),
            ('configure_ssl_environment', 'SSL configuration in health check')
        ]
        
        all_passed = True
        for check, description in ssl_checks:
            if check in dockerfile_content:
                print(f"✅ {description}")
            else:
                print(f"❌ {description}")
                all_passed = False
        
        return all_passed
        
    except FileNotFoundError:
        print("❌ Dockerfile not found")
        return False
    except Exception as e:
        print(f"❌ Error validating Dockerfile: {e}")
        return False

def main():
    """Main validation function."""
    print("🔒 ECS SSL Configuration Validation")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Dockerfile validation
    if validate_dockerfile():
        tests_passed += 1
    
    # Test 2: ECS task definition validation  
    if validate_ecs_task_definition():
        tests_passed += 1
    
    # Test 3: Docker SSL test
    if check_docker_ssl_config():
        tests_passed += 1
    
    print(f"\n📊 Validation Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ECS SSL configuration is ready for deployment!")
        print("\n📋 Your ECS deployment includes:")
        print("   ✅ Proper SSL certificate bundle configuration")
        print("   ✅ Required environment variables in task definition")
        print("   ✅ SSL validation in Docker health checks")
        print("   ✅ Working SSL configuration in container environment")
        print(f"\n🚀 Deploy with: ./deploy_ecs.sh")
        return True
    else:
        print("❌ ECS SSL configuration needs fixes before deployment")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
