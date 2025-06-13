import boto3
import json
import time
import os
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread

from boto3.dynamodb.conditions import Key
from pydub.utils import which
from utils.config import PODCAST_METADATA_TABLE

from tools.components.video.video_chunk_cutting_script import process_video_chunks, update_video_chunking_status
from tools.components.video.video_quote_cutting_script import process_video_quotes, update_quote_video_status
from tools.components.video.video_summary_cutting_script import process_video_summary, update_video_summary_status
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, get_all_quotes, get_summary_data
from utils.aws_clients import get_dynamodb_resource, get_s3_client
                        
logging = setup_custom_logger(__name__)


# Initialize the ECS client
# ecs = boto3.client('ecs', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()


ffmpeg_path = which("ffmpeg")

def process_video_chunks_background(podcast_title, episode_title, s3_video_key, chunks, num_chunks, meta_data_idx, force_video_chunking):
    """
    Background process for video chunking
    """
    try:
        video_chunking_status = get_video_chunking_status(podcast_title, episode_title)
        
        if video_chunking_status == 'COMPLETED' and not force_video_chunking:
            logging.info(f"Video chunking already completed for ID: {meta_data_idx}, skipping processing...")
            return {"status": "COMPLETED", "type": "chunks", "message": "Already completed"}
        elif video_chunking_status == 'IN_PROGRESS':
            logging.info(f"Video chunking in progress for ID: {meta_data_idx}, skipping processing...")
            return {"status": "IN_PROGRESS", "type": "chunks", "message": "Already in progress"}
        else:
            logging.info(f"Video chunking not completed for ID: {meta_data_idx}, processing...")
            # Update metadata to mark chunking as in progress
            update_video_chunking_status(podcast_title, episode_title, 'IN_PROGRESS')

            logging.info(f"Processing video chunking for ID: {meta_data_idx}")
            
            # Download and process video
            if chunks:
                logging.info(f"Processing video {len(chunks)} chunks for {podcast_title}/{episode_title}")
                video_chunk_paths = process_video_chunks(
                    podcast_title=podcast_title, 
                    episode_title=episode_title, 
                    s3_video_key=s3_video_key, 
                    chunks_info=chunks
                )
                if len(video_chunk_paths) != int(num_chunks):
                    update_video_chunking_status(podcast_title, episode_title, 'FAILED')
                    logging.error(f"Number of video chunks ({len(video_chunk_paths)}) does not match number of chunks ({num_chunks})")
                    return {"status": "FAILED", "type": "chunks", "message": f"Chunk count mismatch: {len(video_chunk_paths)} != {num_chunks}"}
                elif len(video_chunk_paths) == int(num_chunks):
                    update_video_chunking_status(podcast_title, episode_title, 'COMPLETED')
                    logging.info(f"Video chunking completed for ID: {meta_data_idx}")
                    return {"status": "COMPLETED", "type": "chunks", "message": "Successfully completed", "paths": video_chunk_paths}
    except Exception as e:
        logging.error(f"Error processing video chunks: {e}")
        update_video_chunking_status(podcast_title, episode_title, 'FAILED')
        return {"status": "FAILED", "type": "chunks", "message": str(e)}

