#!/usr/bin/env python3
"""
FFmpeg functionality test script for the Video Trimming Project.
This script tests various FFmpeg capabilities required by the application.
"""

import os
import sys
import subprocess
import tempfile
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class FFmpegTester:
    """Test FFmpeg installation and functionality."""
    
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()
        self.test_results = {}
        self.temp_dir = None
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable."""
        # Check environment variable first
        if 'FFMPEG_PATH' in os.environ:
            path = os.environ['FFMPEG_PATH']
            if os.path.exists(path):
                return path
        
        # Check system PATH
        return shutil.which('ffmpeg')
    
    def _find_ffprobe(self) -> Optional[str]:
        """Find FFprobe executable."""
        # Check environment variable first
        if 'FFPROBE_PATH' in os.environ:
            path = os.environ['FFPROBE_PATH']
            if os.path.exists(path):
                return path
        
        # Check system PATH
        return shutil.which('ffprobe')
    
    def print_status(self, message: str):
        print(f"[INFO] {message}")
    
    def print_success(self, message: str):
        print(f"[SUCCESS] {message}")
    
    def print_warning(self, message: str):
        print(f"[WARNING] {message}")
    
    def print_error(self, message: str):
        print(f"[ERROR] {message}")
    
    def run_command(self, cmd: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.temp_dir
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def test_installation(self) -> bool:
        """Test if FFmpeg and FFprobe are installed and accessible."""
        self.print_status("Testing FFmpeg installation...")
        
        if not self.ffmpeg_path:
            self.print_error("FFmpeg not found")
            self.test_results['installation'] = False
            return False
        
        if not self.ffprobe_path:
            self.print_error("FFprobe not found")
            self.test_results['installation'] = False
            return False
        
        self.print_success(f"FFmpeg found at: {self.ffmpeg_path}")
        self.print_success(f"FFprobe found at: {self.ffprobe_path}")
        
        # Test version commands
        success, stdout, stderr = self.run_command([self.ffmpeg_path, '-version'])
        if not success:
            self.print_error(f"FFmpeg version command failed: {stderr}")
            self.test_results['installation'] = False
            return False
        
        # Extract version info
        version_line = stdout.split('\n')[0]
        print(f"  {version_line}")
        
        success, stdout, stderr = self.run_command([self.ffprobe_path, '-version'])
        if not success:
            self.print_error(f"FFprobe version command failed: {stderr}")
            self.test_results['installation'] = False
            return False
        
        self.test_results['installation'] = True
        self.print_success("✓ Installation test passed")
        return True
    
    def test_audio_generation(self) -> bool:
        """Test audio file generation."""
        self.print_status("Testing audio generation...")
        
        if self.temp_dir is None:
            self.print_error("Temporary directory not initialized")
            return False
        
        output_file = os.path.join(self.temp_dir, 'test_audio.wav')
        
        # Generate 1 second of silence
        cmd = [
            self.ffmpeg_path,
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=mono',
            '-t', '1',
            '-f', 'wav',
            output_file,
            '-y'
        ]
        
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.print_error(f"Audio generation failed: {stderr}")
            self.test_results['audio_generation'] = False
            return False
        
        # Check if file was created and has reasonable size
        if not os.path.exists(output_file):
            self.print_error("Generated audio file does not exist")
            self.test_results['audio_generation'] = False
            return False
        
        file_size = os.path.getsize(output_file)
        if file_size < 1000:  # Should be at least 1KB for 1 second of audio
            self.print_error(f"Generated audio file too small: {file_size} bytes")
            self.test_results['audio_generation'] = False
            return False
        
        self.test_results['audio_generation'] = True
        self.print_success("✓ Audio generation test passed")
        return True
    
    def test_audio_processing(self) -> bool:
        """Test audio processing capabilities."""
        self.print_status("Testing audio processing...")
        
        if self.temp_dir is None:
            self.print_error("Temporary directory not initialized")
            return False
        
        input_file = os.path.join(self.temp_dir, 'test_audio.wav')
        output_file = os.path.join(self.temp_dir, 'processed_audio.wav')
        
        # First generate input audio if it doesn't exist
        if not os.path.exists(input_file):
            if not self.test_audio_generation():
                return False
        
        # Apply volume filter
        cmd = [
            self.ffmpeg_path,
            '-i', input_file,
            '-af', 'volume=0.5',
            output_file,
            '-y'
        ]
        
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.print_error(f"Audio processing failed: {stderr}")
            self.test_results['audio_processing'] = False
            return False
        
        if not os.path.exists(output_file):
            self.print_error("Processed audio file does not exist")
            self.test_results['audio_processing'] = False
            return False
        
        self.test_results['audio_processing'] = True
        self.print_success("✓ Audio processing test passed")
        return True
    
    def test_audio_cutting(self) -> bool:
        """Test audio cutting/trimming functionality."""
        self.print_status("Testing audio cutting...")
        
        if self.temp_dir is None:
            self.print_error("Temporary directory not initialized")
            return False
        
        input_file = os.path.join(self.temp_dir, 'test_audio.wav')
        output_file = os.path.join(self.temp_dir, 'cut_audio.wav')
        
        # Generate longer audio first
        cmd = [
            self.ffmpeg_path,
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=mono',
            '-t', '5',  # 5 seconds
            '-f', 'wav',
            input_file,
            '-y'
        ]
        
        success, stdout, stderr = self.run_command(cmd)
        if not success:
            self.print_error(f"Long audio generation failed: {stderr}")
            self.test_results['audio_cutting'] = False
            return False
        
        # Cut from 1s to 3s (2 seconds duration)
        cmd = [
            self.ffmpeg_path,
            '-i', input_file,
            '-ss', '1',
            '-t', '2',
            output_file,
            '-y'
        ]
        
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.print_error(f"Audio cutting failed: {stderr}")
            self.test_results['audio_cutting'] = False
            return False
        
        if not os.path.exists(output_file):
            self.print_error("Cut audio file does not exist")
            self.test_results['audio_cutting'] = False
            return False
        
        self.test_results['audio_cutting'] = True
        self.print_success("✓ Audio cutting test passed")
        return True
    
    def test_ffprobe_analysis(self) -> bool:
        """Test FFprobe file analysis."""
        self.print_status("Testing FFprobe analysis...")
        
        if self.temp_dir is None:
            self.print_error("Temporary directory not initialized")
            return False
        
        input_file = os.path.join(self.temp_dir, 'test_audio.wav')
        
        # Generate test file if it doesn't exist
        if not os.path.exists(input_file):
            if not self.test_audio_generation():
                return False
        
        # Analyze file with FFprobe
        cmd = [
            self.ffprobe_path,
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            input_file
        ]
        
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.print_error(f"FFprobe analysis failed: {stderr}")
            self.test_results['ffprobe_analysis'] = False
            return False
        
        try:
            data = json.loads(stdout)
            
            # Check if we got expected structure
            if 'format' not in data or 'streams' not in data:
                self.print_error("FFprobe output missing expected fields")
                self.test_results['ffprobe_analysis'] = False
                return False
            
            # Check format info
            format_info = data['format']
            if 'duration' not in format_info:
                self.print_error("FFprobe output missing duration")
                self.test_results['ffprobe_analysis'] = False
                return False
            
            # Check streams info
            streams = data['streams']
            if not streams or len(streams) == 0:
                self.print_error("No streams found in audio file")
                self.test_results['ffprobe_analysis'] = False
                return False
            
            audio_stream = streams[0]
            if audio_stream.get('codec_type') != 'audio':
                self.print_error("First stream is not audio")
                self.test_results['ffprobe_analysis'] = False
                return False
            
        except json.JSONDecodeError as e:
            self.print_error(f"Failed to parse FFprobe JSON output: {e}")
            self.test_results['ffprobe_analysis'] = False
            return False
        
        self.test_results['ffprobe_analysis'] = True
        self.print_success("✓ FFprobe analysis test passed")
        return True
    
    def test_codec_support(self) -> bool:
        """Test codec support."""
        self.print_status("Testing codec support...")
        
        # Get list of supported codecs
        cmd = [self.ffmpeg_path, '-codecs']
        success, stdout, stderr = self.run_command(cmd)
        
        if not success:
            self.print_error(f"Failed to get codec list: {stderr}")
            self.test_results['codec_support'] = False
            return False
        
        # Check for essential codecs
        essential_codecs = ['aac', 'mp3', 'wav', 'h264']
        missing_codecs = []
        
        for codec in essential_codecs:
            if codec.lower() not in stdout.lower():
                missing_codecs.append(codec)
        
        if missing_codecs:
            self.print_warning(f"Missing codecs: {', '.join(missing_codecs)}")
            # Don't fail the test, just warn as static builds might have limited codec support
        
        self.test_results['codec_support'] = True
        self.print_success("✓ Codec support test passed")
        return True
    
    def test_project_compatibility(self) -> bool:
        """Test compatibility with project requirements."""
        self.print_status("Testing project compatibility...")
        
        try:
            # Test if we can import the project's config module
            sys.path.insert(0, 'src')
            from utils.config import get_ffmpeg_path, get_ffprobe_path
            
            # Test config functions
            try:
                config_ffmpeg = get_ffmpeg_path()
                config_ffprobe = get_ffprobe_path()
                
                self.print_success(f"✓ Config FFmpeg path: {config_ffmpeg}")
                self.print_success(f"✓ Config FFprobe path: {config_ffprobe}")
                
                # Verify paths match what we found
                if config_ffmpeg != self.ffmpeg_path:
                    self.print_warning(f"Config FFmpeg path differs from found path")
                
                if config_ffprobe != self.ffprobe_path:
                    self.print_warning(f"Config FFprobe path differs from found path")
                
            except Exception as e:
                self.print_error(f"Config function error: {e}")
                self.test_results['project_compatibility'] = False
                return False
            
        except ImportError as e:
            self.print_warning(f"Could not import project config: {e}")
            # Not a failure if we're running outside project context
        
        self.test_results['project_compatibility'] = True
        self.print_success("✓ Project compatibility test passed")
        return True
    
    def run_all_tests(self) -> bool:
        """Run all tests."""
        print("=" * 50)
        print("FFmpeg Functionality Test Suite")
        print("=" * 50)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            self.temp_dir = temp_dir
            
            tests = [
                ('Installation', self.test_installation),
                ('Audio Generation', self.test_audio_generation),
                ('Audio Processing', self.test_audio_processing),
                ('Audio Cutting', self.test_audio_cutting),
                ('FFprobe Analysis', self.test_ffprobe_analysis),
                ('Codec Support', self.test_codec_support),
                ('Project Compatibility', self.test_project_compatibility),
            ]
            
            passed = 0
            total = len(tests)
            
            for test_name, test_func in tests:
                print(f"\n--- {test_name} ---")
                try:
                    if test_func():
                        passed += 1
                    else:
                        self.print_error(f"{test_name} test failed")
                except Exception as e:
                    self.print_error(f"{test_name} test error: {e}")
            
            print("\n" + "=" * 50)
            print("Test Results Summary")
            print("=" * 50)
            
            for test_name, result in self.test_results.items():
                status = "PASS" if result else "FAIL"
                print(f"{test_name.replace('_', ' ').title()}: {status}")
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                self.print_success("All tests passed! FFmpeg is ready for use.")
                return True
            else:
                self.print_error(f"{total - passed} test(s) failed.")
                return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test FFmpeg functionality')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    tester = FFmpegTester()
    
    if not tester.ffmpeg_path or not tester.ffprobe_path:
        print("[ERROR] FFmpeg or FFprobe not found. Please install FFmpeg first.")
        return 1
    
    success = tester.run_all_tests()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
