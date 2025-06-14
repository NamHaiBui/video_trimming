
"""
Configuration for video processing background jobs
"""

import os
from typing import Dict, Any, Optional

class VideoProcessingConfig:
    """Configuration settings for video processing background jobs"""
    
    # Concurrency settings
    MAX_CONCURRENT_PROCESSES = int(os.getenv('MAX_CONCURRENT_PROCESSING', '3'))
    MAX_CONCURRENT_CHUNKS = int(os.getenv('MAX_CONCURRENT_CHUNKS', '1'))
    MAX_CONCURRENT_QUOTES = int(os.getenv('MAX_CONCURRENT_QUOTES', '1'))
    MAX_CONCURRENT_SUMMARIES = int(os.getenv('MAX_CONCURRENT_SUMMARIES', '1'))
    
    # Timeout settings (in seconds)
    CHUNK_PROCESSING_TIMEOUT = int(os.getenv('CHUNK_PROCESSING_TIMEOUT', '1800'))  # 30 minutes
    QUOTE_PROCESSING_TIMEOUT = int(os.getenv('QUOTE_PROCESSING_TIMEOUT', '3600'))  # 60 minutes  
    SUMMARY_PROCESSING_TIMEOUT = int(os.getenv('SUMMARY_PROCESSING_TIMEOUT', '2400'))  # 40 minutes
    
    # Retry settings
    MAX_RETRIES = int(os.getenv('MAX_PROCESSING_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY_SECONDS', '300'))  # 5 minutes
    
    # Resource limits
    MAX_MEMORY_MB = int(os.getenv('MAX_MEMORY_MB', '4096'))  # 4GB
    TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/video_processing')
    
    # Process priority settings
    PROCESS_PRIORITIES = {
        'chunks': int(os.getenv('CHUNKS_PRIORITY', '1')),      # Highest priority
        'quotes': int(os.getenv('QUOTES_PRIORITY', '2')),      # Medium priority
        'summaries': int(os.getenv('SUMMARIES_PRIORITY', '3')) # Lowest priority
    }
    
    # Monitoring settings
    STATUS_CHECK_INTERVAL = int(os.getenv('STATUS_CHECK_INTERVAL', '30'))  # 30 seconds
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '60'))       # 1 minute
    
    # FFmpeg settings
    FFMPEG_THREADS = int(os.getenv('FFMPEG_THREADS', '0'))  # 0 = auto
    FFMPEG_PRESET = os.getenv('FFMPEG_PRESET', 'medium')
    FFMPEG_CRF = int(os.getenv('FFMPEG_CRF', '23'))
    
    # Hardware acceleration settings
    USE_GPU_ACCELERATION = os.getenv('USE_GPU_ACCELERATION', 'false').lower() == 'true'
    GPU_DEVICE = os.getenv('GPU_DEVICE', '0')
    
    AUDIO_CODEC = os.getenv('AUDIO_CODEC', 'aac')
    
    @classmethod
    def get_ffmpeg_codec(cls, prefer_gpu: Optional[bool] = None) -> str:
        # """Get the best available FFmpeg video codec"""
        # if prefer_gpu is None:
        #     prefer_gpu = cls.USE_GPU_ACCELERATION
        
        # if prefer_gpu:
        #     # Prefer GPU codecs
        #     for codec in ['h264_nvenc', 'h264_vaapi', 'libx264']:
        #         if codec in cls.VIDEO_CODEC_PRIORITY:
        #             return codec
        
        # # Fallback to CPU codec
        return 'libx264'
    
    @classmethod
    def get_process_config(cls, process_type: str) -> Dict[str, Any]:
        """Get configuration for a specific process type"""
        base_config = {
            'max_workers': cls.MAX_CONCURRENT_PROCESSES,
            'timeout': 3600,  # Default 1 hour
            'max_retries': cls.MAX_RETRIES,
            'retry_delay': cls.RETRY_DELAY,
            'priority': 2,  # Default medium priority
            'temp_dir': cls.TEMP_DIR
        }
        
        if process_type == 'chunks':
            base_config.update({
                'max_workers': cls.MAX_CONCURRENT_CHUNKS,
                'timeout': cls.CHUNK_PROCESSING_TIMEOUT,
                'priority': cls.PROCESS_PRIORITIES['chunks']
            })
        elif process_type == 'quotes':
            base_config.update({
                'max_workers': cls.MAX_CONCURRENT_QUOTES,
                'timeout': cls.QUOTE_PROCESSING_TIMEOUT,
                'priority': cls.PROCESS_PRIORITIES['quotes']
            })
        elif process_type == 'summaries':
            base_config.update({
                'max_workers': cls.MAX_CONCURRENT_SUMMARIES,
                'timeout': cls.SUMMARY_PROCESSING_TIMEOUT,
                'priority': cls.PROCESS_PRIORITIES['summaries']
            })
        
        return base_config
    
    @classmethod
    def get_ffmpeg_config(cls) -> Dict[str, Any]:
        """Get FFmpeg configuration"""
        return {
            'threads': cls.FFMPEG_THREADS,
            'preset': cls.FFMPEG_PRESET,
            'crf': cls.FFMPEG_CRF,
            'video_codec': cls.get_ffmpeg_codec(),
            'audio_codec': cls.AUDIO_CODEC,
            'use_gpu': cls.USE_GPU_ACCELERATION,
            'gpu_device': cls.GPU_DEVICE
        }
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("Video Processing Configuration:")
        print("=" * 40)
        print(f"Max Concurrent Processes: {cls.MAX_CONCURRENT_PROCESSES}")
        print(f"Chunk Processing Timeout: {cls.CHUNK_PROCESSING_TIMEOUT}s")
        print(f"Quote Processing Timeout: {cls.QUOTE_PROCESSING_TIMEOUT}s") 
        print(f"Summary Processing Timeout: {cls.SUMMARY_PROCESSING_TIMEOUT}s")
        print(f"Max Retries: {cls.MAX_RETRIES}")
        print(f"Retry Delay: {cls.RETRY_DELAY}s")
        print(f"Temp Directory: {cls.TEMP_DIR}")
        print(f"Use GPU Acceleration: {cls.USE_GPU_ACCELERATION}")
        print(f"Video Codec: {cls.get_ffmpeg_codec()}")
        print(f"Audio Codec: {cls.AUDIO_CODEC}")
        print(f"Process Priorities: {cls.PROCESS_PRIORITIES}")