def process_video_quotes_background(podcast_title, episode_title, s3_video_key, quotes, num_quotes, meta_data_idx, force_video_quote_extraction):
    """
    Background process for video quote extraction
    """
    try:
        quotes_video_status = get_quotes_video_status(podcast_title, episode_title)
        
        if quotes_video_status == 'COMPLETED' and not force_video_quote_extraction:
            logging.info(f"Quote video extraction already completed for ID: {meta_data_idx}, skipping processing...")
            return {"status": "COMPLETED", "type": "quotes", "message": "Already completed"}
        elif quotes_video_status == 'IN_PROGRESS':
            logging.info(f"Quote video extraction in progress for ID: {meta_data_idx}, skipping processing...")
            return {"status": "IN_PROGRESS", "type": "quotes", "message": "Already in progress"}
        else:
            logging.info(f"Quote video extraction not completed for ID: {meta_data_idx}, processing...")
            # Update metadata to mark chunking as in progress
            update_quote_video_status(podcast_title, episode_title, 'IN_PROGRESS')

            logging.info(f"Processing video quotes for ID: {meta_data_idx}")
            
            # Download and process video
            if quotes:
                logging.info(f"Processing video with {len(quotes)} quotes for {podcast_title}/{episode_title}")
                
                video_quote_paths = process_video_quotes(
                    podcast_title,
                    episode_title,
                    s3_video_key,
                    snippets_info=quotes
                )
                
                if len(video_quote_paths) != int(num_quotes):
                    update_quote_video_status(podcast_title, episode_title, 'COMPLETED')
                    logging.warning(f"Number of video quotes ({len(video_quote_paths)}) does not match number of quotes ({num_quotes})")
                    return {"status": "COMPLETED", "type": "quotes", "message": f"Quote count mismatch: {len(video_quote_paths)} != {num_quotes}", "paths": video_quote_paths}
                elif len(video_quote_paths) == int(num_quotes):
                    update_quote_video_status(podcast_title, episode_title, 'COMPLETED')
                    logging.info(f"Video quotes completed for ID: {meta_data_idx}")
                    return {"status": "COMPLETED", "type": "quotes", "message": "Successfully completed", "paths": video_quote_paths}
        
        return {"status": "COMPLETED", "type": "quotes", "message": "Completed"}
    except Exception as e:
        logging.error(f"Error processing video quotes: {e}")
        update_quote_video_status(podcast_title, episode_title, 'FAILED')
        return {"status": "FAILED", "type": "quotes", "message": str(e)}

def process_video_summaries_background(podcast_title, episode_title, s3_video_key, meta_data_idx, force_video_summary_extraction):
    """
    Background process for video summary extraction
    """
    try:
        summarization_status = get_summarization_status(podcast_title, episode_title)
        summaries_video_status = get_summaries_video_status(podcast_title, episode_title)
        
        if summarization_status == 'COMPLETED':
            # Get summary data and create SummaryTranscriptModel
            summary_data = get_summary_data(podcast_title, episode_title)
            if summary_data:
                logging.info(f"Created summary transcript with {summary_data.total_chunks} merged chunks for ID: {meta_data_idx}")

                if summaries_video_status == 'COMPLETED' and not force_video_summary_extraction:
                    logging.info(f"Summary video extraction already completed for ID: {meta_data_idx}, skipping processing...")
                    return {"status": "COMPLETED", "type": "summaries", "message": "Already completed"}
                elif summaries_video_status == 'IN_PROGRESS' and not force_video_summary_extraction:
                    logging.info(f"Summary video extraction is in progress for ID: {meta_data_idx}, skipping processing...")
                    return {"status": "IN_PROGRESS", "type": "summaries", "message": "Already in progress"}
                else:
                    logging.info(f"Summary video extraction is not completed for ID: {meta_data_idx}, processing...")

                    # Update metadata to mark summary processing as in progress
                    update_video_summary_status(podcast_title, episode_title, 'IN_PROGRESS')

                    logging.info(f"Processing video summaries for ID: {meta_data_idx}")
                    
                    if summary_data.summary_chunk_timestamps:
                        logging.info(f"Processing {len(summary_data.summary_chunk_timestamps)} video summary segments for {podcast_title}/{episode_title}")
                        
                        video_summary_paths = process_video_summary(
                            podcast_title=podcast_title,
                            episode_title=episode_title,
                            s3_video_key=s3_video_key,
                            summaries_info=summary_data
                        )
                        
                        if len(video_summary_paths) == 1:
                            update_video_summary_status(podcast_title, episode_title, 'COMPLETED')
                            logging.info(f"Video summaries completed for ID: {meta_data_idx}")
                            return {"status": "COMPLETED", "type": "summaries", "message": "Successfully completed", "paths": video_summary_paths}
                        else:
                            update_video_summary_status(podcast_title, episode_title, 'FAILED')
                            logging.error(f"Number of video summaries ({len(video_summary_paths)}) does not match expected count (1)")
                            return {"status": "FAILED", "type": "summaries", "message": f"Summary count mismatch: {len(video_summary_paths)} != 1"}
                    else:
                        logging.warning(f"No summary chunk timestamps found for ID: {meta_data_idx}")
                        return {"status": "FAILED", "type": "summaries", "message": "No summary chunk timestamps found"}
            else:
                logging.warning(f"No summary data found for ID: {meta_data_idx}")
                return {"status": "FAILED", "type": "summaries", "message": "No summary data found"}
        else:
            logging.info(f"Summarization is not completed for ID: {meta_data_idx}, skipping summary video processing...")
            return {"status": "PENDING", "type": "summaries", "message": "Summarization not completed"}
                
    except Exception as e:
        logging.error(f"Error processing video summaries: {e}")
        update_video_summary_status(podcast_title, episode_title, 'FAILED')
        return {"status": "FAILED", "type": "summaries", "message": str(e)}

