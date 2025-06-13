#!/usr/bin/env python3
"""
Dependency checker for the Video Trimming Project.
This script validates that all required dependencies are installed and configured correctly.
"""

import os
import sys
import subprocess
import pkg_resources
import shutil
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import importlib.util


class DependencyChecker:
    """Check all project dependencies."""
    
    def __init__(self):
        self.results = {
            'python': {'status': False, 'details': {}},
            'system_packages': {'status': False, 'details': {}},
            'python_packages': {'status': False, 'details': {}},
            'ffmpeg': {'status': False, 'details': {}},
            'environment': {'status': False, 'details': {}},
            'aws': {'status': False, 'details': {}},
            'project_structure': {'status': False, 'details': {}},
        }
        
        # Required Python packages from requirements.txt
        self.required_packages = [
            'ffmpeg-python>=0.2.0',
            'boto3>=1.38.0',
            'joblib>=1.3.0',
            'python-dateutil>=2.9.0',
            'python-dotenv>=1.0.0',
        ]
        
        # Development packages
        self.dev_packages = [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'black>=23.7.0',
            'flake8>=6.0.0',
            'mypy>=1.5.0',
            'pydub>=0.25.1',
        ]
        
        # Required environment variables
        self.required_env_vars = [
            'PODCAST_METADATA_TABLE',
            'QUOTES_TABLE',
            'CHUNK_TABLE',
            'AUDIO_BUCKET',
            'VIDEO_BUCKET',
            'SUMMARY_TRANSCRIPT_BUCKET',
        ]
        
        # Optional environment variables with defaults
        self.optional_env_vars = {
            'AWS_DEFAULT_REGION': 'us-east-1',
            'LOG_LEVEL': 'INFO',
            'MAX_CONCURRENT_PROCESSING': '5',
            'TEMP_DIR': '/tmp/video_processing',
        }
    
    def print_status(self, message: str):
        print(f"[INFO] {message}")
    
    def print_success(self, message: str):
        print(f"[SUCCESS] {message}")
    
    def print_warning(self, message: str):
        print(f"[WARNING] {message}")
    
    def print_error(self, message: str):
        print(f"[ERROR] {message}")
    
    def command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH."""
        return shutil.which(command) is not None
    
    def check_python_version(self) -> bool:
        """Check Python version compatibility."""
        self.print_status("Checking Python version...")
        
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
        
        self.results['python']['details']['version'] = version_str
        self.results['python']['details']['executable'] = sys.executable
        
        # Check if Python 3.8+
        if version_info.major == 3 and version_info.minor >= 8:
            self.print_success(f"✓ Python {version_str} (compatible)")
            self.results['python']['status'] = True
            return True
        else:
            self.print_error(f"✗ Python {version_str} (requires 3.8+)")
            self.results['python']['status'] = False
            return False
    
    def check_system_packages(self) -> bool:
        """Check required system packages."""
        self.print_status("Checking system packages...")
        
        system_checks = {
            'git': self.command_exists('git'),
            'curl': self.command_exists('curl') or self.command_exists('wget'),
            'build_tools': self.command_exists('gcc') or self.command_exists('clang'),
        }
        
        self.results['system_packages']['details'] = system_checks
        
        missing = [pkg for pkg, available in system_checks.items() if not available]
        
        if missing:
            self.print_warning(f"Missing system packages: {', '.join(missing)}")
            self.results['system_packages']['status'] = False
        else:
            self.print_success("✓ All system packages available")
            self.results['system_packages']['status'] = True
        
        return len(missing) == 0
    
    def parse_requirement(self, req_string: str) -> Tuple[str, Optional[str]]:
        """Parse a requirement string to get package name and version."""
        try:
            req = pkg_resources.Requirement.parse(req_string)
            return req.key, str(req.specifier) if req.specifier else None
        except Exception:
            # Fallback parsing
            if '>=' in req_string:
                name, version = req_string.split('>=')
                return name.strip(), f">={version.strip()}"
            else:
                return req_string.strip(), None
    
    def check_python_packages(self, include_dev: bool = False) -> bool:
        """Check Python package dependencies."""
        self.print_status("Checking Python packages...")
        
        packages_to_check = self.required_packages[:]
        if include_dev:
            packages_to_check.extend(self.dev_packages)
        
        installed_packages = {}
        missing_packages = []
        version_conflicts = []
        
        # Get list of installed packages
        try:
            installed_dists = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
        except Exception as e:
            self.print_error(f"Failed to get installed packages: {e}")
            self.results['python_packages']['status'] = False
            return False
        
        for req_string in packages_to_check:
            package_name, version_spec = self.parse_requirement(req_string)
            
            if package_name in installed_dists:
                installed_version = installed_dists[package_name]
                installed_packages[package_name] = installed_version
                
                # Check version compatibility if specified
                if version_spec:
                    try:
                        req = pkg_resources.Requirement.parse(req_string)
                        if installed_version not in req:
                            version_conflicts.append(f"{package_name} {installed_version} (needs {version_spec})")
                    except Exception:
                        # Skip version check if parsing fails
                        pass
            else:
                missing_packages.append(package_name)
        
        self.results['python_packages']['details'] = {
            'installed': installed_packages,
            'missing': missing_packages,
            'conflicts': version_conflicts
        }
        
        if missing_packages:
            self.print_error(f"Missing packages: {', '.join(missing_packages)}")
        
        if version_conflicts:
            self.print_warning(f"Version conflicts: {', '.join(version_conflicts)}")
        
        if not missing_packages and not version_conflicts:
            self.print_success(f"✓ All {len(installed_packages)} Python packages available")
            self.results['python_packages']['status'] = True
            return True
        else:
            self.results['python_packages']['status'] = False
            return False
    
    def check_ffmpeg(self) -> bool:
        """Check FFmpeg installation."""
        self.print_status("Checking FFmpeg installation...")
        
        ffmpeg_path = shutil.which('ffmpeg')
        ffprobe_path = shutil.which('ffprobe')
        
        ffmpeg_details = {
            'ffmpeg_path': ffmpeg_path,
            'ffprobe_path': ffprobe_path,
            'version': None,
        }
        
        if not ffmpeg_path or not ffprobe_path:
            self.print_error("FFmpeg or FFprobe not found in PATH")
            self.results['ffmpeg']['details'] = ffmpeg_details
            self.results['ffmpeg']['status'] = False
            return False
        
        # Get FFmpeg version
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                ffmpeg_details['version'] = version_line
                self.print_success(f"✓ {version_line}")
            else:
                self.print_warning("FFmpeg found but version check failed")
        except Exception as e:
            self.print_warning(f"FFmpeg version check error: {e}")
        
        self.results['ffmpeg']['details'] = ffmpeg_details
        self.results['ffmpeg']['status'] = True
        return True
    
    def check_environment_variables(self) -> bool:
        """Check environment variables."""
        self.print_status("Checking environment variables...")
        
        env_status = {
            'required_present': [],
            'required_missing': [],
            'optional_present': [],
            'optional_missing': [],
        }
        
        # Check required variables
        for var in self.required_env_vars:
            if os.environ.get(var):
                env_status['required_present'].append(var)
            else:
                env_status['required_missing'].append(var)
        
        # Check optional variables
        for var, default in self.optional_env_vars.items():
            if os.environ.get(var):
                env_status['optional_present'].append(var)
            else:
                env_status['optional_missing'].append(var)
        
        self.results['environment']['details'] = env_status
        
        if env_status['required_missing']:
            self.print_error(f"Missing required env vars: {', '.join(env_status['required_missing'])}")
            self.results['environment']['status'] = False
            return False
        else:
            self.print_success(f"✓ All {len(env_status['required_present'])} required env vars present")
            if env_status['optional_missing']:
                self.print_warning(f"Optional env vars using defaults: {', '.join(env_status['optional_missing'])}")
            self.results['environment']['status'] = True
            return True
    
    def check_aws_configuration(self) -> bool:
        """Check AWS configuration."""
        self.print_status("Checking AWS configuration...")
        
        aws_status = {
            'boto3_available': False,
            'credentials_method': None,
            'region': None,
            'can_list_buckets': False,
        }
        
        # Check if boto3 is available and can be imported
        try:
            import boto3
            aws_status['boto3_available'] = True
        except ImportError:
            self.print_error("boto3 not available")
            self.results['aws']['details'] = aws_status
            self.results['aws']['status'] = False
            return False
        
        # Check credentials
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials:
                aws_status['credentials_method'] = 'boto3_session'
                aws_status['region'] = session.region_name or os.environ.get('AWS_DEFAULT_REGION')
                
                # Try to list S3 buckets as a connectivity test
                try:
                    s3_client = boto3.client('s3')
                    s3_client.list_buckets()
                    aws_status['can_list_buckets'] = True
                    self.print_success("✓ AWS credentials configured and working")
                except Exception as e:
                    self.print_warning(f"AWS credentials found but S3 test failed: {e}")
            else:
                self.print_warning("No AWS credentials found")
                
        except Exception as e:
            self.print_warning(f"AWS credential check failed: {e}")
        
        self.results['aws']['details'] = aws_status
        
        # Consider AWS configured if we have credentials, even if S3 test fails
        self.results['aws']['status'] = aws_status['credentials_method'] is not None
        return self.results['aws']['status']
    
    def check_project_structure(self) -> bool:
        """Check project structure and key files."""
        self.print_status("Checking project structure...")
        
        required_files = [
            'src/main.py',
            'src/utils/config.py',
            'src/utils/logging_config.py',
            'requirements.txt',
            '.env.template',
        ]
        
        required_dirs = [
            'src',
            'src/models',
            'src/tools',
            'src/utils',
        ]
        
        structure_status = {
            'files_present': [],
            'files_missing': [],
            'dirs_present': [],
            'dirs_missing': [],
        }
        
        # Check files
        for file_path in required_files:
            if os.path.exists(file_path):
                structure_status['files_present'].append(file_path)
            else:
                structure_status['files_missing'].append(file_path)
        
        # Check directories
        for dir_path in required_dirs:
            if os.path.isdir(dir_path):
                structure_status['dirs_present'].append(dir_path)
            else:
                structure_status['dirs_missing'].append(dir_path)
        
        self.results['project_structure']['details'] = structure_status
        
        missing_items = structure_status['files_missing'] + structure_status['dirs_missing']
        
        if missing_items:
            self.print_error(f"Missing project files/dirs: {', '.join(missing_items)}")
            self.results['project_structure']['status'] = False
            return False
        else:
            self.print_success("✓ Project structure complete")
            self.results['project_structure']['status'] = True
            return True
    
    def check_project_imports(self) -> bool:
        """Check if project modules can be imported."""
        self.print_status("Checking project imports...")
        
        # Add src to path
        src_path = os.path.abspath('src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        
        modules_to_test = [
            'utils.config',
            'utils.logging_config',
            'models.chunk_model',
            'models.quote_model',
        ]
        
        import_status = {
            'successful': [],
            'failed': [],
        }
        
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
                import_status['successful'].append(module_name)
            except Exception as e:
                import_status['failed'].append(f"{module_name}: {str(e)}")
        
        if import_status['failed']:
            self.print_error(f"Import failures: {'; '.join(import_status['failed'])}")
            return False
        else:
            self.print_success(f"✓ All {len(import_status['successful'])} project modules importable")
            return True
    
    def run_comprehensive_check(self, include_dev: bool = False) -> bool:
        """Run all dependency checks."""
        print("=" * 60)
        print("Video Trimming Project - Dependency Check")
        print("=" * 60)
        
        checks = [
            ("Python Version", self.check_python_version),
            ("System Packages", self.check_system_packages),
            ("Python Packages", lambda: self.check_python_packages(include_dev)),
            ("FFmpeg", self.check_ffmpeg),
            ("Environment Variables", self.check_environment_variables),
            ("AWS Configuration", self.check_aws_configuration),
            ("Project Structure", self.check_project_structure),
            ("Project Imports", self.check_project_imports),
        ]
        
        passed = 0
        total = len(checks)
        
        for check_name, check_func in checks:
            print(f"\n--- {check_name} ---")
            try:
                if check_func():
                    passed += 1
                else:
                    self.print_error(f"{check_name} check failed")
            except Exception as e:
                self.print_error(f"{check_name} check error: {e}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("Dependency Check Summary")
        print("=" * 60)
        
        for category, result in self.results.items():
            status = "PASS" if result['status'] else "FAIL"
            print(f"{category.replace('_', ' ').title()}: {status}")
        
        print(f"\nOverall: {passed}/{total} checks passed")
        
        # Print recommendations
        if passed < total:
            print("\nRecommendations:")
            self._print_recommendations()
        
        return passed == total
    
    def _print_recommendations(self):
        """Print recommendations based on failed checks."""
        if not self.results['python']['status']:
            print("• Install Python 3.8 or higher")
        
        if not self.results['system_packages']['status']:
            print("• Install missing system packages (git, curl, build tools)")
        
        if not self.results['python_packages']['status']:
            details = self.results['python_packages']['details']
            if details.get('missing'):
                print(f"• Install missing Python packages: pip install {' '.join(details['missing'])}")
        
        if not self.results['ffmpeg']['status']:
            print("• Install FFmpeg: run ./scripts/setup_ffmpeg.sh --install")
        
        if not self.results['environment']['status']:
            print("• Set up environment variables: copy .env.template to .env and configure")
        
        if not self.results['aws']['status']:
            print("• Configure AWS credentials: aws configure or set environment variables")
        
        if not self.results['project_structure']['status']:
            print("• Ensure you're running from the project root directory")
    
    def export_results(self, filename: str = 'dependency_check_results.json'):
        """Export results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        self.print_success(f"Results exported to {filename}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check project dependencies')
    parser.add_argument('--include-dev', action='store_true', help='Include development dependencies')
    parser.add_argument('--export', help='Export results to JSON file')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode - only show summary')
    
    args = parser.parse_args()
    
    if args.quiet:
        # Redirect stdout to suppress detailed output
        import io
        import contextlib
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            checker = DependencyChecker()
            success = checker.run_comprehensive_check(include_dev=args.include_dev)
        
        # Print only summary
        output = f.getvalue()
        lines = output.split('\n')
        summary_start = None
        for i, line in enumerate(lines):
            if 'Dependency Check Summary' in line:
                summary_start = i
                break
        
        if summary_start:
            print('\n'.join(lines[summary_start:]))
    else:
        checker = DependencyChecker()
        success = checker.run_comprehensive_check(include_dev=args.include_dev)
    
    if args.export:
        checker.export_results(args.export)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
