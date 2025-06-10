import logging
import tempfile
from typing import List, Tuple
import boto3
from botocore.exceptions import ClientError
import ffmpeg
import os.path
import urllib.parse

from models.summary_transcript_model import SummaryTranscriptModel, SummaryChunkTimestamp
from utils.config import PODCAST_METADATA_TABLE, VIDEO_BUCKET, VIDEO_SUMMARY_BUCKET
from utils.dynamo_att_to_types import dynamodb_attribute_to_python_type

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

def process_video_summary(podcast_title: str, 
                           episode_title: str, 
                           s3_video_key: str,
                           summaries_info: SummaryTranscriptModel, 
                           overwrite: bool = True) -> List[Tuple[str, str]]:
    """
    Merges multiple video summary snippets from a single input file into one combined video.
    Uses SummaryTranscriptModel with merged timestamp intervals.

    Args:
        podcast_title (str): Title of the podcast
        episode_title (str): Title of the episode
        s3_video_key (str): S3 key for the source video
        summaries_info (SummaryTranscriptModel): SummaryTranscriptModel with chunk timestamps
        overwrite (bool): Whether to overwrite output files if they exist.
    
    Returns:
        List[Tuple[str,str]]: List containing single (local_path, s3_key) tuple for the merged video
    """
    
    # Input validation
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    if not summaries_info or not summaries_info.summary_chunk_timestamps:
        logging.warning("No summary chunks provided for processing")
        return []
    
    # Sanitize inputs for file paths
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
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
                
                # Collect valid summary chunks
                valid_chunks = []
                for i, summary_chunk in enumerate(summaries_info.summary_chunk_timestamps):
                    try:
                        start_time = summary_chunk.start_time
                        end_time = summary_chunk.end_time
                        
                        if start_time is None or end_time is None:
                            logging.warning(f"Skipping summary chunk {i+1}/{len(summaries_info.summary_chunk_timestamps)} for {podcast_title}/{episode_title} due to missing timestamps")
                            continue
                            
                        if start_time < 0 or end_time < 0:
                            logging.warning(f"Skipping summary chunk {i+1} due to negative timestamps: start={start_time}, end={end_time}")
                            continue
                            
                        if start_time >= end_time:
                            logging.warning(f"Start time {start_time} >= end time {end_time} for summary chunk {i+1}. Skipping.")
                            continue
                        
                        duration = end_time - start_time
                        if duration < 0.1:
                            logging.warning(f"Skipping summary chunk {i+1} due to too short duration: {duration}s")
                            continue
                        
                        valid_chunks.append((start_time, end_time, duration, summary_chunk.word_count))
                        logging.info(f"Added summary chunk {i+1}/{len(summaries_info.summary_chunk_timestamps)} - {start_time:.2f}s to {end_time:.2f}s ({duration:.2f}s, {summary_chunk.word_count} words)")
                        
                    except (ValueError, AttributeError) as e:
                        logging.error(f"Error processing summary chunk {i+1}: {e}")
                        continue
                
                if not valid_chunks:
                    logging.warning("No valid summaries found for processing")
                    return []

                logging.info(f"Creating merged video from {len(valid_chunks)} valid summary chunks...")
                
                # Create individual chunk files first
                chunk_files = []
                for i, (start_time, end_time, duration, word_count) in enumerate(valid_chunks):
                    chunk_filename = f"chunk_{i+1}.mp4"
                    chunk_files.append(chunk_filename)
                    
                    # Extract individual chunk
                    chunk_input = ffmpeg.input(full_video_path, ss=start_time, t=duration)
                    chunk_output = ffmpeg.output(chunk_input, chunk_filename, 
                                               vcodec='libx264', 
                                               acodec='aac', 
                                               crf=23,
                                               preset='medium')
                    
                    try:
                        ffmpeg.run(chunk_output, capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                    except ffmpeg.Error as e:
                        stderr_output = e.stderr.decode('utf8', errors='ignore') if isinstance(e.stderr, bytes) else str(e.stderr)
                        logging.error(f"FFmpeg chunk extraction failed for chunk {i+1}: {stderr_output}")
                        raise Exception(f"Chunk extraction failed: {stderr_output}")
                
                # Create concat file for ffmpeg
                concat_filename = "concat_list.txt"
                with open(concat_filename, 'w') as f:
                    for chunk_file in chunk_files:
                        f.write(f"file '{chunk_file}'\n")
                
                # Merge all chunks into final video
                merged_video_filename = "merged_summary.mp4"
                s3_summary_key = f"{safe_podcast_title}/{safe_episode_title}/{merged_video_filename}"
                
                try:
                    # Use concat demuxer for better quality
                    concat_input = ffmpeg.input(concat_filename, format='concat', safe=0)
                    merged_output = ffmpeg.output(concat_input, merged_video_filename,
                                                vcodec='copy',  # Copy streams for faster processing
                                                acodec='copy',
                                                movflags='faststart')
                    
                    ffmpeg.run(merged_output, capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                    logging.info(f"Successfully merged {len(valid_chunks)} chunks into {merged_video_filename}")
                    
                except ffmpeg.Error as e:
                    stderr_output = e.stderr.decode('utf8', errors='ignore') if isinstance(e.stderr, bytes) else str(e.stderr)
                    logging.error(f"FFmpeg merging failed: {stderr_output}")
                    raise Exception(f"Video merging failed: {stderr_output}")
                
                # Verify merged file exists and has content
                local_path = os.path.join(temp_dir, merged_video_filename)
                if not os.path.exists(local_path):
                    raise Exception(f"Merged file '{merged_video_filename}' does not exist after processing")
                
                if os.path.getsize(local_path) == 0:
                    raise Exception(f"Merged file '{merged_video_filename}' is empty")
                
                # Upload merged video
                try:
                    s3_client.upload_file(
                        local_path, 
                        VIDEO_SUMMARY_BUCKET, 
                        s3_summary_key, 
                        ExtraArgs={
                            "ContentType": "video/mp4", 
                            "ACL": "public-read",
                            "CacheControl": "max-age=3600"  
                        }
                    )
                    logging.info(f"Uploaded merged video to s3://{VIDEO_SUMMARY_BUCKET}/{s3_summary_key}")
                    
                    total_duration = sum(chunk[2] for chunk in valid_chunks)
                    total_words = sum(chunk[3] for chunk in valid_chunks)
                    logging.info(f"Successfully processed merged video: {total_duration:.2f}s total duration, {total_words} total words")
                    
                    return [(merged_video_filename, s3_summary_key)]
                    
                except ClientError as e:
                    logging.error(f"Failed to upload merged video: {e}")
                    raise
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
    except Exception as e:
        logging.error(f"Unexpected error in process_video_summaries: {e}")
        raise

def update_video_summary_status(podcast_title, episode_title, status):
    """
    Update the summary video status in the metadata table.
    
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
            UpdateExpression='SET summaries_video_status = :status, last_updated = :timestamp',
            ExpressionAttributeValues={
                ':status': status,
                ':timestamp': int(__import__('time').time())
            },
            ReturnValues='UPDATED_NEW'
        )

        logging.info(f"Updated summaries_video_status to '{status}' for {podcast_title}/{episode_title}")
        return response
    except ClientError as e:
        logging.error(f"Error updating summary video status for {podcast_title}/{episode_title}: {e}")
        raise

def update_summary_video_urls_in_dynamo(podcast_title, episode_title, summaries):
    """
    For each summary, generate summary_video_url and update the item in DynamoDB.
    
    Args:
        podcast_title (str): Title of the podcast
        episode_title (str): Title of the episode
        summaries (list): List of summary dictionaries or objects
        
    Returns:
        list: Updated summaries list
        
    Raises:
        ValueError: If input parameters are invalid
    """
    if not podcast_title or not episode_title:
        raise ValueError("podcast_title and episode_title cannot be empty")
        
    if not summaries:
        logging.warning("No summaries provided for URL updates")
        return []
    
    # Sanitize inputs for URLs
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()
    
    table = dynamodb.Table(SUMMARY_TABLE) # type: ignore
    successful_updates = 0
    
    for i, summary in enumerate(summaries):
        sk = None  
        try:
            # Handle both dictionary and object formats
            if hasattr(summary, 'summary_rank'):
                summary_rank = summary.summary_rank
                sk = f"{episode_title}#{summary_rank}"
            elif isinstance(summary, dict):
                if 'episode_title#summary_rank' in summary:
                    sk = summary['episode_title#summary_rank']
                    summary_rank = sk.split('#')[-1]
                elif 'summary_rank' in summary:
                    summary_rank = summary['summary_rank']
                    sk = f"{episode_title}#{summary_rank}"
                else:
                    logging.error(f"Summary {i+1} missing required rank information")
                    continue
            else:
                logging.error(f"Summary {i+1} has invalid format")
                continue
            
            s3_key = f"{safe_podcast_title}/{safe_episode_title}/{summary_rank}.mp4"
            BASE_S3_VIDEO_URL = f"https://{VIDEO_SUMMARY_BUCKET}.s3.amazonaws.com"
            encoded_key = urllib.parse.quote(s3_key, safe='/')  # Allow forward slashes in path
            summary_video_url = f"{BASE_S3_VIDEO_URL}/{encoded_key}"
            
            # Update summary object/dict
            if isinstance(summary, dict):
                summary['summary_video_url'] = summary_video_url
            else:
                summary.summary_video_url = summary_video_url

            # Update in DynamoDB
            table.update_item(
                Key={
                    'podcast_title': podcast_title,
                    'episode_title#summary_rank': sk
                },
                UpdateExpression='SET summary_video_url = :url, last_updated = :timestamp',
                ExpressionAttributeValues={
                    ':url': summary_video_url,
                    ':timestamp': int(__import__('time').time())
                }
            )
            successful_updates += 1
            logging.info(f"Updated summary_video_url for {sk}")
        except Exception as e:
            logging.error(f"Failed to update summary {i+1} ({sk if sk else 'unknown'}): {e}")
            continue

    logging.info(f"Successfully updated {successful_updates}/{len(summaries)} summary video URLs")
    return summaries