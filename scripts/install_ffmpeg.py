
"""
Cross-platform FFmpeg installer for the Video Trimming Project.
This script downloads and installs FFmpeg static builds when package managers are not available.
"""

import os
import sys
import platform
import subprocess
import urllib.request
import tarfile
import zipfile
import shutil
from pathlib import Path
import tempfile
import json


class FFmpegInstaller:
    """Cross-platform FFmpeg installer."""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        self.home_dir = Path.home()
        self.local_bin = self.home_dir / '.local' / 'bin'
        
        # Official FFmpeg builds
        self.urls = {
            'linux': {
                'x86_64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
                'i686': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux32-gpl.tar.xz',
                'aarch64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz',
            },
            'darwin': {
                'x86_64': 'https://evermeet.cx/ffmpeg/getrelease/zip',
                'arm64': 'https://evermeet.cx/ffmpeg/getrelease/zip',
            },
            'windows': {
                'amd64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
                'i386': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win32-gpl.zip',
            }
        }
        self.system = platform.system().lower()
        self.machine = platform.machine().lower()
        self.home_dir = Path.home()
        self.local_bin = self.home_dir / '.local' / 'bin'
        
        # Official FFmpeg builds
        self.urls = {
            'linux': {
                'x86_64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
                'i686': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux32-gpl.tar.xz',
                'aarch64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz',
            },
            'darwin': {
                'x86_64': 'https://evermeet.cx/ffmpeg/getrelease/zip',
                'arm64': 'https://evermeet.cx/ffmpeg/getrelease/zip',
            },
            'windows': {
                'amd64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
                'x86_64': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
            }
        }
    
    def print_status(self, message):
        print(f"[INFO] {message}")
    
    def print_success(self, message):
        print(f"[SUCCESS] {message}")
    
    def print_warning(self, message):
        print(f"[WARNING] {message}")
    
    def print_error(self, message):
        print(f"[ERROR] {message}")
    
    def command_exists(self, command):
        """Check if a command exists in PATH."""
        return shutil.which(command) is not None
    
    def check_installation(self):
        """Check if FFmpeg is already installed."""
        ffmpeg_path = shutil.which('ffmpeg')
        ffprobe_path = shutil.which('ffprobe')
        
        if ffmpeg_path and ffprobe_path:
            try:
                # Get version info
                result = subprocess.run(
                    ['ffmpeg', '-version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                version_line = result.stdout.split('\n')[0]
                version = version_line.split()[2] if len(version_line.split()) > 2 else 'unknown'
                
                self.print_success("FFmpeg is already installed:")
                print(f"  Version: {version}")
                print(f"  FFmpeg path: {ffmpeg_path}")
                print(f"  FFprobe path: {ffprobe_path}")
                return True
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, IndexError):
                self.print_warning("FFmpeg found but version check failed")
                return False
        
        self.print_warning("FFmpeg not found in PATH")
        return False
    
    def get_download_url(self):
        """Get the appropriate download URL for the current platform."""
        if self.system not in self.urls:
            raise RuntimeError(f"Unsupported operating system: {self.system}")
        
        platform_urls = self.urls[self.system]
        
        # Try to match machine architecture
        for arch in [self.machine, 'x86_64', 'amd64']:
            if arch in platform_urls:
                return platform_urls[arch]
        
        raise RuntimeError(f"No FFmpeg build available for {self.system} {self.machine}")
    
    def download_file(self, url, destination):
        """Download a file with progress indication."""
        self.print_status(f"Downloading from {url}")
        
        try:
            with urllib.request.urlopen(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                
                with open(destination, 'wb') as f:
                    downloaded = 0
                    chunk_size = 8192
                    
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r  Progress: {percent:.1f}%", end='', flush=True)
                    
                    print()  # New line after progress
                    
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}")
    
    def extract_archive(self, archive_path, extract_to):
        """Extract archive file."""
        self.print_status("Extracting archive...")
        
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif archive_path.suffix in ['.tar', '.xz'] or '.tar.' in archive_path.name:
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
        else:
            raise RuntimeError(f"Unsupported archive format: {archive_path.suffix}")
    
    def find_binaries(self, extract_dir):
        """Find FFmpeg and FFprobe binaries in extracted directory."""
        binaries = {}
        
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                file_path = Path(root) / file
                
                # Handle different naming patterns for different builds
                if ((file == 'ffmpeg' or file == 'ffmpeg.exe') and 
                    (file.startswith('ffmpeg') or 'ffmpeg' in file.lower())):
                    binaries['ffmpeg'] = file_path
                elif ((file == 'ffprobe' or file == 'ffprobe.exe') and 
                      (file.startswith('ffprobe') or 'ffprobe' in file.lower())):
                    binaries['ffprobe'] = file_path
        
        # If not found, look more specifically in bin/ directories
        if not binaries:
            for root, dirs, files in os.walk(extract_dir):
                if 'bin' in Path(root).name.lower():
                    for file in files:
                        file_path = Path(root) / file
                        if file in ['ffmpeg', 'ffmpeg.exe']:
                            binaries['ffmpeg'] = file_path
                        elif file in ['ffprobe', 'ffprobe.exe']:
                            binaries['ffprobe'] = file_path
        
        return binaries
    
    def install_binaries(self, binaries):
        """Install binaries to local bin directory."""
        self.print_status("Installing binaries...")
        
        # Create local bin directory
        self.local_bin.mkdir(parents=True, exist_ok=True)
        
        for name, source_path in binaries.items():
            if self.system == 'windows':
                dest_path = self.local_bin / f"{name}.exe"
            else:
                dest_path = self.local_bin / name
            
            shutil.copy2(source_path, dest_path)
            
            # Make executable on Unix systems
            if self.system != 'windows':
                dest_path.chmod(0o755)
            
            self.print_success(f"Installed {name} to {dest_path}")
    
    def update_path(self):
        """Update PATH environment variable to include local bin."""
        local_bin_str = str(self.local_bin)
        
        # Check if already in PATH
        current_path = os.environ.get('PATH', '')
        if local_bin_str in current_path:
            self.print_success("Local bin directory already in PATH")
            return
        
        # Add to current session
        os.environ['PATH'] = f"{local_bin_str}{os.pathsep}{current_path}"
        
        # Add to shell profile
        if self.system != 'windows':
            shell_profiles = [
                self.home_dir / '.bashrc',
                self.home_dir / '.zshrc',
                self.home_dir / '.profile'
            ]
            
            export_line = f'export PATH="{local_bin_str}:$PATH"\n'
            
            for profile in shell_profiles:
                if profile.exists():
                    with open(profile, 'r') as f:
                        content = f.read()
                    
                    if local_bin_str not in content:
                        with open(profile, 'a') as f:
                            f.write(f"\n# Added by FFmpeg installer\n{export_line}")
                        self.print_status(f"Added PATH update to {profile}")
                        break
        
        self.print_success("Updated PATH environment variable")
    
    def test_installation(self):
        """Test the FFmpeg installation."""
        self.print_status("Testing FFmpeg installation...")
        
        # Check if binaries are accessible
        ffmpeg_path = shutil.which('ffmpeg')
        ffprobe_path = shutil.which('ffprobe')
        
        if not ffmpeg_path or not ffprobe_path:
            # Try local bin directory
            ffmpeg_path = str(self.local_bin / ('ffmpeg.exe' if self.system == 'windows' else 'ffmpeg'))
            ffprobe_path = str(self.local_bin / ('ffprobe.exe' if self.system == 'windows' else 'ffprobe'))
        
        try:
            # Test FFmpeg
            result = subprocess.run(
                [ffmpeg_path, '-version'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                self.print_success("✓ FFmpeg is working")
            else:
                raise RuntimeError("FFmpeg version check failed")
            
            # Test FFprobe
            result = subprocess.run(
                [ffprobe_path, '-version'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                self.print_success("✓ FFprobe is working")
            else:
                raise RuntimeError("FFprobe version check failed")
            
            return True
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            self.print_error(f"Installation test failed: {e}")
            return False
    
    def install(self, force=False):
        """Install FFmpeg."""
        if not force and self.check_installation():
            self.print_status("FFmpeg already installed, use --force to reinstall")
            return True
        
        try:
            # Get download URL
            url = self.get_download_url()
            
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Determine file extension from URL
                if url.endswith('.zip'):
                    archive_name = 'ffmpeg.zip'
                elif '.tar.' in url or url.endswith('.tar') or url.endswith('.xz'):
                    archive_name = 'ffmpeg.tar.xz'
                else:
                    archive_name = 'ffmpeg_archive'
                
                archive_path = temp_path / archive_name
                extract_path = temp_path / 'extracted'
                
                # Download
                self.download_file(url, archive_path)
                
                # Extract
                self.extract_archive(archive_path, extract_path)
                
                # Find binaries
                binaries = self.find_binaries(extract_path)
                
                if not binaries:
                    raise RuntimeError("Could not find FFmpeg binaries in archive")
                
                if 'ffmpeg' not in binaries or 'ffprobe' not in binaries:
                    raise RuntimeError("Incomplete FFmpeg installation (missing ffmpeg or ffprobe)")
                
                # Install
                self.install_binaries(binaries)
                
                # Update PATH
                self.update_path()
                
                # Test
                if self.test_installation():
                    self.print_success("FFmpeg installation completed successfully!")
                    return True
                else:
                    raise RuntimeError("Installation test failed")
                
        except Exception as e:
            self.print_error(f"Installation failed: {e}")
            return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cross-platform FFmpeg installer')
    parser.add_argument('--check', action='store_true', help='Check if FFmpeg is installed')
    parser.add_argument('--install', action='store_true', help='Install FFmpeg')
    parser.add_argument('--force', action='store_true', help='Force reinstallation')
    parser.add_argument('--test', action='store_true', help='Test FFmpeg installation')
    
    args = parser.parse_args()
    
    installer = FFmpegInstaller()
    
    # Default to check if no arguments provided
    if not any([args.check, args.install, args.test]):
        args.install = True
    
    success = True
    
    if args.check or args.install:
        if args.check:
            installer.check_installation()
        
        if args.install:
            success = installer.install(force=args.force)
    
    if args.test:
        success = installer.test_installation()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