def get_video_chunking_status(podcast_title, episode_title):
    """Get current video chunking status from metadata table"""
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.get_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            }
        )
        if 'Item' in response:
            return response['Item'].get('video_chunking_status', 'PENDING')
        return 'PENDING'
    except Exception as e:
        logging.error(f"Error getting video chunking status: {e}")
        return 'PENDING'

def get_quotes_video_status(podcast_title, episode_title):
    """Get current quotes video status from metadata table"""
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.get_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            }
        )
        if 'Item' in response:
            return response['Item'].get('quotes_video_status', 'PENDING')
        return 'PENDING'
    except Exception as e:
        logging.error(f"Error getting quotes video status: {e}")
        return 'PENDING'

def get_summaries_video_status(podcast_title, episode_title):
    """Get current summaries video status from metadata table"""
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.get_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            }
        )
        if 'Item' in response:
            return response['Item'].get('summaries_video_status', 'PENDING')
        return 'PENDING'
    except Exception as e:
        logging.error(f"Error getting summaries video status: {e}")
        return 'PENDING'

def get_summarization_status(podcast_title, episode_title):
    """Get current summarization status from metadata table"""
    try:
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
        response = metadata_table.get_item(
            Key={
                'podcast_title': podcast_title,
                'episode_title': episode_title
            }
        )
        if 'Item' in response:
            return response['Item'].get('summarization_status', 'PENDING')
        return 'PENDING'
    except Exception as e:
        logging.error(f"Error getting summarization status: {e}")
        return 'PENDING'

