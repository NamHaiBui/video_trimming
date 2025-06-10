import logging
import tempfile
from typing import List, Tuple
import boto3
from botocore.exceptions import ClientError
import ffmpeg
import sys
import os.path

import urllib.parse

from models.quote_model import Quote
from utils.config import PODCAST_METADATA_TABLE, QUOTES_TABLE, VIDEO_BUCKET, VIDEO_QUOTE_BUCKET

dynamodb= boto3.resource('dynamodb')
s3_client = boto3.client('s3')

def process_video_quotes(podcast_title:str, 
                         episode_title:str, 
                         s3_video_key:str,
                         snippets_info:List[Quote], 
                         overwrite:bool=True)-> List[Tuple[str,str]]:
    """
    Cuts multiple video snippets from a single input file in one ffmpeg process.
    Now handles both video and audio streams.

    Args:
        podcast_title (str): Title of the podcast
        episode_title (str): Title of the episode
        s3_video_key (str): S3 key for the source video
        snippets_info (List[Quote]): List of quote objects with timestamps
        overwrite (bool): Whether to overwrite output files if they exist.
    
    Returns:
        List[Tuple[str,str]]: List of (local_path, s3_key) tuples for processed videos
    
    Raises:
        ValueError: If input parameters are invalid
        ClientError: If S3 operations fail
        Exception: If ffmpeg processing fails
    """
    
    # Input validation
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    if not snippets_info:
        logging.warning("No snippets provided for processing")
        return []
    
    # Sanitize inputs for file paths
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
        video_quotes_paths_and_keys = []
        output_operations = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change working directory to temp_dir for ffmpeg operations
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                full_video_path = os.path.join(temp_dir, "full_video.mp4")
                
                # Download source video with error handling
                try:
                    s3_client.download_file(VIDEO_BUCKET, s3_video_key, full_video_path)
                    logging.info(f"Downloaded source video from s3://{VIDEO_BUCKET}/{s3_video_key}")
                except ClientError as e:
                    logging.error(f"Failed to download source video: {e}")
                    raise
                
                # Verify downloaded file exists and has content
                if not os.path.exists(full_video_path) or os.path.getsize(full_video_path) == 0:
                    raise Exception("Downloaded video file is empty or missing")
                
                # Process each quote
                valid_quotes_count = 0
                for i, quote in enumerate(snippets_info):
                    try:
                        start_time = float(quote.context_timestamps.start_time) if quote.context_timestamps.start_time else None
                        end_time = float(quote.context_timestamps.end_time) if quote.context_timestamps.end_time else None
                        
                        if not start_time or not end_time:
                            logging.warning(f"Skipping quote {i+1}/{len(snippets_info)} for {podcast_title}/{episode_title} due to missing timestamps")
                            continue
                            
                        if start_time < 0 or end_time < 0:
                            logging.warning(f"Skipping quote {i+1} due to negative timestamps: start={start_time}, end={end_time}")
                            continue
                            
                        if start_time > end_time:
                            logging.warning(f"Start time {start_time} > end time {end_time} for quote {i+1}. Swapping values.")
                            start_time, end_time = end_time, start_time
                        
                        duration = end_time - start_time
                        if duration < 0.1:
                            logging.warning(f"Skipping quote {i+1} due to too short duration: {duration}s")
                            continue
                        
                        video_quotes_filename = f"{quote.quote_rank}.mp4"
                        s3_quote_key = f"{safe_podcast_title}/{safe_episode_title}/{video_quotes_filename}"
                        
                        output_op = (
                            ffmpeg
                            .input(full_video_path, ss=start_time, t=duration)
                            .output(video_quotes_filename, 
                                vcodec='libx264', 
                                acodec='aac', 
                                crf=23,
                                preset='medium',
                                movflags='faststart')
                        )
                        output_operations.append(output_op)
                        video_quotes_paths_and_keys.append((video_quotes_filename, s3_quote_key))
                        valid_quotes_count += 1
                        
                        logging.info(f"Prepared quote {i+1}/{len(snippets_info)} (rank: {quote.quote_rank}) - {start_time:.2f}s to {end_time:.2f}s")
                        
                    except (ValueError, AttributeError) as e:
                        logging.error(f"Error processing quote {i+1}: {e}")
                        continue
                
                if not output_operations:
                    logging.warning("No valid quotes found for processing")
                    return []

                logging.info(f"Executing ffmpeg command for {valid_quotes_count} valid quotes...")
                
                # Execute ffmpeg with better error handling
                try:
                    ffmpeg.run(tuple(output_operations), capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                except ffmpeg.Error as e:
                    stderr_output = e.stderr.decode('utf8', errors='ignore') if isinstance(e.stderr, bytes) else str(e.stderr)
                    logging.error(f"FFmpeg processing failed: {stderr_output}")
                    raise Exception(f"Video processing failed: {stderr_output}")
                
                # Upload processed files
                successful_uploads = []
                for video_quote_path, s3_quote_key in video_quotes_paths_and_keys:
                    local_path = os.path.join(temp_dir, video_quote_path)
                    
                    if not os.path.exists(local_path):
                        logging.error(f"Processed file '{video_quote_path}' does not exist after processing")
                        continue
                    
                    if os.path.getsize(local_path) == 0:
                        logging.error(f"Processed file '{video_quote_path}' is empty")
                        continue
                    
                    try:
                        s3_client.upload_file(
                            local_path, 
                            VIDEO_QUOTE_BUCKET, 
                            s3_quote_key, 
                            ExtraArgs={
                                "ContentType": "video/mp4", 
                                "ACL": "public-read",
                                "CacheControl": "max-age=3600"  
                            }
                        )
                        successful_uploads.append((video_quote_path, s3_quote_key))
                        logging.info(f"Uploaded {video_quote_path} to s3://{VIDEO_BUCKET}/{s3_quote_key}")
                    except ClientError as e:
                        logging.error(f"Failed to upload {video_quote_path}: {e}")
                        continue
                
                logging.info(f"Successfully processed and uploaded {len(successful_uploads)}/{len(video_quotes_paths_and_keys)} video snippets")
                return successful_uploads
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
    except Exception as e:
        logging.error(f"Unexpected error in process_video_quotes: {e}")
        raise

def update_quote_video_status(podcast_title, episode_title, status):
    """
    Update the quote status in the metadata table.
    
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
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE) #type:ignore
        response = metadata_table.update_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            },
            UpdateExpression='SET quotes_video_status = :status, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':status': status,
                ':timestamp': int(boto3.Session().region_name and __import__('time').time() or 0)  # Add timestamp
            },
            ReturnValues='UPDATED_NEW'
        )

        logging.info(f"Updated quotes_video_status to '{status}' for {podcast_title}/{episode_title}")
        return response
    except ClientError as e:
        logging.error(f"Error updating quote video status for {podcast_title}/{episode_title}: {e}")
        raise

def update_quote_video_urls_in_dynamo(podcast_title, episode_title, quotes):
    """
    For each quote, generate quote_video_url and update the item in DynamoDB.
    
    Args:
        podcast_title (str): Title of the podcast
        episode_title (str): Title of the episode
        quotes (list): List of quote dictionaries or objects
        
    Returns:
        list: Updated quotes list
        
    Raises:
        ValueError: If input parameters are invalid
    """
    if not podcast_title or not episode_title:
        raise ValueError("podcast_title and episode_title cannot be empty")
        
    if not quotes:
        logging.warning("No quotes provided for URL updates")
        return []
    
    # Sanitize inputs for URLs
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()
    
    table = dynamodb.Table(QUOTES_TABLE) # type: ignore
    successful_updates = 0
    
    for i, quote in enumerate(quotes):
        sk = None  
        try:
            # Handle both dictionary and object formats
            if hasattr(quote, 'quote_rank'):
                quote_rank = quote.quote_rank
                sk = f"{episode_title}#{quote_rank}"
            elif isinstance(quote, dict):
                if 'episode_title#quote_rank' in quote:
                    sk = quote['episode_title#quote_rank']
                    quote_rank = sk.split('#')[-1]
                elif 'quote_rank' in quote:
                    quote_rank = quote['quote_rank']
                    sk = f"{episode_title}#{quote_rank}"
                else:
                    logging.error(f"Quote {i+1} missing required rank information")
                    continue
            else:
                logging.error(f"Quote {i+1} has invalid format")
                continue
            
            s3_key = f"{safe_podcast_title}/{safe_episode_title}/{quote_rank}.mp4"
            BASE_S3_VIDEO_URL = f"https://{VIDEO_QUOTE_BUCKET}.s3.amazonaws.com"
            encoded_key = urllib.parse.quote(s3_key, safe='/')  # Allow forward slashes in path
            quote_video_url = f"{BASE_S3_VIDEO_URL}/{encoded_key}"
            
            # Update quote object/dict
            if isinstance(quote, dict):
                quote['quote_video_url'] = quote_video_url
            else:
                quote.quote_video_url = quote_video_url

            # Update in DynamoDB
            table.update_item(
                Key={
                    'podcast_title': podcast_title,
                    'episode_title#quote_rank': sk
                },
                UpdateExpression='SET quote_video_url = :url, last_updated = :timestamp',
                ExpressionAttributeValues={
                    ':url': quote_video_url,
                    ':timestamp': int(__import__('time').time())
                }
            )
            successful_updates += 1
            logging.info(f"Updated quote_video_url for {sk}")
        except Exception as e:
            logging.error(f"Failed to update quote {i+1} ({sk if sk else 'unknown'}): {e}")
            continue

    logging.info(f"Successfully updated {successful_updates}/{len(quotes)} quote video URLs")
    return quotes