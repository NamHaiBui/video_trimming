
"""
Monitor video processing background jobs and their status.
Fixed version with enhanced error handling.
"""

import sys
import os
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import traceback

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.aws_clients import get_dynamodb_resource
from utils.config import PODCAST_METADATA_TABLE
from utils.logging_config import setup_custom_logger
from boto3.dynamodb.conditions import Key

logging = setup_custom_logger(__name__)
dynamodb = get_dynamodb_resource()

class VideoProcessMonitor:
    """Monitor for video processing background jobs"""
    
    def __init__(self):
        self.metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
    
    def get_episode_status(self, episode_id: str) -> Optional[Dict]:
        """Get current status of all video processes for an episode"""
        try:
            response = self.metadata_table.query(
                IndexName='episodeUUID', 
                KeyConditionExpression=Key('id').eq(episode_id)
            )
            items = response.get("Items", [])
            
            if not items:
                return None
            
            item = items[0]
            
            # Handle DynamoDB type conversion for numbers
            last_updated_raw = item.get('last_updated', 0)
            last_updated = int(last_updated_raw) if isinstance(last_updated_raw, (int, str)) else 0
            
            num_chunks_raw = item.get('num_chunks', 0)
            num_chunks = int(num_chunks_raw) if isinstance(num_chunks_raw, (int, str)) else 0
            
            num_quotes_raw = item.get('num_quotes', 0)
            num_quotes = int(num_quotes_raw) if isinstance(num_quotes_raw, (int, str)) else 0
            
            return {
                'episode_id': episode_id,
                'podcast_title': str(item.get('podcast_title', '')),
                'episode_title': str(item.get('episode_title', '')),
                'chunking_status': str(item.get('chunking_status', 'PENDING')),
                'video_chunking_status': str(item.get('video_chunking_status', 'PENDING')),
                'quotes_video_status': str(item.get('quotes_video_status', 'PENDING')),
                'summaries_video_status': str(item.get('summaries_video_status', 'PENDING')),
                'last_updated': last_updated,
                'num_chunks': num_chunks,
                'num_quotes': num_quotes
            }
        except Exception as e:
            logging.error(f"Error getting episode status: {e}")
            return None
    
    def get_all_in_progress_episodes(self) -> List[Dict]:
        """Get all episodes with video processing in progress"""
        try:
            # Scan for episodes with any IN_PROGRESS status
            response = self.metadata_table.scan(
                FilterExpression="video_chunking_status = :status OR quotes_video_status = :status OR summaries_video_status = :status",
                ExpressionAttributeValues={':status': 'IN_PROGRESS'}
            )
            
            episodes = []
            for item in response.get('Items', []):
                # Handle DynamoDB type conversion for numbers
                last_updated_raw = item.get('last_updated', 0)
                last_updated = int(last_updated_raw) if isinstance(last_updated_raw, (int, str)) else 0
                
                episodes.append({
                    'episode_id': str(item.get('id', '')),
                    'podcast_title': str(item.get('podcast_title', '')),
                    'episode_title': str(item.get('episode_title', '')),
                    'video_chunking_status': str(item.get('video_chunking_status', 'PENDING')),
                    'quotes_video_status': str(item.get('quotes_video_status', 'PENDING')), 
                    'summaries_video_status': str(item.get('summaries_video_status', 'PENDING')),
                    'last_updated': last_updated
                })
            
            return episodes
        except Exception as e:
            logging.error(f"Error getting in-progress episodes: {e}")
            return []
    
    def print_status(self, episode_data: Dict, include_details: bool = True):
        """Print formatted status for an episode"""
        print(f"\n{'='*60}")
        print(f"Episode ID: {episode_data['episode_id']}")
        print(f"Podcast: {episode_data['podcast_title']}")
        print(f"Episode: {episode_data['episode_title']}")
        
        if include_details:
            print(f"Chunks: {episode_data.get('num_chunks', 0)}")
            print(f"Quotes: {episode_data.get('num_quotes', 0)}")
        
        print(f"\nProcessing Status:")
        print(f"  Chunking (base): {episode_data.get('chunking_status', 'UNKNOWN')}")
        print(f"  Video Chunks:    {self._format_status(episode_data.get('video_chunking_status', 'UNKNOWN'))}")
        print(f"  Video Quotes:    {self._format_status(episode_data.get('quotes_video_status', 'UNKNOWN'))}")
        print(f"  Video Summaries: {self._format_status(episode_data.get('summaries_video_status', 'UNKNOWN'))}")
        
        if episode_data.get('last_updated', 0) > 0:
            last_updated = datetime.fromtimestamp(episode_data['last_updated'])
            print(f"\nLast Updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")

    def _format_status(self, status: str) -> str:
        """Format status with emoji indicators"""
        status_icons = {
            'COMPLETED': '✅ COMPLETED',
            'IN_PROGRESS': '🔄 IN_PROGRESS', 
            'PENDING': '⏳ PENDING',
            'FAILED': '❌ FAILED',
            'SKIPPED': '⏭️ SKIPPED'
        }
        return status_icons.get(status, f'❓ {status}')
    
    def monitor_episode(self, episode_id: str, check_interval: int = 30, timeout_seconds: int = 3600) -> bool:
        """Monitor a specific episode until completion or timeout"""
        start_time = time.time()
        print(f"🔄 Monitoring episode {episode_id} (timeout: {timeout_seconds}s)")
        
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    print(f"⏰ Timeout reached after {elapsed:.0f} seconds")
                    return False
                
                status = self.get_episode_status(episode_id)
                if not status:
                    print(f"❌ Episode {episode_id} not found")
                    return False
                
                # Check if all video processes are completed
                video_statuses = [
                    status['video_chunking_status'],
                    status['quotes_video_status'], 
                    status['summaries_video_status']
                ]
                
                completed_count = sum(1 for s in video_statuses if s == 'COMPLETED')
                failed_count = sum(1 for s in video_statuses if s == 'FAILED')
                in_progress_count = sum(1 for s in video_statuses if s == 'IN_PROGRESS')
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: ✅{completed_count} 🔄{in_progress_count} ❌{failed_count}")
                
                # All completed
                if completed_count == 3:
                    print(f"🎉 All video processing completed for episode {episode_id}")
                    return True
                
                # Any failed
                if failed_count > 0:
                    print(f"❌ {failed_count} process(es) failed for episode {episode_id}")
                    self.print_status(status, include_details=False)
                    return False
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped by user")
            return False
        except Exception as e:
            print(f"❌ Error monitoring episode: {e}")
            logging.error(f"Monitor error: {e}")
            return False
    
    def monitor_all_in_progress(self, interval: int = 30):
        """Monitor all episodes currently in progress"""
        print(f"🔄 Monitoring all in-progress episodes (check interval: {interval}s)")
        print("Press Ctrl+C to stop monitoring")
        
        try:
            while True:
                episodes = self.get_all_in_progress_episodes()
                
                if not episodes:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No episodes currently in progress")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(episodes)} episodes in progress:")
                    
                    for episode in episodes:
                        print(f"\n  📺 {episode['episode_id']} - {episode['podcast_title']}")
                        print(f"     Chunks: {self._format_status(episode['video_chunking_status'])}")
                        print(f"     Quotes: {self._format_status(episode['quotes_video_status'])}")
                        print(f"     Summaries: {self._format_status(episode['summaries_video_status'])}")
                
                print(f"\n{'─'*50}")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped by user")

