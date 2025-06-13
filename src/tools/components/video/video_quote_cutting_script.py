
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
from utils.aws_clients import get_dynamodb_resource, get_s3_client
from utils.logging_config import setup_custom_logger
logging = setup_custom_logger(__name__)
dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()

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
        raise ValueError("podcast_title, episode_title, or s3_video_key are empty")
    
    if not snippets_info:
        logging.warning("No snippets provided for processing")
        return []
    logging.info(len(snippets_info))
    # Sanitize inputs for file paths
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
        video_quotes_paths_and_keys = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
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
                
                # Process each quote sequentially
                ffmpeg_processed_count = 0 # Counts quotes successfully processed by ffmpeg in this run
                for i, quote in enumerate(snippets_info):
                    logging.info(f"Processing quote {i+1}/{len(snippets_info)}: {quote.context_timestamps}")
                    video_quotes_filename = None # Initialize for error handling in case of early failure
                    try:
                        # Ensure context_timestamps and its attributes exist
                        if not hasattr(quote, 'context_timestamps') or \
                           not hasattr(quote.context_timestamps, 'start_time') or \
                           not hasattr(quote.context_timestamps, 'end_time'):
                            logging.warning(f"Skipping quote {i+1}/{len(snippets_info)} for {podcast_title}/{episode_title} due to missing timestamp structure.")
                            continue

                        start_time_str = quote.context_timestamps.start_time
                        end_time_str = quote.context_timestamps.end_time

                        if start_time_str is None or end_time_str is None:
                            logging.warning(f"Skipping quote {i+1}/{len(snippets_info)} for {podcast_title}/{episode_title} due to missing start or end time values.")
                            continue
                        
                        try:
                            start_time = float(start_time_str)
                            end_time = float(end_time_str)
                        except (ValueError, TypeError) as e:
                            logging.warning(f"Skipping quote {i+1} due to invalid timestamp format: start='{start_time_str}', end='{end_time_str}'. Error: {e}")
                            continue
                            
                        if start_time < 0 or end_time < 0:
                            logging.warning(f"Skipping quote {i+1} due to negative timestamps: start={start_time}, end={end_time}")
                            continue
                            
                        if start_time > end_time:
                            logging.warning(f"Start time {start_time} > end time {end_time} for quote {i+1}. Swapping values.")
                            start_time, end_time = end_time, start_time
                        
                        duration = end_time - start_time
                        if duration < 0.1: # Minimum 0.1 second duration
                            logging.warning(f"Skipping quote {i+1} due to too short duration: {duration}s")
                            continue
                        
                        video_quotes_filename = f"{quote.quote_rank}.mp4"
                        s3_quote_key = f"{safe_podcast_title}/{safe_episode_title}/{video_quotes_filename}"
                        
                        # Note: S3 existence check and skipping if not overwrite (like in chunk script) is not implemented here.
                        # If needed, it would go here.

                        logging.info(f"Preparing ffmpeg operation for quote {i+1} ({video_quotes_filename}): {start_time:.2f}s to {end_time:.2f}s ({duration:.2f}s)")
                        input_stream = ffmpeg.input(full_video_path, ss=start_time, t=duration)
                        output_op = ffmpeg.output(
                            input_stream,
                            video_quotes_filename, 
                            vcodec='h264_vaapi', #libx264 for CPU encoding, h264_nvenc for GPU encoding''
                            acodec='aac', 
                            crf=23,
                            preset='medium',
                            movflags='+faststart'
                        )
                        
                        logging.info(f"Executing ffmpeg for quote {i+1} ({video_quotes_filename})...")
                        try:
                            # Execute ffmpeg for this single quote.
                            # overwrite_output=overwrite ensures local file is overwritten if it exists from a previous attempt.
                            ffmpeg.run(output_op, capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                            logging.info(f"Successfully processed quote {i+1} ({video_quotes_filename}) with ffmpeg.")
                            video_quotes_paths_and_keys.append((video_quotes_filename, s3_quote_key))
                            ffmpeg_processed_count += 1
                        except ffmpeg.Error as e_ffmpeg:
                            stderr_output = e_ffmpeg.stderr.decode('utf8', errors='ignore') if isinstance(e_ffmpeg.stderr, bytes) else str(e_ffmpeg.stderr)
                            logging.error(f"FFmpeg processing failed for quote {i+1} ({video_quotes_filename}): {stderr_output}")
                            # Do not add to video_quotes_paths_and_keys as it failed.
                            continue # to the next quote
                        
                    except (ValueError, AttributeError, TypeError) as e_data: # Catch issues with quote data or timestamp conversion
                        logging.error(f"Error preparing quote {i+1} (filename: {video_quotes_filename if video_quotes_filename else 'unknown'}) due to invalid data: {e_data}")
                        continue # to the next quote
                    except Exception as e_inner_loop: # Catch any other unexpected error for this specific quote
                        logging.error(f"Error preparing or processing quote {i+1} (filename: {video_quotes_filename if video_quotes_filename else 'unknown'}): {e_inner_loop}")
                        continue # to the next quote
                
                if not video_quotes_paths_and_keys:
                    logging.warning("No video quotes available for upload (none processed successfully by ffmpeg).")
                    return []
                successful_uploads = []
                logging.info(f"Starting upload process for {len(video_quotes_paths_and_keys)} referenced quotes ({ffmpeg_processed_count} processed by ffmpeg in this run).")
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
                        logging.info(f"Uploaded {video_quote_path} to s3://{VIDEO_QUOTE_BUCKET}/{s3_quote_key}")
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