def generate_video_artifacts(meta_data_idx, force_video_chunking=False, force_video_quote_extraction=False, force_video_summary_extraction=True):
    """
    Generate video chunks, quotes, and summaries for a given podcast episode.
    Now runs each process in the background concurrently.
    
    Args:
        meta_data_idx (str): The ID of the podcast episode.
        force_video_chunking (bool): Flag to force video chunking.
        force_video_quote_extraction (bool): Flag to force video quote extraction.
        force_video_summary_extraction (bool): Flag to force video summary extraction.
    Returns:
        list: List of video chunks.
        list: List of video quotes.
        list: List of video summaries.
        dict: Metadata of the podcast episode.
    """
    
    try:
        print(f"Received meta_data_idx: {meta_data_idx}")
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)  # type: ignore
        if not meta_data_idx:
            logging.warning("No ID found in the message, skipping processing...")
            return None, None, None, None
        
        response = metadata_table.query(IndexName='episodeUUID', KeyConditionExpression=Key('id').eq(meta_data_idx))
        items = response.get("Items", [])
        if not items:
            logging.warning(f"No record found for ID: {meta_data_idx}")
            return None, None, None, None
        
        # Check for chunking_status first
        if items[0].get('chunking_status', '') != 'COMPLETED':
            logging.info(f"Chunking not completed for ID: {meta_data_idx}, skipping processing...")
            return None, None, None, None
        
        podcast_title = str(items[0].get('podcast_title', ''))
        episode_title = str(items[0].get('episode_title', ''))
        num_chunks = int(items[0].get('num_chunks', 0)) #type:ignore
        s3_video_key = str(items[0].get('file_name', ''))
        video_chunking_status = items[0].get('video_chunking_status', 'PENDING')
        summarization_status = items[0].get('summarization_status', 'PENDING')
        quotes_status = items[0].get('quote_status', 'PENDING')
        num_quotes = int(items[0].get('num_quotes', 0)) #type:ignore
        quotes_video_status = items[0].get('quotes_video_status', 'PENDING')
        summaries_video_status = items[0].get('summaries_video_status', 'PENDING')

        episode_metadata = {
            'podcast_title': podcast_title,
            'episode_title': episode_title,
            'num_chunks': num_chunks,
            'summarization_status': summarization_status,
            'quotes_status': quotes_status,
            'num_quotes': num_quotes,
            'summaries_video_status': summaries_video_status,
        }
        logging.info(f"Podcast Title: {podcast_title}, Episode Title: {episode_title}, Number of Chunks: {num_chunks}, Number of Quotes: {num_quotes}, Video Chunking Status: {video_chunking_status}, Summarization Status: {summarization_status}, Quotes Video Status: {quotes_video_status}, Summaries Video Status: {summaries_video_status}")
        
        # Initialize return variables
        chunks = []
        quotes = []
        summaries = []
        
        # Retrieve data for processing
        chunks = [x for x in get_all_chunks(podcast_title, episode_title, int(num_chunks)) if x.duration_seconds > 3]
        quotes = get_all_quotes(podcast_title, episode_title)
        
        logging.info(f"Retrieved {len(chunks)} chunks and {len(quotes)} quotes for ID: {meta_data_idx}")
        
        # Run all three processes concurrently using ThreadPoolExecutor
        max_workers = int(os.getenv('MAX_CONCURRENT_PROCESSING', '3'))  # Default to 3 concurrent processes
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all three background processes
            future_to_process = {}
            
            # Submit chunks processing
            if chunks:
                future_chunks = executor.submit(
                    process_video_chunks_background,
                    podcast_title, episode_title, s3_video_key, chunks, num_chunks, meta_data_idx, force_video_chunking
                )
                future_to_process[future_chunks] = "chunks"
            
            # Submit quotes processing  
            if quotes:
                future_quotes = executor.submit(
                    process_video_quotes_background,
                    podcast_title, episode_title, s3_video_key, quotes, num_quotes, meta_data_idx, force_video_quote_extraction
                )
                future_to_process[future_quotes] = "quotes"
            
            # Submit summaries processing
            future_summaries = executor.submit(
                process_video_summaries_background,
                podcast_title, episode_title, s3_video_key, meta_data_idx, force_video_summary_extraction
            )
            future_to_process[future_summaries] = "summaries"
            
            # Collect results as they complete
            results = {}
            for future in as_completed(future_to_process):
                process_type = future_to_process[future]
                try:
                    result = future.result()
                    results[process_type] = result
                    logging.info(f"Background process '{process_type}' completed with status: {result.get('status', 'UNKNOWN')}")
                    if result.get('status') == 'FAILED':
                        logging.error(f"Background process '{process_type}' failed: {result.get('message', 'Unknown error')}")
                except Exception as exc:
                    logging.error(f"Background process '{process_type}' generated an exception: {exc}")
                    results[process_type] = {"status": "FAILED", "type": process_type, "message": str(exc)}
        
        # Log final results
        logging.info(f"All background processes completed for ID: {meta_data_idx}")
        for process_type, result in results.items():
            logging.info(f"Process '{process_type}': {result.get('status')} - {result.get('message')}")
        
        return chunks, quotes, summaries, episode_metadata
        
    except Exception as e:
        # Log the exception
        logging.error(f"Error processing video chunks, quotes, and summaries: {e}")
        raise e