def get_processing_config() -> Dict[str, Any]:
    """
    Get the current processing configuration as a dictionary
    
    Returns:
        Dict containing all configuration settings
    """
    return {
        # Concurrency settings
        'max_concurrent_processes': VideoProcessingConfig.MAX_CONCURRENT_PROCESSES,
        'max_concurrent_chunks': VideoProcessingConfig.MAX_CONCURRENT_CHUNKS,
        'max_concurrent_quotes': VideoProcessingConfig.MAX_CONCURRENT_QUOTES,
        'max_concurrent_summaries': VideoProcessingConfig.MAX_CONCURRENT_SUMMARIES,
        
        # Timeout settings
        'chunk_processing_timeout': VideoProcessingConfig.CHUNK_PROCESSING_TIMEOUT,
        'quote_processing_timeout': VideoProcessingConfig.QUOTE_PROCESSING_TIMEOUT,
        'summary_processing_timeout': VideoProcessingConfig.SUMMARY_PROCESSING_TIMEOUT,
        
        # Retry settings
        'max_retries': VideoProcessingConfig.MAX_RETRIES,
        'retry_delay': VideoProcessingConfig.RETRY_DELAY,
        
        # Resource limits
        'max_memory_mb': VideoProcessingConfig.MAX_MEMORY_MB,
        'temp_dir': VideoProcessingConfig.TEMP_DIR,
        
        # Process priorities
        'process_priorities': VideoProcessingConfig.PROCESS_PRIORITIES.copy(),
        
        # Monitoring settings
        'status_check_interval': VideoProcessingConfig.STATUS_CHECK_INTERVAL,
        'heartbeat_interval': VideoProcessingConfig.HEARTBEAT_INTERVAL,
        
        # FFmpeg settings
        'ffmpeg_threads': VideoProcessingConfig.FFMPEG_THREADS,
        'ffmpeg_preset': VideoProcessingConfig.FFMPEG_PRESET,
        'ffmpeg_crf': VideoProcessingConfig.FFMPEG_CRF,
        
        # Hardware acceleration
        'use_gpu_acceleration': VideoProcessingConfig.USE_GPU_ACCELERATION,
        'gpu_device': VideoProcessingConfig.GPU_DEVICE,
    }

def get_config_for_process(process_type: str) -> Dict[str, Any]:
    """
    Get configuration specific to a process type
    
    Args:
        process_type: 'chunks', 'quotes', or 'summaries'
        
    Returns:
        Dict containing process-specific configuration
    """
    base_config = get_processing_config()
    
    timeout_map = {
        'chunks': base_config['chunk_processing_timeout'],
        'quotes': base_config['quote_processing_timeout'], 
        'summaries': base_config['summary_processing_timeout']
    }
    
    return {
        'timeout': timeout_map.get(process_type, 1800),
        'priority': base_config['process_priorities'].get(process_type, 2),
        'max_retries': base_config['max_retries'],
        'retry_delay': base_config['retry_delay'],
        'max_memory_mb': base_config['max_memory_mb'],
        'temp_dir': base_config['temp_dir'],
        'ffmpeg_settings': {
            'threads': base_config['ffmpeg_threads'],
            'preset': base_config['ffmpeg_preset'],
            'crf': base_config['ffmpeg_crf'],
            'use_gpu': base_config['use_gpu_acceleration'],
            'gpu_device': base_config['gpu_device']
        }
    }

if __name__ == '__main__':
    # Print current configuration when run directly
    VideoProcessingConfig.print_config()
