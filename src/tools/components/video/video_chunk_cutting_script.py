import boto3
import logging
import os
from boto3.dynamodb.conditions import Key
import tempfile
from botocore.exceptions import ClientError
from pydub.utils import which
import urllib.parse
import ffmpeg
from typing import List, Tuple, Dict, Any

from utils.config import  CHUNK_TABLE, PODCAST_METADATA_TABLE, VIDEO_BUCKET, VIDEO_CHUNK_BUCKET
from utils.logging_config import setup_custom_logger

logging = setup_custom_logger(__name__)

# Initialize clients
ecs = boto3.client('ecs')
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

def check_if_exists_in_s3(bucket_name, s3_chunk_key):
    """
    Check if an object exists in S3.
    
    Args:
        bucket_name (str): Name of the S3 bucket
        s3_chunk_key (str): S3 key to check
        
    Returns:
        bool: True if object exists, False otherwise
        
    Raises:
        ClientError: If there's an error other than 404
    """
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
                        chunks_info: List[Dict[str, Any]], 
                        overwrite: bool = True) -> List[Tuple[str, str]]:
    """
    Process video chunks from a single input file using ffmpeg in batch mode.
    Downloads the full video file, splits it into chunks based on 
    start and end timestamps from each chunk, and uploads them to S3.
    Returns a list of S3 paths for the uploaded video chunks.
    """
    # Input validation
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    if not chunks_info:
        logging.warning("No chunks provided for processing")
        return []
    
    try:
        video_chunks_paths_and_keys = []
        output_operations = []
        
        # Create a temporary directory for video processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change working directory to temp_dir for ffmpeg operations
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Download full video file
                full_video_path = os.path.join(temp_dir, "full_video.mp4")
                
                try:
                    s3_client.download_file(VIDEO_BUCKET, s3_video_key, full_video_path)
                    logging.info(f"Downloaded source video from s3://{VIDEO_BUCKET}/{s3_video_key}")
                except ClientError as e:
                    logging.error(f"Failed to download source video: {e}")
                    raise
                
                # Verify downloaded file exists and has content
                if not os.path.exists(full_video_path) or os.path.getsize(full_video_path) == 0:
                    raise Exception("Downloaded video file is empty or missing")
                
                # Process each chunk and prepare batch operations
                valid_chunks_count = 0
                for i, chunk in enumerate(chunks_info):
                    try:
                        logging.info(f"Preparing chunk {i+1}/{len(chunks_info)} for {podcast_title}/{episode_title}")
                        
                        # Extract chunk information
                        chunk_filename = f"{chunk['episode_title#chunk_no']}.mp4"
                        time_stamps = chunk['time_stamps']
                        start_time = time_stamps['start']
                        end_time = time_stamps['end']
                        s3_chunk_key = f"{podcast_title}/{episode_title}/{chunk_filename}"
                        
                        if start_time is None or end_time is None:
                            logging.warning(f"Skipping chunk {i+1} due to missing timestamps")
                            continue
                        
                        # Validate timestamps
                        if start_time < 0 or end_time < 0:
                            logging.warning(f"Skipping chunk {i+1} due to negative timestamps: start={start_time}, end={end_time}")
                            continue
                            
                        if start_time >= end_time:
                            logging.warning(f"Skipping chunk {i+1} due to invalid timestamps: start={start_time} >= end={end_time}")
                            continue
                        
                        duration = end_time - start_time
                        if duration < 1.0:  # Minimum 1 second duration
                            logging.warning(f"Skipping chunk {i+1} due to too short duration: {duration}s")
                            continue
                        
                        # Check if chunk already exists in S3 and skip if not overwriting
                        if not overwrite and check_if_exists_in_s3(VIDEO_CHUNK_BUCKET, s3_chunk_key):
                            logging.info(f"Chunk {i+1} already exists in S3, skipping")
                            video_chunks_paths_and_keys.append((chunk_filename, s3_chunk_key))
                            continue
                        
                        # Create ffmpeg operation for this chunk
                        output_op = (
                            ffmpeg
                            .input(full_video_path, ss=start_time, t=duration)
                            .output(chunk_filename, 
                                vcodec='libx264', 
                                acodec='aac',
                                crf=23,
                                preset='medium',
                                movflags='faststart')
                        )
                        output_operations.append(output_op)
                        video_chunks_paths_and_keys.append((chunk_filename, s3_chunk_key))
                        valid_chunks_count += 1
                        
                        logging.info(f"Prepared chunk {i+1} - {start_time:.2f}s to {end_time:.2f}s ({duration:.2f}s)")
                        
                    except Exception as e:
                        logging.error(f"Error preparing chunk {i+1}: {e}")
                        continue
                
                if not output_operations:
                    logging.warning("No valid chunks found for processing")
                    return []

                logging.info(f"Executing ffmpeg batch command for {valid_chunks_count} valid chunks...")
                
                # Execute all ffmpeg operations in one go (batch processing)
                try:
                    ffmpeg.run(tuple(output_operations), capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                except ffmpeg.Error as e:
                    stderr_output = e.stderr.decode('utf8', errors='ignore') if isinstance(e.stderr, bytes) else str(e.stderr)
                    logging.error(f"FFmpeg batch processing failed: {stderr_output}")
                    raise Exception(f"Video chunk processing failed: {stderr_output}")
                
                # Upload processed files
                successful_uploads = []
                for video_chunk_path, s3_chunk_key in video_chunks_paths_and_keys:
                    local_path = os.path.join(temp_dir, video_chunk_path)
                    
                    if not os.path.exists(local_path):
                        logging.error(f"Processed file '{video_chunk_path}' does not exist after processing")
                        continue
                    
                    if os.path.getsize(local_path) == 0:
                        logging.error(f"Processed file '{video_chunk_path}' is empty")
                        continue
                    
                    try:
                        s3_client.upload_file(
                            local_path, 
                            VIDEO_CHUNK_BUCKET, 
                            s3_chunk_key, 
                            ExtraArgs={
                                "ContentType": "video/mp4", 
                                "ACL": "public-read",
                                "CacheControl": "max-age=3600"
                            }
                        )
                        successful_uploads.append((video_chunk_path, s3_chunk_key))
                        logging.info(f"Uploaded {video_chunk_path} to s3://{VIDEO_CHUNK_BUCKET}/{s3_chunk_key}")
                    except ClientError as e:
                        logging.error(f"Failed to upload {video_chunk_path}: {e}")
                        continue
                
                logging.info(f"Successfully processed and uploaded {len(successful_uploads)}/{len(video_chunks_paths_and_keys)} video chunks")
                
                # Add the chunk video URLs to the chunks
                chunks_with_urls = update_chunk_video_urls_in_dynamo(podcast_title, episode_title, chunks_info)
                
                return successful_uploads
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
        
    except Exception as e:
        logging.error(f"Error processing video chunks: {e}")
        raise

def update_video_chunking_status(podcast_title, episode_title, status):
    """
    Update the chunking status in the metadata table.
    
    Args:
        podcast_title (str): Title of the podcast
        episode_title (str): Title of the episode
        status (str): Status to set
        
    Returns:
        dict: DynamoDB response
        
    Raises:
        ValueError: If input parameters are invalid
        ClientError: If DynamoDB operation fails
    """
    if not podcast_title or not episode_title or not status:
        raise ValueError("podcast_title, episode_title, and status cannot be empty")
        
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE) # type: ignore
        response = metadata_table.update_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            },
            UpdateExpression='SET video_chunking_status = :status, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':status': status,
                ':timestamp': int(__import__('time').time())  # Add timestamp
            },
            ReturnValues='UPDATED_NEW'
        )

        logging.info(f"Updated video_chunking_status to '{status}' for {podcast_title}/{episode_title}")
        return response
    except ClientError as e:
        logging.error(f"Error updating video chunking status for {podcast_title}/{episode_title}: {e}")
        raise

