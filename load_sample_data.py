#!/usr/bin/env python3
"""
Script to load sample CSV data into DynamoDB tables and upload sample files to S3
"""

import os
import sys
import csv
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

# Load environment variables
project_root = Path(__file__).parent
env_file = project_root / '.env'
if env_file.exists():
    load_dotenv(env_file)

# Add src to path
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))

from utils.aws_clients import get_dynamodb_resource, get_s3_client
from utils.config import (
    CHUNK_TABLE, QUOTES_TABLE, PODCAST_METADATA_TABLE,
    AUDIO_BUCKET, VIDEO_BUCKET, SUMMARY_TRANSCRIPT_BUCKET
)
from models.chunk_model import Chunk

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_json_field(field_value):
    """Parse JSON field from CSV, return empty dict/list if parsing fails"""
    if not field_value or field_value.strip() == '':
        return {}
    try:
        return json.loads(field_value)
    except json.JSONDecodeError:
        return {}

def convert_csv_row_to_dynamodb_chunk_item(row: Dict[str, str]) -> Dict[str, Any]:
    """Convert CSV row to DynamoDB item format"""
    
    # Parse complex JSON fields
    sentiment = parse_json_field(row.get('sentiment', '[]'))
    speakers = parse_json_field(row.get('speakers', '[]'))
    topics = parse_json_field(row.get('topics', '[]'))
    time_stamps = parse_json_field(row.get('time_stamps', '{}'))
    word_timestamps = parse_json_field(row.get('word_timestamps', '[]'))
    
    # Create DynamoDB item
    item = {
        'podcast_title': row.get('podcast_title', ''),
        'episode_title#chunk_no': row.get('episode_title#chunk_no', ''),
        'chunk': row.get('chunk', ''),
        'chunk_audio_url': row.get('chunk_audio_url', ''),
        'chunk_description': row.get('chunk_description', ''),
        'chunk_length': row.get('chunk_length', ''),
        'chunk_title': row.get('chunk_title', ''),
        'chunk_uuid': row.get('chunk_uuid', ''),
        'genre': row.get('genre', ''),
        'sentiment': sentiment,
        'speakers': speakers,
        'time_stamps': time_stamps,
        'topics': topics,
        'word_timestamps': word_timestamps
    }
    
    return item

