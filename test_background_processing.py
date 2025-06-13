#!/usr/bin/env python3
"""
Integration test for video processing background jobs
"""

import sys
import os
import time
import json
from unittest.mock import Mock, patch

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from tools.generate_video_artifacts import (
    process_video_chunks_background,
    process_video_quotes_background,
    process_video_summaries_background,
    get_video_chunking_status,
    get_quotes_video_status,
    get_summaries_video_status,
    get_summarization_status
)
from tools.video_processing_config import VideoProcessingConfig
from utils.logging_config import setup_custom_logger

logging = setup_custom_logger(__name__)

def test_config():
    """Test configuration loading"""
    print("Testing configuration...")
    
    # Test basic configuration
    config = VideoProcessingConfig()
    assert config.MAX_CONCURRENT_PROCESSES > 0
    assert config.CHUNK_PROCESSING_TIMEOUT > 0
    assert config.QUOTE_PROCESSING_TIMEOUT > 0
    assert config.SUMMARY_PROCESSING_TIMEOUT > 0
    
    # Test process-specific config
    chunks_config = config.get_process_config('chunks')
    assert 'max_workers' in chunks_config
    assert 'timeout' in chunks_config
    assert 'priority' in chunks_config
    
    # Test FFmpeg config
    ffmpeg_config = config.get_ffmpeg_config()
    assert 'video_codec' in ffmpeg_config
    assert 'audio_codec' in ffmpeg_config
    
    print("✅ Configuration test passed")

def test_status_functions():
    """Test status checking functions with mocked DynamoDB"""
    print("Testing status functions...")
    
    mock_table = Mock()
    mock_response = {
        'Item': {
            'video_chunking_status': 'COMPLETED',
            'quotes_video_status': 'PENDING',
            'summaries_video_status': 'IN_PROGRESS',
            'summarization_status': 'COMPLETED'
        }
    }
    mock_table.get_item.return_value = mock_response
    
    with patch('tools.generate_video_artifacts.dynamodb') as mock_dynamodb:
        mock_dynamodb.Table.return_value = mock_table
        
        # Test each status function
        chunks_status = get_video_chunking_status('test_podcast', 'test_episode')
        assert chunks_status == 'COMPLETED'
        
        quotes_status = get_quotes_video_status('test_podcast', 'test_episode')
        assert quotes_status == 'PENDING'
        
        summaries_status = get_summaries_video_status('test_podcast', 'test_episode')
        assert summaries_status == 'IN_PROGRESS'
        
        summarization_status = get_summarization_status('test_podcast', 'test_episode')
        assert summarization_status == 'COMPLETED'
    
    print("✅ Status functions test passed")

def test_background_process_structure():
    """Test that background process functions have correct structure"""
    print("Testing background process structure...")
    
    # Mock data
    test_podcast = "Test Podcast"
    test_episode = "Test Episode"
    test_s3_key = "test/video.mp4"
    test_episode_id = "test-123"
    
    with patch('tools.generate_video_artifacts.get_video_chunking_status') as mock_status:
        with patch('tools.generate_video_artifacts.update_video_chunking_status') as mock_update:
            with patch('tools.generate_video_artifacts.process_video_chunks') as mock_process:
                mock_status.return_value = 'COMPLETED'
                
                # Test chunks background process
                result = process_video_chunks_background(
                    test_podcast, test_episode, test_s3_key, [], 0, test_episode_id, False
                )
                
                assert isinstance(result, dict)
                assert 'status' in result
                assert 'type' in result
                assert result['type'] == 'chunks'
                assert result['status'] == 'COMPLETED'
    
    with patch('tools.generate_video_artifacts.get_quotes_video_status') as mock_status:
        mock_status.return_value = 'COMPLETED'
        
        # Test quotes background process
        result = process_video_quotes_background(
            test_podcast, test_episode, test_s3_key, [], 0, test_episode_id, False
        )
        
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'type' in result
        assert result['type'] == 'quotes'
        assert result['status'] == 'COMPLETED'
    
    with patch('tools.generate_video_artifacts.get_summarization_status') as mock_sum_status:
        with patch('tools.generate_video_artifacts.get_summaries_video_status') as mock_vid_status:
            mock_sum_status.return_value = 'PENDING'
            mock_vid_status.return_value = 'PENDING'
            
            # Test summaries background process
            result = process_video_summaries_background(
                test_podcast, test_episode, test_s3_key, test_episode_id, False
            )
            
            assert isinstance(result, dict)
            assert 'status' in result
            assert 'type' in result
            assert result['type'] == 'summaries'
            assert result['status'] == 'PENDING'
    
    print("✅ Background process structure test passed")

def test_concurrent_execution_simulation():
    """Simulate concurrent execution to test threading behavior"""
    print("Testing concurrent execution simulation...")
    
    import concurrent.futures
    from concurrent.futures import ThreadPoolExecutor
    
    def mock_background_task(task_id, duration):
        """Mock background task that takes some time"""
        time.sleep(duration)
        return {
            'task_id': task_id,
            'status': 'COMPLETED',
            'type': f'task_{task_id}',
            'message': f'Task {task_id} completed successfully'
        }
    
    # Test concurrent execution
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        
        # Submit 3 tasks that should run concurrently
        for i in range(3):
            future = executor.submit(mock_background_task, i, 0.1)  # Very short duration for testing
            futures.append(future)
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Should complete faster than sequential execution (3 * 0.1 = 0.3 seconds)
    assert total_time < 0.25, f"Concurrent execution took too long: {total_time}s"
    assert len(results) == 3
    
    for result in results:
        assert result['status'] == 'COMPLETED'
        assert 'task_id' in result
    
    print(f"✅ Concurrent execution test passed (completed in {total_time:.3f}s)")

def main():
    """Run all tests"""
    print("🚀 Starting video processing background jobs integration tests\n")
    
    try:
        test_config()
        test_status_functions()
        test_background_process_structure()
        test_concurrent_execution_simulation()
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 Test Summary:")
        print("  ✅ Configuration loading")
        print("  ✅ Status checking functions")
        print("  ✅ Background process structure")
        print("  ✅ Concurrent execution simulation")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
