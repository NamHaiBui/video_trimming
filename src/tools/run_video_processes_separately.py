#!/usr/bin/env python3
"""
Separate script runners for each video processing component.
This allows running each process independently or monitoring their status.
"""

import sys
import os
import json
import argparse
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from generate_video_artifacts import (
    process_video_chunks_background,
    process_video_quotes_background, 
    process_video_summaries_background
)
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, get_all_quotes
from utils.aws_clients import get_dynamodb_resource
from utils.config import PODCAST_METADATA_TABLE
from boto3.dynamodb.conditions import Key

logging = setup_custom_logger(__name__)
dynamodb = get_dynamodb_resource()

def get_episode_metadata(meta_data_idx):
    """Get episode metadata from DynamoDB"""
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.query(IndexName='episodeUUID', KeyConditionExpression=Key('id').eq(meta_data_idx))
        items = response.get("Items", [])
        
        if not items:
            logging.error(f"No record found for ID: {meta_data_idx}")
            return None
        
        item = items[0]
        return {
            'podcast_title': str(item.get('podcast_title', '')),
            'episode_title': str(item.get('episode_title', '')),
            'num_chunks': int(item.get('num_chunks', 0)),
            's3_video_key': str(item.get('file_name', '')),
            'num_quotes': int(item.get('num_quotes', 0)),
            'chunking_status': str(item.get('chunking_status', 'PENDING')),
            'video_chunking_status': str(item.get('video_chunking_status', 'PENDING')),
            'quotes_video_status': str(item.get('quotes_video_status', 'PENDING')), 
            'summaries_video_status': str(item.get('summaries_video_status', 'PENDING')),
            'summarization_status': str(item.get('summarization_status', 'PENDING'))
        }
    except Exception as e:
        logging.error(f"Error getting episode metadata: {e}")
        return None

def run_chunks_processor(meta_data_idx, force=False):
    """Run only the video chunks processor"""
    logging.info(f"Starting video chunks processor for episode ID: {meta_data_idx}")
    start_time = datetime.now()
    
    metadata = get_episode_metadata(meta_data_idx)
    if not metadata:
        return False
    
    if metadata['chunking_status'] != 'COMPLETED':
        logging.error(f"Chunking not completed for ID: {meta_data_idx}, cannot process video chunks")
        return False
    
    # Get chunks data
    chunks = [x for x in get_all_chunks(metadata['podcast_title'], metadata['episode_title'], metadata['num_chunks']) if x.duration_seconds > 3]
    
    if not chunks:
        logging.error(f"No chunks found for episode ID: {meta_data_idx}")
        return False
    
    result = process_video_chunks_background(
        metadata['podcast_title'],
        metadata['episode_title'], 
        metadata['s3_video_key'],
        chunks,
        metadata['num_chunks'],
        meta_data_idx,
        force
    )
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    logging.info(f"Video chunks processor completed in {duration.total_seconds():.2f} seconds")
    logging.info(f"Result: {result}")
    
    return result.get('status') == 'COMPLETED'

def run_quotes_processor(meta_data_idx, force=False):
    """Run only the video quotes processor"""
    logging.info(f"Starting video quotes processor for episode ID: {meta_data_idx}")
    start_time = datetime.now()
    
    metadata = get_episode_metadata(meta_data_idx)
    if not metadata:
        return False
    
    if metadata['chunking_status'] != 'COMPLETED':
        logging.error(f"Chunking not completed for ID: {meta_data_idx}, cannot process video quotes")
        return False
    
    # Get quotes data
    quotes = get_all_quotes(metadata['podcast_title'], metadata['episode_title'])
    
    if not quotes:
        logging.error(f"No quotes found for episode ID: {meta_data_idx}")
        return False
    
    result = process_video_quotes_background(
        metadata['podcast_title'],
        metadata['episode_title'],
        metadata['s3_video_key'], 
        quotes,
        metadata['num_quotes'],
        meta_data_idx,
        force
    )
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    logging.info(f"Video quotes processor completed in {duration.total_seconds():.2f} seconds")
    logging.info(f"Result: {result}")
    
    return result.get('status') == 'COMPLETED'

def run_summaries_processor(meta_data_idx, force=False):
    """Run only the video summaries processor"""
    logging.info(f"Starting video summaries processor for episode ID: {meta_data_idx}")
    start_time = datetime.now()
    
    metadata = get_episode_metadata(meta_data_idx)
    if not metadata:
        return False
    
    if metadata['chunking_status'] != 'COMPLETED':
        logging.error(f"Chunking not completed for ID: {meta_data_idx}, cannot process video summaries")
        return False
    
    result = process_video_summaries_background(
        metadata['podcast_title'],
        metadata['episode_title'],
        metadata['s3_video_key'],
        meta_data_idx,
        force
    )
    
    end_time = datetime.now() 
    duration = end_time - start_time
    
    logging.info(f"Video summaries processor completed in {duration.total_seconds():.2f} seconds")
    logging.info(f"Result: {result}")
    
    return result.get('status') == 'COMPLETED'

def main():
    parser = argparse.ArgumentParser(description='Run video processing scripts separately')
    parser.add_argument('process_type', choices=['chunks', 'quotes', 'summaries', 'all'], 
                       help='Type of process to run')
    parser.add_argument('episode_id', help='Episode ID to process')
    parser.add_argument('--force', action='store_true', 
                       help='Force processing even if already completed')
    parser.add_argument('--json-input', help='JSON input with episode data')
    
    args = parser.parse_args()
    
    # Handle JSON input
    if args.json_input:
        try:
            json_data = json.loads(args.json_input)
            episode_id = json_data.get('id') or json_data.get('episode_id') or json_data.get('meta_data_idx')
            force_chunks = json_data.get('force_video_chunking', False)
            force_quotes = json_data.get('force_video_quote_extraction', False) 
            force_summaries = json_data.get('force_video_summary_extraction', False)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON input: {e}")
            return 1
    else:
        episode_id = args.episode_id
        force_chunks = force_quotes = force_summaries = args.force
    
    if not episode_id:
        logging.error("No episode ID provided")
        return 1
    
    success = True
    
    if args.process_type == 'chunks':
        success = run_chunks_processor(episode_id, force_chunks)
    elif args.process_type == 'quotes':
        success = run_quotes_processor(episode_id, force_quotes)
    elif args.process_type == 'summaries':
        success = run_summaries_processor(episode_id, force_summaries)
    elif args.process_type == 'all':
        # Run all processes sequentially
        logging.info("Running all video processes sequentially...")
        results = []
        results.append(('chunks', run_chunks_processor(episode_id, force_chunks)))
        results.append(('quotes', run_quotes_processor(episode_id, force_quotes)))  
        results.append(('summaries', run_summaries_processor(episode_id, force_summaries)))
        
        success = all(result for _, result in results)
        
        for process_name, result in results:
            status = "SUCCESS" if result else "FAILED"
            logging.info(f"Process '{process_name}': {status}")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
