import boto3
import json
import time
import os

from boto3.dynamodb.conditions import Key
from pydub.utils import which
from utils.config import PODCAST_METADATA_TABLE

from tools.components.video.video_chunk_cutting_script import process_video_chunks, update_video_chunking_status
from tools.components.video.video_quote_cutting_script import process_video_quotes, update_quote_video_status
from tools.components.video.video_summary_cutting_script import process_video_summary, update_video_summary_status
from utils.dynamo_att_to_types import dynamodb_attribute_to_python_type
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, get_all_quotes, get_summary_data
from utils.aws_clients import get_dynamodb_resource, get_s3_client
                        
logging = setup_custom_logger(__name__)

dynamodb = get_dynamodb_resource()
s3_client = get_s3_client()
ffmpeg_path = which("ffmpeg")

def generate_video_artifacts(meta_data_idx, force_video_chunking=False, force_video_quote_extraction=False, force_video_summary_extraction=False):
    """
    Generate video chunks, quotes, and summaries for a given podcast episode.
    Now runs each process sequentially - much simpler and safer.
    """
    
    try:
        print(f"Received meta_data_idx: {meta_data_idx}")
        metadata_table = dynamodb.Table(PODCAST_METADATA_TABLE)
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
        num_chunks = int(dynamodb_attribute_to_python_type(items[0].get('num_chunks', 0)))
        s3_video_key = str(items[0].get('video_url', ''))
        num_quotes = int(dynamodb_attribute_to_python_type(items[0].get('num_quotes', 0)))

        logging.info(f"Processing {podcast_title}/{episode_title} - {num_chunks} chunks, {num_quotes} quotes")
        
        # Initialize return variables
        chunks = []
        quotes = []
        summaries = []
        
        # Retrieve data for processing
        chunks = [x for x in get_all_chunks(podcast_title, episode_title, int(num_chunks)) if x.duration_seconds > 3]
        quotes = get_all_quotes(podcast_title, episode_title)
        
        logging.info(f"Retrieved {len(chunks)} chunks and {len(quotes)} quotes for ID: {meta_data_idx}")
        
        # Process 1: Video Chunks (Sequential)
        if chunks:
            logging.info(f"Starting video chunk processing...")
            video_chunking_status = get_video_chunking_status(podcast_title, episode_title)
            
            if video_chunking_status == 'COMPLETED' and not force_video_chunking:
                logging.info(f"Video chunking already completed, skipping...")
            else:
                update_video_chunking_status(podcast_title, episode_title, 'IN_PROGRESS')
                try:
                    video_chunk_paths = process_video_chunks(
                        podcast_title=podcast_title, 
                        episode_title=episode_title, 
                        s3_video_key=s3_video_key, 
                        chunks_info=chunks
                    )
                    
                    if len(video_chunk_paths) == int(num_chunks):
                        update_video_chunking_status(podcast_title, episode_title, 'COMPLETED')
                        logging.info(f"Video chunking completed: {len(video_chunk_paths)} chunks")
                    else:
                        update_video_chunking_status(podcast_title, episode_title, 'REQUEST_REVIEW')
                        logging.warning(f"Chunk count mismatch: {len(video_chunk_paths)} != {num_chunks}")
                        
                except Exception as e:
                    logging.error(f"Video chunk processing failed: {e}")
                    update_video_chunking_status(podcast_title, episode_title, 'FAILED')
        
        # Process 2: Video Quotes (Sequential)
        if quotes:
            logging.info(f"Starting video quote processing...")
            quotes_video_status = get_quotes_video_status(podcast_title, episode_title)
            
            if quotes_video_status == 'COMPLETED' and not force_video_quote_extraction:
                logging.info(f"Video quote extraction already completed, skipping...")
            else:
                update_quote_video_status(podcast_title, episode_title, 'IN_PROGRESS')
                try:
                    video_quote_paths = process_video_quotes(
                        podcast_title,
                        episode_title,
                        s3_video_key,
                        snippets_info=quotes
                    )
                    
                    if len(video_quote_paths) > 0:
                        update_quote_video_status(podcast_title, episode_title, 'COMPLETED')
                        logging.info(f"Video quote processing completed: {len(video_quote_paths)} quotes")
                        if len(video_quote_paths) != num_quotes:
                            logging.warning(f"Quote count mismatch: {len(video_quote_paths)} != {num_quotes}")
                    else:
                        update_quote_video_status(podcast_title, episode_title, 'FAILED')
                        logging.error(f"No quotes processed successfully")
                        
                except Exception as e:
                    logging.error(f"Video quote processing failed: {e}")
                    update_quote_video_status(podcast_title, episode_title, 'FAILED')
        
        # Process 3: Video Summaries (Sequential)
        # logging.info(f"Starting video summary processing...")
        # summarization_status = get_summarization_status(podcast_title, episode_title)
        # summaries_video_status = get_summaries_video_status(podcast_title, episode_title)
        
        # if summarization_status == 'COMPLETED':
        #     if summaries_video_status == 'COMPLETED' and not force_video_summary_extraction:
        #         logging.info(f"Video summary extraction already completed, skipping...")
        #     else:
        #         update_video_summary_status(podcast_title, episode_title, 'IN_PROGRESS')
        #         try:
        #             summary_data = get_summary_data(podcast_title, episode_title)
        #             if summary_data and summary_data.summary_chunk_timestamps:
        #                 video_summary_paths = process_video_summary(
        #                     podcast_title=podcast_title,
        #                     episode_title=episode_title,
        #                     s3_video_key=s3_video_key,
        #                     summaries_info=summary_data
        #                 )
                        
        #                 if len(video_summary_paths) == 1:
        #                     update_video_summary_status(podcast_title, episode_title, 'COMPLETED')
        #                     logging.info(f"Video summary processing completed")
        #                 else:
        #                     update_video_summary_status(podcast_title, episode_title, 'FAILED')
        #                     logging.error(f"Summary count mismatch: {len(video_summary_paths)} != 1")
        #             else:
        #                 update_video_summary_status(podcast_title, episode_title, 'FAILED')
        #                 logging.error(f"No summary data found")
                        
        #         except Exception as e:
        #             logging.error(f"Video summary processing failed: {e}")
        #             update_video_summary_status(podcast_title, episode_title, 'FAILED')
        # else:
        #     logging.info(f"Summarization not completed, skipping video summary processing")
        
        episode_metadata = {
            'podcast_title': podcast_title,
            'episode_title': episode_title,
            'num_chunks': num_chunks,
            'num_quotes': num_quotes,
        }
        
        logging.info(f"All sequential processing completed for ID: {meta_data_idx}")
        return chunks, quotes, summaries, episode_metadata
        
    except Exception as e:
        logging.error(f"Error processing video artifacts: {e}")
        raise e

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