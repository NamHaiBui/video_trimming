#!/usr/bin/env python3
"""
Monitor video processing background jobs and their status.
"""

import sys
import os
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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
            return {
                'episode_id': episode_id,
                'podcast_title': str(item.get('podcast_title', '')),
                'episode_title': str(item.get('episode_title', '')),
                'chunking_status': str(item.get('chunking_status', 'PENDING')),
                'video_chunking_status': str(item.get('video_chunking_status', 'PENDING')),
                'quotes_video_status': str(item.get('quotes_video_status', 'PENDING')),
                'summaries_video_status': str(item.get('summaries_video_status', 'PENDING')),
                'last_updated': int(item.get('last_updated', 0)) if item.get('last_updated') else 0,
                'num_chunks': int(item.get('num_chunks', 0)) if item.get('num_chunks') else 0,
                'num_quotes': int(item.get('num_quotes', 0)) if item.get('num_quotes') else 0
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
                episodes.append({
                    'episode_id': str(item.get('id', '')),
                    'podcast_title': str(item.get('podcast_title', '')),
                    'episode_title': str(item.get('episode_title', '')),
                    'video_chunking_status': str(item.get('video_chunking_status', 'PENDING')),
                    'quotes_video_status': str(item.get('quotes_video_status', 'PENDING')), 
                    'summaries_video_status': str(item.get('summaries_video_status', 'PENDING')),
                    'last_updated': int(item.get('last_updated', 0)) if item.get('last_updated') else 0
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
            print(f"Chunks: {episode_data['num_chunks']}")
            print(f"Quotes: {episode_data['num_quotes']}")
        
        print(f"\nProcessing Status:")
        print(f"  Chunking (base): {episode_data['chunking_status']}")
        print(f"  Video Chunks:    {self._format_status(episode_data['video_chunking_status'])}")
        print(f"  Video Quotes:    {self._format_status(episode_data['quotes_video_status'])}")
        print(f"  Video Summaries: {self._format_status(episode_data['summaries_video_status'])}")
        
        if episode_data['last_updated']:
            last_updated = datetime.fromtimestamp(episode_data['last_updated'])
            print(f"\nLast Updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _format_status(self, status: str) -> str:
        """Format status with color indicators (if terminal supports it)"""
        status_colors = {
            'COMPLETED': '✅',
            'IN_PROGRESS': '🔄', 
            'FAILED': '❌',
            'PENDING': '⏳'
        }
        icon = status_colors.get(status, '❓')
        return f"{icon} {status}"
    
    def monitor_episode(self, episode_id: str, interval: int = 30, timeout: int = 3600):
        """Monitor a specific episode until completion or timeout"""
        print(f"Monitoring episode {episode_id} (checking every {interval}s, timeout: {timeout}s)")
        
        start_time = datetime.now()
        timeout_time = start_time + timedelta(seconds=timeout)
        
        while datetime.now() < timeout_time:
            status = self.get_episode_status(episode_id)
            if not status:
                print(f"Episode {episode_id} not found")
                return False
            
            self.print_status(status)
            
            # Check if all processes are complete
            video_statuses = [
                status['video_chunking_status'],
                status['quotes_video_status'], 
                status['summaries_video_status']
            ]
            
            if all(s in ['COMPLETED', 'FAILED'] for s in video_statuses):
                completed_count = sum(1 for s in video_statuses if s == 'COMPLETED')
                failed_count = sum(1 for s in video_statuses if s == 'FAILED')
                
                print(f"\n🎉 All processes finished! Completed: {completed_count}, Failed: {failed_count}")
                return failed_count == 0
            
            # Check if any are still in progress
            if any(s == 'IN_PROGRESS' for s in video_statuses):
                print(f"\n⏰ Still processing... Next check in {interval}s")
                time.sleep(interval)
            else:
                print(f"\n⏸️  No processes currently running")
                return True
        
        print(f"\n⏰ Monitoring timeout reached after {timeout}s")
        return False
    
    def monitor_all_in_progress(self, interval: int = 60):
        """Monitor all episodes with processes in progress"""
        print(f"Monitoring all in-progress episodes (checking every {interval}s)")
        print("Press Ctrl+C to stop monitoring\n")
        
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
        # Show current in-progress episodes
        episodes = monitor.get_all_in_progress_episodes()
        if not episodes:
            print("No episodes currently in progress")
        else:
            print(f"Found {len(episodes)} episodes in progress:")
            for episode in episodes:
                monitor.print_status(episode, include_details=False)
        return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