def load_chunks_from_csv(csv_path: str) -> int:
    """Load chunk data from CSV file into DynamoDB"""
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return 0
    
    # Initialize DynamoDB
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(CHUNK_TABLE)
    
    loaded_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Convert CSV row to DynamoDB item
                    item = convert_csv_row_to_dynamodb_chunk_item(row)
                    
                    # Put item into DynamoDB
                    table.put_item(Item=item)
                    loaded_count += 1
                    
                    if loaded_count % 10 == 0:
                        logger.info(f"Loaded {loaded_count} chunks...")
                        
                except Exception as e:
                    logger.error(f"Error loading row {row_num}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return loaded_count
    
    logger.info(f"Successfully loaded {loaded_count} chunks from {csv_path}")
    return loaded_count
def load_quotes_from_csv(csv_path: str) -> int:
    """Load quotes from CSV file into DynamoDB table"""
    
    # Initialize DynamoDB
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(QUOTES_TABLE)
    
    loaded_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    item = {
                        'podcast_title': row.get('podcast_title', ''),
                        'episode_title#quote_rank': row.get('episode_title#quote_rank', ''),
                        'absolute_context_word_timestamps': parse_json_field(row.get('absolute_context_word_timestamps', '[]')),
                        'absolute_quote_word_timestamps': parse_json_field(row.get('absolute_quote_word_timestamps', '[]')),
                        'context': row.get('context', ''),
                        'context_length': row.get('context_length', ''),
                        'context_timestamps': parse_json_field(row.get('context_timestamps', '{}')),
                        'episode_title': row.get('episode_title', ''),
                        'generated_quote_uuid': row.get('generated_quote_uuid', ''),
                        'genre': row.get('genre', ''),
                        'processing_timestamp_utc': row.get('processing_timestamp_utc', ''),
                        'quote': row.get('quote', ''),
                        'quote_audio_url': row.get('quote_audio_url', ''),
                        'quote_length': row.get('quote_length', ''),
                        'quote_rank': row.get('quote_rank', ''),
                        'quote_timestamps': parse_json_field(row.get('quote_timestamps', '{}')),
                        'sentiment': row.get('sentiment', ''),  # Keep as string, not parsed JSON
                        'Short_description': row.get('Short_description', ''),
                        'source_transcript_id': row.get('source_transcript_id', ''),
                        'speaker_label': row.get('speaker_label', ''),
                        'speaker_name': row.get('speaker_name', ''),
                        'topic': row.get('topic', ''),
                        'transcript_level_context_word_timestamps': parse_json_field(row.get('transcript_level_context_word_timestamps', '[]')),
                        'transcript_level_quote_word_timestamps': parse_json_field(row.get('transcript_level_quote_word_timestamps', '[]'))
                    }
                    
                    # Put item into DynamoDB
                    table.put_item(Item=item)
                    loaded_count += 1
                    
                    if loaded_count % 10 == 0:
                        logger.info(f"Loaded {loaded_count} quotes...")
                        
                except Exception as e:
                    logger.error(f"Error loading row {row_num}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return loaded_count
    
    logger.info(f"Successfully loaded {loaded_count} quotes from {csv_path}")
    return loaded_count
def create_podcast_metadata_entry(podcast_title: str, episode_title: str, num_chunks: int, num_quotes: int):
    """Create metadata entry for the podcast episode"""
    
    # Initialize DynamoDB
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(PODCAST_METADATA_TABLE)
    
    # Create metadata item
    metadata_item = {
        'episodeUUID': podcast_title,  # Primary partition key for the table
        'episode_title': episode_title,  # Sort key for the table
        'id': podcast_title, 
        'podcast_title': podcast_title,
        'num_chunks': num_chunks,
        'num_quotes': num_quotes, 
        'file_name': "ouput.mp4",
        'chunking_status': 'COMPLETED',
        'quote_extraction_status': 'COMPLETED',
        'summarization_status': 'COMPLETED',
        'video_chunking_status': 'PENDING',
        'quotes_video_status': 'PENDING',
        'summaries_video_status': 'PENDING',
        'last_updated': int(__import__('time').time())
    }
    
    try:
        table.put_item(Item=metadata_item)
        logger.info(f"Created metadata entry for {podcast_title} - {episode_title}")
    except Exception as e:
        logger.error(f"Error creating metadata entry: {e}")

def count_quotes_from_csv(csv_path: str) -> int:
    """Count the number of quotes in the quotes CSV file"""
    
    if not os.path.exists(csv_path):
        logger.warning(f"Quotes CSV file not found: {csv_path}")
        return 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return sum(1 for _ in reader)
    except Exception as e:
        logger.error(f"Error counting quotes: {e}")
        return 0

def upload_sample_files_to_s3():
    """Upload base audio, video, and summary transcript files to S3"""
    
    logger.info("Starting S3 upload of sample files...")
    
    # Initialize S3 client
    s3_client = get_s3_client()
    
    # Define file mappings: (local_path, bucket, s3_key)
    file_mappings = [

        (
            project_root / "sample" / "ouput.mp4", 
            VIDEO_BUCKET,
            "ouput.mp4"
        ),
        (
            project_root / "sample" / "summary_transcript-all-in-live-from-austin-colin-and-samir-chris-williamson-and-bryan-johnson.json",
            SUMMARY_TRANSCRIPT_BUCKET,
            "summary_transcript-all-in-live-from-austin-colin-and-samir-chris-williamson-and-bryan-johnson.json"
        )
    ]
    
    upload_results = []
    
    for local_path, bucket, s3_key in file_mappings:
        try:
            if not local_path.exists():
                logger.warning(f"File not found: {local_path}")
                upload_results.append((s3_key, False, f"File not found: {local_path}"))
                continue
            
            file_size_mb = local_path.stat().st_size / (1024 * 1024)
            logger.info(f"Uploading {local_path.name} ({file_size_mb:.1f} MB) to s3://{bucket}/{s3_key}")
            
            # Determine content type based on file extension
            content_type = "application/octet-stream"  # default
            if local_path.suffix.lower() in ['.mp4', '.mov', '.avi']:
                content_type = "video/mp4"
            elif local_path.suffix.lower() in ['.mp3', '.m4a', '.wav']:
                content_type = "audio/mpeg"
            elif local_path.suffix.lower() == '.json':
                content_type = "application/json"
            
            # Upload file to S3
            s3_client.upload_file(
                str(local_path),
                bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "ACL": "public-read",
                    "CacheControl": "max-age=3600"
                }
            )
            
            logger.info(f"✓ Successfully uploaded {local_path.name} to s3://{bucket}/{s3_key}")
            upload_results.append((s3_key, True, "Success"))
            
        except Exception as e:
            logger.error(f"✗ Failed to upload {local_path.name}: {e}")
            upload_results.append((s3_key, False, str(e)))
    
    # Summary of uploads
    successful_uploads = sum(1 for _, success, _ in upload_results if success)
    total_uploads = len(upload_results)
    
    logger.info(f"S3 upload summary: {successful_uploads}/{total_uploads} files uploaded successfully")
    
    for s3_key, success, message in upload_results:
        status = "✓" if success else "✗"
        logger.info(f"  {status} {s3_key}: {message}")
    
    return upload_results

def main():
    """Main function to load sample data"""
    
    logger.info("Starting sample data loading...")
    
    # Define paths
    chunks_csv = project_root / "sample" / "Chunk_results.csv"
    quotes_csv = project_root / "sample" / "Quote_results.csv"
    
    total_loaded = 0
    num_quotes = 0
    
    # Count quotes first
    if quotes_csv.exists():
        num_quotes = count_quotes_from_csv(str(quotes_csv))
        logger.info(f"Found {num_quotes} quotes in {quotes_csv}")
    
    # Load chunks data
    if chunks_csv.exists():
        logger.info(f"Loading chunks from {chunks_csv}")
        chunks_loaded = load_chunks_from_csv(str(chunks_csv))
        total_loaded += chunks_loaded
        
        # Create metadata entry based on loaded chunks
        if chunks_loaded > 0:
            # Determine podcast and episode info from the first few rows
            with open(chunks_csv, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                first_row = next(reader, None)
                if first_row:
                    podcast_title = first_row.get('podcast_title', '')
                    episode_chunk_id = first_row.get('episode_title#chunk_no', '')
                    episode_title = episode_chunk_id.split('#')[0] if '#' in episode_chunk_id else episode_chunk_id
                    
                    create_podcast_metadata_entry(podcast_title, episode_title, chunks_loaded, num_quotes)
    else:
        logger.warning(f"Chunks CSV file not found: {chunks_csv}")
    
    if quotes_csv.exists():
        logger.info(f"Quotes CSV found: {quotes_csv}")
        quotes_loaded = load_quotes_from_csv(str(quotes_csv))
        total_loaded += quotes_loaded
        logger.info(f"Successfully loaded {quotes_loaded} quotes from {quotes_csv}")

    else:
        logger.warning(f"Quotes CSV file not found: {quotes_csv}")
    
    # Upload sample audio, video, and transcript files to S3
    upload_results = upload_sample_files_to_s3()
    
    logger.info(f"Data loading complete. Total items loaded: {total_loaded}")

if __name__ == "__main__":
    main()
