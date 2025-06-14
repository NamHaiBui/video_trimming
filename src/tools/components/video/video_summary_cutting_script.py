import shutil
import tempfile
from typing import List, Tuple
import boto3
from botocore.exceptions import ClientError
import ffmpeg
import os.path

from models.summary_transcript_model import SummaryTranscriptModel
from utils.config import PODCAST_METADATA_TABLE, VIDEO_BUCKET, VIDEO_SUMMARY_BUCKET
from utils.aws_clients import get_dynamodb_resource, get_s3_client
from utils.logging_config import setup_custom_logger

logging = setup_custom_logger(__name__)
dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()

def process_video_summary(podcast_title: str, 
                           episode_title: str, 
                           s3_video_key: str,
                           summaries_info: SummaryTranscriptModel, 
                           overwrite: bool = True) -> List[Tuple[str, str]]:
    """
    Simple sequential video summary processing.
    Merges multiple video summary snippets into one combined video.
    """
    
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    if not summaries_info or not summaries_info.summary_chunk_timestamps:
        logging.warning("No summary chunks provided for processing")
        return []
    
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory(prefix="video_summary_") as temp_dir:
            # Download source video
            full_video_path = os.path.join(temp_dir, "source_video.mp4")
            
            try:
                logging.info(f"Downloading source video from s3://{VIDEO_BUCKET}/{s3_video_key}")
                s3_client.download_file(VIDEO_BUCKET, s3_video_key, full_video_path)
            except ClientError as e:
                logging.error(f"Failed to download source video: {e}")
                raise
            
            if not os.path.exists(full_video_path) or os.path.getsize(full_video_path) == 0:
                raise Exception("Downloaded video file is empty or missing")
            
            # Filter and validate chunks
            valid_chunks = []
            for i, chunk in enumerate(summaries_info.summary_chunk_timestamps):
                if chunk.duration() > 3:  # Only include chunks longer than 3 seconds
                    start_time = chunk.start_time
                    end_time = chunk.end_time
                    
                    if start_time is not None and end_time is not None and start_time >= 0 and end_time > start_time:
                        valid_chunks.append({
                            "start": start_time,
                            "duration": end_time - start_time,
                            "index": i
                        })
                        logging.info(f"Valid summary chunk {i+1}: {start_time:.2f}s for {end_time - start_time:.2f}s")
            
            if not valid_chunks:
                logging.warning("No valid summary chunks found")
                return []

            # Extract individual chunks
            extracted_files = []
            for chunk_data in valid_chunks:
                chunk_filename = f"chunk_{chunk_data['index']}.mp4"
                chunk_path = os.path.join(temp_dir, chunk_filename)
                
                try:
                    (
                        ffmpeg
                        .input(full_video_path, ss=chunk_data["start"], t=chunk_data["duration"])
                        .output(chunk_path, vcodec='libx264', acodec='aac', crf=23, preset='medium', movflags='+faststart')
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    
                    if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                        extracted_files.append(chunk_filename)
                        logging.info(f"Extracted chunk: {chunk_filename}")
                    
                except ffmpeg.Error as e:
                    stderr = e.stderr.decode('utf8', errors='ignore') if e.stderr else "No error output"
                    logging.error(f"Failed to extract chunk {chunk_filename}: {stderr}")
                    continue

            if not extracted_files:
                logging.warning("No chunks were successfully extracted")
                return []

            # Prepare final merged video
            merged_filename = "merged_summary.mp4"
            merged_path = os.path.join(temp_dir, merged_filename)
            s3_summary_key = f"{safe_podcast_title}/{safe_episode_title}/{merged_filename}"

            if len(extracted_files) == 1:
                # Single chunk - just rename it
                shutil.move(os.path.join(temp_dir, extracted_files[0]), merged_path)
                logging.info("Single summary chunk, using as merged video")
            else:
                # Multiple chunks - concatenate with black gaps
                logging.info(f"Merging {len(extracted_files)} chunks with black gaps")
                
                # Create concat file list
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                
                # Generate a simple black gap video
                black_gap_path = os.path.join(temp_dir, "black_gap.mp4")
                try:
                    (
                        ffmpeg
                        .input('color=c=black:s=1280x720:d=0.5', format='lavfi')
                        .input('anullsrc=channel_layout=stereo:sample_rate=44100:d=0.5', format='lavfi')
                        .output(black_gap_path, vcodec='libx264', acodec='aac', t=0.5)
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                except ffmpeg.Error as e:
                    logging.warning("Failed to create black gap, proceeding without gaps")
                    black_gap_path = None
                
                # Write concat list
                with open(concat_file, 'w') as f:
                    for i, chunk_file in enumerate(extracted_files):
                        f.write(f"file '{os.path.join(temp_dir, chunk_file)}'\n")
                        if i < len(extracted_files) - 1 and black_gap_path:
                            f.write(f"file '{black_gap_path}'\n")
                
                # Concatenate videos
                try:
                    (
                        ffmpeg
                        .input(concat_file, format='concat', safe=0)
                        .output(merged_path, vcodec='libx264', acodec='aac', crf=23, preset='medium', movflags='+faststart')
                        .overwrite_output()
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                except ffmpeg.Error as e:
                    stderr = e.stderr.decode('utf8', errors='ignore') if e.stderr else "No error output"
                    logging.error(f"Failed to merge videos: {stderr}")
                    raise Exception(f"Video merging failed: {stderr}")

            # Verify merged file
            if not os.path.exists(merged_path) or os.path.getsize(merged_path) == 0:
                raise Exception("Merged video file was not created or is empty")
            
            # Upload to S3
            try:
                s3_client.upload_file(
                    merged_path, 
                    VIDEO_SUMMARY_BUCKET, 
                    s3_summary_key, 
                    ExtraArgs={"ContentType": "video/mp4", "ACL": "public-read", "CacheControl": "max-age=3600"}
                )
                logging.info(f"Uploaded merged video to s3://{VIDEO_SUMMARY_BUCKET}/{s3_summary_key}")
                
                total_duration = sum(chunk["duration"] for chunk in valid_chunks)
                logging.info(f"Successfully processed merged video: {total_duration:.2f}s total duration")
                
                return [(merged_filename, s3_summary_key)]
                
            except ClientError as e:
                logging.error(f"Failed to upload merged video: {e}")
                raise
                
    except Exception as e:
        logging.error(f"Error in process_video_summary: {e}")
        raise

def update_video_summary_status(podcast_title, episode_title, status):
    """Update the summary video status in the metadata table."""
    if not podcast_title or not episode_title or not status:
        raise ValueError("podcast_title, episode_title, and status cannot be empty")
    
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
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
        logging.error(f"Error updating summary video status: {e}")
        raise

