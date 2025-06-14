import tempfile
from typing import List, Tuple
import boto3
from botocore.exceptions import ClientError
import ffmpeg
import os.path
import urllib.parse

from models.quote_model import Quote
from utils.config import PODCAST_METADATA_TABLE, QUOTES_TABLE, VIDEO_BUCKET, VIDEO_QUOTE_BUCKET
from utils.aws_clients import get_dynamodb_resource, get_s3_client
from utils.logging_config import setup_custom_logger

logging = setup_custom_logger(__name__)
dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()

def process_video_quotes(podcast_title: str, 
                         episode_title: str, 
                         s3_video_key: str,
                         snippets_info: List[Quote], 
                         overwrite: bool = True) -> List[Tuple[str, str]]:
    """
    Simple sequential video quote processing.
    Cuts video snippets from a single input file.
    """
    
    # Input validation
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, or s3_video_key are empty")
    
    if not snippets_info:
        logging.warning("No snippets provided for processing")
        return []
    
    logging.info(f"Processing {len(snippets_info)} quotes")
    
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
        successful_uploads = []
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory(prefix="video_quotes_") as temp_dir:
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
            
            # Process each quote
            for i, quote in enumerate(snippets_info):
                try:
                    logging.info(f"Processing quote {i+1}/{len(snippets_info)}: {quote.episode_title_quote_rank}")
                    
                    # Validate quote timestamps
                    if not hasattr(quote, 'context_timestamps') or \
                       not hasattr(quote.context_timestamps, 'start_time') or \
                       not hasattr(quote.context_timestamps, 'end_time'):
                        logging.warning(f"Skipping quote {i+1} due to missing timestamp structure")
                        continue

                    start_time_str = quote.context_timestamps.start_time
                    end_time_str = quote.context_timestamps.end_time

                    if start_time_str is None or end_time_str is None:
                        logging.warning(f"Skipping quote {i+1} due to missing timestamp values")
                        continue
                    
                    try:
                        start_time = float(start_time_str)
                        end_time = float(end_time_str)
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Skipping quote {i+1} due to invalid timestamp format: {e}")
                        continue
                    
                    # Validate timestamp values
                    if start_time < 0 or end_time < 0:
                        logging.warning(f"Skipping quote {i+1} due to negative timestamps")
                        continue
                        
                    if start_time > end_time:
                        logging.warning(f"Swapping timestamps for quote {i+1}: start={start_time}, end={end_time}")
                        start_time, end_time = end_time, start_time
                    
                    duration = end_time - start_time
                    if duration < 0.1:
                        logging.warning(f"Skipping quote {i+1} due to too short duration: {duration}s")
                        continue
                    
                    # Prepare file paths
                    quote_filename = f"{quote.episode_title_quote_rank}.mp4"
                    quote_path = os.path.join(temp_dir, quote_filename)
                    s3_quote_key = f"{safe_podcast_title}/{safe_episode_title}/{quote_filename}"

                    # Process with FFmpeg
                    logging.info(f"Processing quote {quote_filename}: {start_time:.2f}s to {end_time:.2f}s")
                    try:
                        (
                            ffmpeg
                            .input(full_video_path, ss=start_time, t=duration)
                            .output(quote_path, vcodec='libx264', acodec='aac', crf=23, preset='medium', movflags='+faststart')
                            .overwrite_output()
                            .run(capture_stdout=True, capture_stderr=True)
                        )
                        
                        # Verify output file was created
                        if not os.path.exists(quote_path) or os.path.getsize(quote_path) == 0:
                            logging.error(f"FFmpeg did not create valid output for quote {quote_filename}")
                            continue
                            
                    except ffmpeg.Error as e:
                        stderr = e.stderr.decode('utf8', errors='ignore') if e.stderr else "No error output"
                        logging.error(f"FFmpeg failed for quote {quote_filename}: {stderr}")
                        continue
                    
                    # Upload to S3
                    try:
                        s3_client.upload_file(
                            quote_path, 
                            VIDEO_QUOTE_BUCKET, 
                            s3_quote_key, 
                            ExtraArgs={
                                "ContentType": "video/mp4", 
                                "ACL": "public-read",
                                "CacheControl": "max-age=3600"  
                            }
                        )
                        successful_uploads.append((quote_filename, s3_quote_key))
                        logging.info(f"Uploaded {quote_filename} to S3")
                        
                    except ClientError as e:
                        logging.error(f"Failed to upload {quote_filename}: {e}")
                        continue
                        
                except Exception as e:
                    logging.error(f"Error processing quote {i+1}: {e}")
                    continue
            
            logging.info(f"Successfully processed {len(successful_uploads)}/{len(snippets_info)} quotes")
            return successful_uploads
                
    except Exception as e:
        logging.error(f"Error in process_video_quotes: {e}")
        raise

def update_quote_video_status(podcast_title, episode_title, status):
    """Update the quote status in the metadata table."""
    if not podcast_title or not episode_title or not status:
        raise ValueError("podcast_title, episode_title, and status cannot be empty")
    
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.update_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            },
            UpdateExpression='SET quotes_video_status = :status, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':status': status,
                ':timestamp': int(__import__('time').time())
            },
            ReturnValues='UPDATED_NEW'
        )
        logging.info(f"Updated quotes_video_status to '{status}' for {podcast_title}/{episode_title}")
        return response
    except ClientError as e:
        logging.error(f"Error updating quote video status: {e}")
        raise

def update_quote_video_urls_in_dynamo(podcast_title, episode_title, quotes):
    """Update quote video URLs in DynamoDB."""
    if not podcast_title or not episode_title or not quotes:
        return []
    
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()
    
    table = dynamodb.Table(QUOTES_TABLE)
    BASE_S3_VIDEO_URL = f"https://{VIDEO_QUOTE_BUCKET}.s3.amazonaws.com"
    
    for quote in quotes:
        try:
            # Handle both dictionary and object formats
            if hasattr(quote, 'quote_rank'):
                quote_rank = quote.quote_rank
                sk = f"{episode_title}#{quote_rank}"
            elif isinstance(quote, dict) and 'quote_rank' in quote:
                quote_rank = quote['quote_rank']
                sk = f"{episode_title}#{quote_rank}"
            else:
                logging.error(f"Quote missing required rank information")
                continue
            
            s3_key = f"{safe_podcast_title}/{safe_episode_title}/{quote_rank}.mp4"
            encoded_key = urllib.parse.quote(s3_key, safe='/')
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
            logging.info(f"Updated quote_video_url for {sk}")
        except Exception as e:
            logging.error(f"Failed to update quote URL: {e}")

    return quotes