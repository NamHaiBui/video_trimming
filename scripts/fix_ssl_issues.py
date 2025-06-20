#!/usr/bin/env python3
"""
SSL Troubleshooting and Fix Script for Video Trimming Service
Diagnoses and attempts to fix common SSL/TLS issues that cause:
"EOF occurred in violation of protocol (_ssl.c:2427)"
"""

import os
import sys
import ssl
import urllib3
import requests
import certifi
import subprocess
import platform
from pathlib import Path


class SSLTroubleshooter:
    """Diagnose and fix SSL/TLS issues."""
    
    def __init__(self):
        self.issues_found = []
        self.fixes_applied = []
    
    def print_status(self, message):
        print(f"🔍 {message}")
    
    def print_success(self, message):
        print(f"✅ {message}")
    
    def print_warning(self, message):
        print(f"⚠️  {message}")
    
    def print_error(self, message):
        print(f"❌ {message}")
    
    def check_python_ssl_support(self):
        """Check Python's SSL support."""
        self.print_status("Checking Python SSL support...")
        
        try:
            import ssl
            self.print_success(f"SSL module available: {ssl.OPENSSL_VERSION}")
            
            # Check SSL context
            context = ssl.create_default_context()
            self.print_success(f"Default SSL context created successfully")
            
            # Check protocol support
            protocols = []
            for protocol in ['TLSv1_2', 'TLSv1_3']:
                if hasattr(ssl, f'PROTOCOL_{protocol}'):
                    protocols.append(protocol)
            
            if protocols:
                self.print_success(f"Supported TLS protocols: {', '.join(protocols)}")
            else:
                self.print_warning("No modern TLS protocols found")
                self.issues_found.append("Limited TLS protocol support")
                
        except Exception as e:
            self.print_error(f"SSL module issues: {e}")
            self.issues_found.append(f"SSL module error: {e}")
    
    def check_certificate_bundle(self):
        """Check SSL certificate bundle."""
        self.print_status("Checking SSL certificate bundle...")
        
        try:
            cert_path = certifi.where()
            if os.path.exists(cert_path):
                self.print_success(f"Certificate bundle found: {cert_path}")
                
                # Check bundle size (should be substantial)
                size = os.path.getsize(cert_path)
                if size > 100000:  # At least 100KB
                    self.print_success(f"Certificate bundle size OK: {size:,} bytes")
                else:
                    self.print_warning(f"Certificate bundle seems small: {size:,} bytes")
                    self.issues_found.append("Small certificate bundle")
            else:
                self.print_error(f"Certificate bundle not found: {cert_path}")
                self.issues_found.append("Missing certificate bundle")
                
        except Exception as e:
            self.print_error(f"Certificate bundle check failed: {e}")
            self.issues_found.append(f"Certificate bundle error: {e}")
    
    def check_urllib3_version(self):
        """Check urllib3 version compatibility."""
        self.print_status("Checking urllib3 version...")
        
        try:
            import urllib3
            # Try to get version using different methods
            version = "unknown"
            
            try:
                import pkg_resources
                version = pkg_resources.get_distribution('urllib3').version
            except Exception:
                try:
                    import importlib.metadata
                    version = importlib.metadata.version('urllib3')
                except Exception:
                    # Fallback: check if we can at least import urllib3
                    version = "installed (version unknown)"
            
            self.print_success(f"urllib3 version: {version}")
            
            if version not in ["unknown", "installed (version unknown)"]:
                try:
                    major, minor = map(int, version.split('.')[:2])
                    if major == 2 and minor >= 0:
                        self.print_success("urllib3 2.x detected - should work with modern SSL")
                    elif major == 1 and minor >= 26:
                        self.print_success("urllib3 1.26+ detected - good SSL support")
                    else:
                        self.print_warning(f"urllib3 version may be outdated: {version}")
                        self.issues_found.append(f"Outdated urllib3: {version}")
                except ValueError:
                    self.print_warning(f"Could not parse urllib3 version: {version}")
            else:
                self.print_warning("Could not determine urllib3 version - assuming it needs update")
                self.issues_found.append("urllib3 version unknown")
                
        except Exception as e:
            self.print_error(f"urllib3 check failed: {e}")
            self.issues_found.append(f"urllib3 error: {e}")
    
    def test_aws_connection(self):
        """Test connection to AWS services."""
        self.print_status("Testing AWS service connectivity...")
        
        # Test endpoints
        endpoints = [
            "https://s3.us-east-1.amazonaws.com",
            "https://dynamodb.us-east-1.amazonaws.com",
            "https://sqs.us-east-1.amazonaws.com"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10, verify=True)
                service = endpoint.split('.')[0].split('//')[-1]
                if response.status_code in [200, 403, 404]:  # Any valid response
                    self.print_success(f"✓ {service} connectivity OK")
                else:
                    self.print_warning(f"⚠ {service} returned status {response.status_code}")
                    
            except requests.exceptions.SSLError as e:
                service = endpoint.split('.')[0].split('//')[-1]
                self.print_error(f"✗ {service} SSL error: {e}")
                self.issues_found.append(f"SSL error connecting to {service}")
                
            except requests.exceptions.RequestException as e:
                service = endpoint.split('.')[0].split('//')[-1]
                self.print_warning(f"⚠ {service} connection issue: {e}")
    
    def fix_certificate_issues(self):
        """Attempt to fix certificate issues."""
        self.print_status("Attempting to fix certificate issues...")
        
        try:
            # Update certificates via pip
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'certifi'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("Updated certifi package")
                self.fixes_applied.append("Updated certifi")
            else:
                self.print_warning(f"Failed to update certifi: {result.stderr}")
                
        except Exception as e:
            self.print_warning(f"Could not update certifi: {e}")
    
    def fix_urllib3_issues(self):
        """Attempt to fix urllib3 issues."""
        self.print_status("Attempting to fix urllib3 issues...")
        
        try:
            # Update urllib3 to a compatible version
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'urllib3>=1.26.18,<3.0.0'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.print_success("Updated urllib3 package")
                self.fixes_applied.append("Updated urllib3")
            else:
                self.print_warning(f"Failed to update urllib3: {result.stderr}")
                
        except Exception as e:
            self.print_warning(f"Could not update urllib3: {e}")
    
    def update_boto3_packages(self):
        """Update boto3 and related packages."""
        self.print_status("Updating AWS packages...")
        
        packages = ['boto3', 'botocore', 'requests']
        
        for package in packages:
            try:
                result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', package], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.print_success(f"Updated {package}")
                    self.fixes_applied.append(f"Updated {package}")
                else:
                    self.print_warning(f"Failed to update {package}: {result.stderr}")
                    
            except Exception as e:
                self.print_warning(f"Could not update {package}: {e}")
    
    def provide_recommendations(self):
        """Provide manual fix recommendations."""
        self.print_status("Additional recommendations...")
        
        print("\n🔧 Manual fixes you can try:")
        print("1. Update your system's CA certificates:")
        
        if platform.system() == "Linux":
            print("   sudo apt-get update && sudo apt-get install ca-certificates")
            print("   # or")
            print("   sudo yum update ca-certificates")
        elif platform.system() == "Darwin":
            print("   brew install ca-certificates")
        
        print("\n2. Set environment variables:")
        print("   export SSL_CERT_FILE=$(python -m certifi)")
        print("   export REQUESTS_CA_BUNDLE=$(python -m certifi)")
        
        print("\n3. Disable SSL warnings (temporary):")
        print("   export PYTHONHTTPSVERIFY=0")
        print("   # WARNING: This reduces security!")
        
        print("\n4. Try using a different AWS region:")
        print("   export AWS_DEFAULT_REGION=us-west-2")
        
        print("\n5. Check your network/firewall settings")
        print("   - Ensure HTTPS (port 443) is not blocked")
        print("   - Check for corporate proxy settings")
    
    def run_diagnostics(self):
        """Run all diagnostic checks."""
        print("=" * 60)
        print("🔍 SSL/TLS Troubleshooting for Video Trimming Service")
        print("=" * 60)
        
        self.check_python_ssl_support()
        print()
        
        self.check_certificate_bundle()
        print()
        
        self.check_urllib3_version()
        print()
        
        self.test_aws_connection()
        print()
        
        # Summary
        print("=" * 60)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        if self.issues_found:
            print("❌ Issues found:")
            for issue in self.issues_found:
                print(f"   - {issue}")
        else:
            print("✅ No major issues detected")
        
        return len(self.issues_found) == 0
    
    def apply_fixes(self):
        """Apply automatic fixes."""
        print("\n🔧 APPLYING FIXES")
        print("=" * 60)
        
        self.fix_certificate_issues()
        self.fix_urllib3_issues()
        self.update_boto3_packages()
        
        if self.fixes_applied:
            print("\n✅ Fixes applied:")
            for fix in self.fixes_applied:
                print(f"   - {fix}")
            print("\n⚠️  Please restart your application to apply changes")
        else:
            print("\n⚠️  No automatic fixes could be applied")
        
        self.provide_recommendations()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SSL troubleshooting for Video Trimming Service')
    parser.add_argument('--check-only', action='store_true', help='Only run diagnostics, do not apply fixes')
    parser.add_argument('--apply-fixes', action='store_true', help='Apply automatic fixes')
    
    args = parser.parse_args()
    
    troubleshooter = SSLTroubleshooter()
    
    # Always run diagnostics
    healthy = troubleshooter.run_diagnostics()
    
    if not args.check_only and (args.apply_fixes or not healthy):
        troubleshooter.apply_fixes()
    
    return 0 if healthy else 1


if __name__ == '__main__':
    sys.exit(main())
