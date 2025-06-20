import boto3
import logging
import os
import tempfile
from botocore.exceptions import ClientError
import urllib.parse
import ffmpeg
from typing import List, Tuple, Dict, Any

from models.chunk_model import Chunk
from utils.config import CHUNK_TABLE, PODCAST_METADATA_TABLE, VIDEO_BUCKET, VIDEO_CHUNK_BUCKET
from utils.logging_config import setup_custom_logger
from utils.aws_clients import get_dynamodb_resource, get_s3_client

logging = setup_custom_logger(__name__)

dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()

def check_if_exists_in_s3(bucket_name, s3_chunk_key):
    """Check if an object exists in S3."""
    if not bucket_name or not s3_chunk_key:
        raise ValueError("bucket_name and s3_chunk_key cannot be empty")
    
    try:
        s3_client.head_object(Bucket=bucket_name, Key=s3_chunk_key)
        return True  
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == '404':
            return False
        else:
            logging.error(f"Error checking S3 object {bucket_name}/{s3_chunk_key}: {e}")
            raise e

def process_video_chunks(podcast_title: str, 
                        episode_title: str, 
                        s3_video_key: str,
                        chunks_info: List[Chunk], 
                        overwrite: bool = True) -> List[Tuple[str, str]]:
    """
    Simple sequential video chunk processing.
    Downloads the full video file, splits it into chunks, and uploads them to S3.
    """
    # Input validation
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (" ", '-', '_')).strip()
    safe_episode_title = "".join(c  for c in episode_title if c.isalnum() or c in (" ", '-', '_')).strip()
    
    if not chunks_info:
        logging.warning("No chunks provided for processing")
        return []

    try:
        successful_uploads = []
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory(prefix="video_chunks_") as temp_dir:
            # Download source video
            full_video_path = os.path.join(temp_dir, "source_video.mp4")
            
            try:
                logging.info(f"Downloading source video from s3://{VIDEO_BUCKET}/{s3_video_key}")
                s3_client.download_file(VIDEO_BUCKET, s3_video_key, full_video_path)
            except ClientError as e:
                logging.error(f"Failed to download source video: {e}")
                raise
            
            # Verify downloaded file
            if not os.path.exists(full_video_path) or os.path.getsize(full_video_path) == 0:
                raise Exception("Downloaded video file is empty or missing")
            
            # Process each chunk
            for i, chunk in enumerate(chunks_info):
                try:
                    logging.info(f"Processing chunk {i+1}/{len(chunks_info)}: {chunk.episode_chunk_id}")
                    
                    # Extract timestamps
                    time_stamps = chunk.time_stamps
                    try:
                        start_time = float(time_stamps.start) if time_stamps.start else None
                        end_time = float(time_stamps.end) if time_stamps.end else None
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Skipping chunk {i+1} due to invalid timestamps: {e}")
                        continue
                    
                    if start_time is None or end_time is None:
                        logging.warning(f"Skipping chunk {i+1} due to missing timestamps")
                        continue
                    
                    # Validate timestamps
                    if start_time < 0 or end_time < 0 or start_time >= end_time:
                        logging.warning(f"Skipping chunk {i+1} due to invalid timestamps: start={start_time}, end={end_time}")
                        continue
                    
                    duration = end_time - start_time
                    if duration < 1.0:
                        logging.warning(f"Skipping chunk {i+1} due to too short duration: {duration}s")
                        continue
                    
                    # Prepare file paths
                    chunk_filename = f"{chunk.episode_chunk_id}.mp4"
                    chunk_path = os.path.join(temp_dir, chunk_filename)
                    s3_chunk_key = f"{safe_podcast_title}/{safe_episode_title}/{chunk_filename}"
                    
                    # Check if already exists in S3
                    if not overwrite and check_if_exists_in_s3(VIDEO_CHUNK_BUCKET, s3_chunk_key):
                        logging.info(f"Chunk {chunk_filename} already exists in S3, skipping")
                        successful_uploads.append((chunk_filename, s3_chunk_key))
                        continue
                    
                    # Process with FFmpeg
                    logging.info(f"Processing chunk {chunk_filename}: {start_time:.2f}s to {end_time:.2f}s")
                    try:
                        (
                            ffmpeg
                            .input(full_video_path, ss=start_time, t=duration)
                            .output(chunk_path, vcodec='libx264', acodec='aac', crf=23)
                            .overwrite_output()
                            .run(capture_stdout=True, capture_stderr=True)
                        )
                        
                        # Verify output file was created
                        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
                            logging.error(f"FFmpeg did not create valid output for chunk {chunk_filename}")
                            continue
                            
                    except ffmpeg.Error as e:
                        stderr = e.stderr.decode('utf8', errors='ignore') if e.stderr else "No error output"
                        logging.error(f"FFmpeg failed for chunk {chunk_filename}: {stderr}")
                        continue
                    
                    # Upload to S3
                    try:
                        s3_client.upload_file(
                            chunk_path, 
                            VIDEO_CHUNK_BUCKET, 
                            s3_chunk_key,
                            ExtraArgs={
                                "ContentType": "video/mp4", 
                                "ACL": "public-read"
                            }
                        )
                        successful_uploads.append((chunk_filename, s3_chunk_key))
                        logging.info(f"Uploaded {chunk_filename} to S3")
                        
                    except ClientError as e:
                        logging.error(f"Failed to upload {chunk_filename}: {e}")
                        continue
                        
                except Exception as e:
                    logging.error(f"Error processing chunk {i+1}: {e}")
                    continue
            
            # Update chunk URLs in database
            if successful_uploads:
                update_chunk_video_urls_in_dynamo(podcast_title, episode_title, chunks_info)
            
            logging.info(f"Successfully processed {len(successful_uploads)}/{len(chunks_info)} chunks")
            return successful_uploads
        
    except Exception as e:
        logging.error(f"Error processing video chunks: {e}")
        raise

def update_video_chunking_status(podcast_title, episode_title, status):
    """Update the chunking status in the metadata table."""
    if not podcast_title or not episode_title or not status:
        raise ValueError("podcast_title, episode_title, and status cannot be empty")
        
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.update_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            },
            UpdateExpression='SET video_chunking_status = :status',
            ExpressionAttributeValues={
                ':status': status,
            },
            ReturnValues='UPDATED_NEW'
        )
        logging.info(f"Updated video_chunking_status to '{status}' for {podcast_title}/{episode_title}")
        return response
    except ClientError as e:
        logging.error(f"Error updating video chunking status: {e}")
        raise