def main():
    parser = argparse.ArgumentParser(description='Monitor video processing background jobs')
    parser.add_argument('--episode-id', help='Monitor specific episode ID')
    parser.add_argument('--all', action='store_true', help='Monitor all in-progress episodes')
    parser.add_argument('--status', help='Get current status of episode ID')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds')
    parser.add_argument('--timeout', type=int, default=3600, help='Timeout in seconds for episode monitoring')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    args = parser.parse_args()
    
    monitor = VideoProcessMonitor()
    
    try:
        if args.status:
            # Get status of specific episode
            status = monitor.get_episode_status(args.status)
            if not status:
                print(f"Episode {args.status} not found")
                return 1
            
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                monitor.print_status(status)
            return 0
        
        elif args.episode_id:
            # Monitor specific episode
            success = monitor.monitor_episode(args.episode_id, args.interval, args.timeout)
            return 0 if success else 1
        
        elif args.all:
            # Monitor all in-progress episodes
            monitor.monitor_all_in_progress(args.interval)
            return 0
        
        else:
            # Default: show all in-progress episodes once
            episodes = monitor.get_all_in_progress_episodes()
            if episodes:
                print(f"Found {len(episodes)} episodes with video processing in progress:")
                for episode in episodes:
                    if args.json:
                        print(json.dumps(episode, indent=2))
                    else:
                        monitor.print_status(episode)
            else:
                print("No episodes with video processing in progress")
            return 0
    
    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Main error: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
