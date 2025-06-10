import os
import shutil
from pathlib import Path

PODCAST_METADATA_TABLE=os.environ.get("PODCAST_METADATA_TABLE", "PodcastEpisodeStore")
QUOTES_TABLE = os.environ.get("QUOTES_TABLE", "TranscriptQuoteStore")
CHUNK_TABLE=os.environ.get("CHUNK_TABLE", "TranscriptChunkStore")
# root file
AUDIO_BUCKET=os.environ.get("AUDIO_BUCKET", "pd-audio-storage")
VIDEO_BUCKET = os.environ.get("VIDEO_BUCKET", "pd-video-storage")
#
SUMMARY_TRANSCRIPT_BUCKET = os.environ.get("SUMMARY_TRANSCRIPT_BUCKET", "pd-summary-transcript-storage")

AUDIO_QUOTE_BUCKET=os.environ.get("AUDIO_QUOTES_CHUNK_BUCKET", "pd-audio-quotes-storage")
VIDEO_QUOTE_BUCKET = os.environ.get("VIDEO_QUOTES_CHUNK_BUCKET", "pd-video-quotes-storage")

VIDEO_CHUNK_BUCKET =os.environ.get("CHUNK_VIDEO_BUCKET", "pd-video-chunks-storage")
AUDIO_CHUNK_BUCKET =os.environ.get("AUDIO_CHUNK_BUCKET", "pd-audio-chunks-storage")

AUDIO_SUMMARY_BUCKET = os.environ.get("AUDIO_SUMMARY_BUCKET", "pd-audio-summary-storage")
VIDEO_SUMMARY_BUCKET = os.environ.get("VIDEO_SUMMARY_BUCKET", "pd-video-summary-storage")

# ===========================================
# FFmpeg Configuration
# ===========================================
def get_ffmpeg_path():
    """Get FFmpeg path from environment or system PATH."""
    # Check environment variable first
    ffmpeg_path = os.environ.get("FFMPEG_PATH")
    if ffmpeg_path and Path(ffmpeg_path).exists():
        return ffmpeg_path
    
    # Check system PATH
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path
    
    # Check common installation paths
    common_paths = [
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        str(Path.home() / '.local' / 'bin' / 'ffmpeg'),
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    raise FileNotFoundError("FFmpeg not found. Please install FFmpeg or run scripts/setup_ffmpeg.sh")

def get_ffprobe_path():
    """Get FFprobe path from environment or system PATH."""
    # Check environment variable first
    ffprobe_path = os.environ.get("FFPROBE_PATH")
    if ffprobe_path and Path(ffprobe_path).exists():
        return ffprobe_path
    
    # Check system PATH
    ffprobe_path = shutil.which('ffprobe')
    if ffprobe_path:
        return ffprobe_path
    
    # Check common installation paths
    common_paths = [
        '/usr/bin/ffprobe',
        '/usr/local/bin/ffprobe',
        str(Path.home() / '.local' / 'bin' / 'ffprobe'),
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    raise FileNotFoundError("FFprobe not found. Please install FFmpeg or run scripts/setup_ffmpeg.sh")

# Application Settings
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
MAX_CONCURRENT_PROCESSING = int(os.environ.get("MAX_CONCURRENT_PROCESSING", "5"))
TEMP_DIR = os.environ.get("TEMP_DIR", "/tmp/video_processing")

# Ensure temp directory exists
Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)