def update_chunk_video_urls_in_dynamo(podcast_title, episode_title, chunks):
    """
    For each chunk, generate chunk_video_url and update the item in DynamoDB.
    (Matching audio implementation pattern)
    """
    if not podcast_title or not episode_title:
        raise ValueError("podcast_title and episode_title cannot be empty")
        
    if not chunks:
        logging.warning("No chunks provided for URL updates")
        return []
    
    # Use the correct BASE_S3_URL for video chunks (matching audio pattern)
    BASE_S3_VIDEO_CHUNK_URL = f"https://{VIDEO_CHUNK_BUCKET}.s3.amazonaws.com"
    
    table = dynamodb.Table(CHUNK_TABLE) # type: ignore
    
    for chunk in chunks:
        pk = chunk['podcast_title']
        sk = chunk['episode_title#chunk_no']
        s3_key = f"{podcast_title}/{episode_title}/{sk}.mp4"
        encoded_key = urllib.parse.quote(s3_key, safe='')  # Match audio implementation exactly
        chunk_video_url = f"{BASE_S3_VIDEO_CHUNK_URL}/{encoded_key}"
        chunk['chunk_video_url'] = chunk_video_url

        try:
            table.update_item(
                Key={
                    'podcast_title': pk,
                    'episode_title#chunk_no': sk
                },
                UpdateExpression='SET chunk_video_url = :url',
                ExpressionAttributeValues={
                    ':url': chunk_video_url
                }
            )
            logging.info(f"Updated chunk_video_url for {sk}")
        except Exception as e:
            logging.error(f"Failed to update {sk}: {e}")

    return chunks