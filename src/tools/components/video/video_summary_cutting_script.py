import shutil
import tempfile
from typing import List, Tuple
import boto3
from botocore.exceptions import ClientError
import ffmpeg
import os.path
import urllib.parse

from models.summary_transcript_model import SummaryTranscriptModel, SummaryChunkTimestamp
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
    Merges multiple video summary snippets from a single input file into one combined video,
    with a short black screen gap between each snippet.
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
    
    if not podcast_title or not episode_title or not s3_video_key:
        raise ValueError("podcast_title, episode_title, and s3_video_key cannot be empty")
    
    if not summaries_info or not summaries_info.summary_chunk_timestamps:
        logging.warning("No summary chunks provided for processing")
        return []
    
    safe_podcast_title = "".join(c for c in podcast_title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_episode_title = "".join(c for c in episode_title if c.isalnum() or c in (' ', '-', '_')).strip()

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                full_video_path = os.path.join(temp_dir, "full_video.mp4")
                
                try:
                    s3_client.download_file(VIDEO_BUCKET, s3_video_key, full_video_path)
                    logging.info(f"Downloaded source video from s3://{VIDEO_BUCKET}/{s3_video_key}")
                except ClientError as e:
                    logging.error(f"Failed to download source video: {e}")
                    raise
                
                if not os.path.exists(full_video_path) or os.path.getsize(full_video_path) == 0:
                    raise Exception("Downloaded video file is empty or missing")
                summaries_info.summary_chunk_timestamps = [x for x in summaries_info.summary_chunk_timestamps if x.duration() > 3]
                valid_chunks_data = []
                for i, summary_chunk in enumerate(summaries_info.summary_chunk_timestamps):
                    try:
                        start_time = summary_chunk.start_time
                        end_time = summary_chunk.end_time
                        
                        if start_time is None or end_time is None:
                            logging.warning(f"Skipping summary chunk {i+1} due to missing timestamps")
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
                        
                        valid_chunks_data.append({
                            "start": start_time, "duration": duration, 
                            "word_count": summary_chunk.word_count, "index": i
                        })
                        logging.info(f"Validated summary chunk {i+1}: {start_time:.2f}s for {duration:.2f}s ({summary_chunk.word_count} words)")
                        
                    except (ValueError, AttributeError, TypeError) as e:
                        logging.error(f"Error processing summary chunk {i+1} data: {e}")
                        continue
                
                if not valid_chunks_data:
                    logging.warning("No valid summary chunks found for processing after validation.")
                    return []

                logging.info(f"Extracting {len(valid_chunks_data)} valid summary chunks individually...")
                extracted_chunk_files = []
                for chunk_data in valid_chunks_data:
                    idx = chunk_data["index"]
                    start = chunk_data["start"]
                    duration = chunk_data["duration"]
                    chunk_filename = f"temp_summary_chunk_{idx}.mp4"
                    
                    try:
                        chunk_input = ffmpeg.input(full_video_path, ss=start, t=duration)
                        chunk_output_op = ffmpeg.output(chunk_input, chunk_filename, 
                                                       vcodec='libx264', acodec='aac', 
                                                       crf=23, preset='medium',
                                                       movflags='+faststart')
                        ffmpeg.run(chunk_output_op, capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                        extracted_chunk_files.append(chunk_filename)
                        logging.info(f"Successfully extracted chunk {idx+1} to {chunk_filename}")
                    except ffmpeg.Error as e:
                        stderr_output = e.stderr.decode('utf8', errors='ignore')
                        logging.error(f"FFmpeg chunk extraction failed for chunk {idx+1}: {stderr_output}")
                        # Decide if one failed chunk should stop all, or just skip this one.
                        # For now, let's be strict and raise, or one could 'continue'
                        raise Exception(f"Chunk extraction failed for chunk {idx+1}: {stderr_output}")

                if not extracted_chunk_files:
                    logging.warning("No chunks were successfully extracted.")
                    return []

                merged_video_filename = "merged_summary.mp4"
                s3_summary_key = f"{safe_podcast_title}/{safe_episode_title}/{merged_video_filename}"
                final_merged_path = os.path.join(temp_dir, merged_video_filename)

                if len(extracted_chunk_files) == 1:
                    # If only one chunk, rename it to the final merged filename
                    single_chunk_path = os.path.join(temp_dir, extracted_chunk_files[0])
                    shutil.move(single_chunk_path, final_merged_path) # Use shutil.move for rename
                    logging.info(f"Single summary chunk. Using '{extracted_chunk_files[0]}' as '{merged_video_filename}'.")
                else:
                    # Multiple chunks: generate black gap, then concatenate
                    logging.info(f"Preparing to merge {len(extracted_chunk_files)} chunks with black screen gaps...")
                    gap_duration = 0.5  # seconds
                    black_gap_filename = "black_gap.mp4"
                    black_gap_filepath = os.path.join(temp_dir, black_gap_filename)

                    try:
                        # Probe first chunk for video properties
                        first_chunk_probe_path = os.path.join(temp_dir, extracted_chunk_files[0])
                        probe = ffmpeg.probe(first_chunk_probe_path)
                        video_stream_info = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
                        audio_stream_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)

                        if not video_stream_info:
                            raise ValueError("No video stream found in the first chunk for probing.")

                        width = video_stream_info.get('width', 1280)
                        height = video_stream_info.get('height', 720)
                        frame_rate = video_stream_info.get('r_frame_rate', '25/1')
                        
                        audio_sample_rate = audio_stream_info.get('sample_rate', '44100') if audio_stream_info else '44100'
                        audio_channels = audio_stream_info.get('channels', 2) if audio_stream_info else 2

                        # Generate black screen gap clip with simpler approach
                        logging.info(f"Generating black gap: {width}x{height}, {frame_rate}fps, {gap_duration}s")
                        
                        # Use more compatible settings
                        black_video_input = ffmpeg.input(f'color=c=black:s={width}x{height}:d={gap_duration}', format='lavfi')
                        silent_audio_input = ffmpeg.input(f'anullsrc=channel_layout=stereo:sample_rate={audio_sample_rate}:d={gap_duration}', format='lavfi')
                        
                        black_gap_output = ffmpeg.output(
                            black_video_input, silent_audio_input, black_gap_filepath,
                            vcodec='libx264',  # Use standard CPU encoder
                            acodec='aac', 
                            preset='fast',  # Faster preset for gap generation
                            crf=23,
                            pix_fmt='yuv420p',  # Ensure compatibility
                            r=frame_rate,
                            s=f'{width}x{height}',
                            ar=audio_sample_rate, 
                            ac=audio_channels,
                            t=gap_duration,
                            movflags='+faststart'
                        )
                        
                        ffmpeg.run(black_gap_output, capture_stdout=True, capture_stderr=True, overwrite_output=True)
                        
                        # Verify the gap file was created
                        if not os.path.exists(black_gap_filepath) or os.path.getsize(black_gap_filepath) == 0:
                            raise Exception(f"Black gap file was not created or is empty: {black_gap_filepath}")
                            
                        logging.info(f"Generated black gap clip: {black_gap_filename}")
                    except ffmpeg.Error as e_gap:
                        stderr_output = e_gap.stderr.decode('utf8', errors='ignore') if e_gap.stderr else "No stderr available"
                        logging.error(f"FFmpeg error generating black gap: {stderr_output}")
                        raise Exception(f"Failed to generate black gap clip: {stderr_output}")
                    except Exception as e_gap:
                        logging.error(f"Failed to generate black gap clip: {e_gap}")
                        raise

                    # Prepare list of input files for concatenation using a text file approach
                    concat_list_file = os.path.join(temp_dir, "concat_list.txt")
                    
                    # Write the concatenation list to a file (FFmpeg concat demuxer approach)
                    with open(concat_list_file, 'w') as f:
                        for i, chunk_f in enumerate(extracted_chunk_files):
                            chunk_path = os.path.join(temp_dir, chunk_f)
                            f.write(f"file '{chunk_path}'\n")
                            
                            # Add black gap between chunks (except after the last chunk)
                            if i < len(extracted_chunk_files) - 1:
                                f.write(f"file '{black_gap_filepath}'\n")
                    
                    logging.info(f"Created concatenation list with {len(extracted_chunk_files)} chunks and {len(extracted_chunk_files)-1} gaps")
                    
                    try:
                        # Use the concat demuxer which is more efficient for many files
                        concat_input = ffmpeg.input(concat_list_file, format='concat', safe=0)
                        merged_output_op = ffmpeg.output(
                            concat_input,
                            final_merged_path,
                            vcodec='libx264',  # Use CPU encoder for better compatibility
                            acodec='aac', 
                            crf=23, 
                            preset='medium',
                            movflags='+faststart'
                        )
                        ffmpeg.run(merged_output_op, capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
                        logging.info(f"Successfully merged {len(extracted_chunk_files)} chunks with gaps into {merged_video_filename}")
                    except ffmpeg.Error as e_concat:
                        stderr_output = e_concat.stderr.decode('utf8', errors='ignore')
                        logging.error(f"FFmpeg merging with concat demuxer failed: {stderr_output}")
                        # Log additional debug info
                        with open(concat_list_file, 'r') as f:
                            concat_content = f.read()
                            logging.error(f"Concat file content (first 10 lines):\n{concat_content[:500]}...")
                        raise Exception(f"Video merging with concat demuxer failed: {stderr_output}")

                # Verify merged file exists and has content (applies to both single and multi-chunk cases)
                if not os.path.exists(final_merged_path):
                    raise Exception(f"Merged file '{merged_video_filename}' does not exist after processing")
                if os.path.getsize(final_merged_path) == 0:
                    raise Exception(f"Merged file '{merged_video_filename}' is empty")
                
                # Upload merged video
                try:
                    s3_client.upload_file(
                        final_merged_path, 
                        VIDEO_SUMMARY_BUCKET, 
                        s3_summary_key, 
                        ExtraArgs={"ContentType": "video/mp4", "ACL": "public-read", "CacheControl": "max-age=3600"}
                    )
                    logging.info(f"Uploaded merged video to s3://{VIDEO_SUMMARY_BUCKET}/{s3_summary_key}")
                    
                    total_duration_data = sum(vc["duration"] for vc in valid_chunks_data)
                    total_words_data = sum(vc["word_count"] for vc in valid_chunks_data)
                    logging.info(f"Successfully processed merged video: {total_duration_data:.2f}s content duration, {total_words_data} total words")
                    
                    return [(merged_video_filename, s3_summary_key)]
                    
                except ClientError as e_upload:
                    logging.error(f"Failed to upload merged video: {e_upload}")
                    raise
                
            finally:
                os.chdir(original_cwd)
                
    except Exception as e_main:
        logging.error(f"Unexpected error in process_video_summary: {e_main}")
        # Consider how to handle partial cleanup if temp_dir context manager fails early
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

