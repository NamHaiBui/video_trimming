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

from models.summary_transcript_model import SummaryTranscriptModel
from utils.dynamo_att_to_types import dynamodb_attribute_to_python_type
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, get_all_quotes, get_summary_data
                        
logging = setup_custom_logger(__name__)


# Initialize the ECS client
ecs = boto3.client('ecs')
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')


ffmpeg_path = which("ffmpeg")

def generate_video_artifacts(meta_data_idx, force_video_chunking=False, force_video_quote_extraction=False, force_video_summary_extraction=False):
    """
    Generate video chunks, quotes, and summaries for a given podcast episode.
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
        
        podcast_title = dynamodb_attribute_to_python_type(items[0].get('podcast_title', ''))
        episode_title = dynamodb_attribute_to_python_type(items[0].get('episode_title', ''))
        num_chunks = dynamodb_attribute_to_python_type(items[0].get('num_chunks', 0))
        s3_video_key = dynamodb_attribute_to_python_type(items[0].get('file_name', ''))
        video_chunking_status = dynamodb_attribute_to_python_type(items[0].get('video_chunking_status', 'PENDING'))
        summarization_status = dynamodb_attribute_to_python_type(items[0].get('summarization_status', 'PENDING'))
        quotes_status = dynamodb_attribute_to_python_type(items[0].get('quote_status', 'PENDING'))
        num_quotes = dynamodb_attribute_to_python_type(items[0].get('num_quotes', 0))
        quotes_video_status = dynamodb_attribute_to_python_type(items[0].get('quotes_video_status', 'PENDING'))
        summaries_video_status = dynamodb_attribute_to_python_type(items[0].get('summaries_video_status', 'PENDING'))

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
        
        ######## Processing Chunks ########

        try:
            # Retrieve all chunks from CHUNK_TABLE
            chunks = get_all_chunks(podcast_title, episode_title, int(num_chunks))
            logging.info(f"Retrieved {len(chunks)} chunks for ID: {meta_data_idx}")

            if video_chunking_status == 'COMPLETED' and not force_video_chunking:
                logging.info(f"video chunking already completed for ID: {meta_data_idx}, skipping processing...")
            elif video_chunking_status == 'IN_PROGRESS':
                logging.info(f"video chunking in progress for ID: {meta_data_idx}, skipping processing...")
            else:
                logging.info(f"video chunking not completed for ID: {meta_data_idx}, processing...")
                # Update metadata to mark chunking as in progress
                update_video_chunking_status(podcast_title, episode_title, 'IN_PROGRESS')

                logging.info(f"Processing video chunking for ID: {meta_data_idx}")
                
                # Download and process video
                if chunks:
                    logging.info(f"Processing video {len(chunks)} chunks for {podcast_title}/{episode_title}")
                    video_chunk_paths = process_video_chunks(podcast_title = podcast_title, episode_title = episode_title, s3_video_key = s3_video_key, chunks_info= chunks)
                    if len(video_chunk_paths) != int(num_chunks):
                        update_video_chunking_status(podcast_title, episode_title, 'FAILED')
                        logging.error(f"Number of video chunks ({len(video_chunk_paths)}) does not match number of chunks ({num_chunks})")
                        # raise Exception(f"Number of video chunks ({len(video_chunk_paths)}) does not match number of chunks ({num_chunks})")
                    # Update metadata to mark chunking as completed
                    elif len(video_chunk_paths) == int(num_chunks):
                        update_video_chunking_status(podcast_title, episode_title, 'COMPLETED')
                        logging.info(f"video chunking completed for ID: {meta_data_idx}")
        except Exception as e:
            # Log the exception
            logging.error(f"Error processing video chunks: {e}")
            update_video_chunking_status(podcast_title, episode_title, 'FAILED')
            raise e

        ######## Processing Quotes ########

        try:
            # Retrieve all quotes from QUOTES_TABLE
            quotes = get_all_quotes(podcast_title, episode_title)
            logging.info(f"Retrieved {len(quotes)} quotes for ID: {meta_data_idx}")

            if quotes_video_status == 'COMPLETED' and not force_video_quote_extraction:
                logging.info(f"Quote video extraction already completed for ID: {meta_data_idx}, skipping processing...")
                logging.info(f"Lets process the summarization for ID: {meta_data_idx}")
            elif quotes_video_status == 'IN_PROGRESS':
                logging.info(f"Quote video extraction in progress for ID: {meta_data_idx}, skipping processing...")
            else:
                logging.info(f"Quote video extraction not completed for ID: {meta_data_idx}, processing...")
                # Update metadata to mark chunking as in progress
                update_quote_video_status(podcast_title, episode_title, 'IN_PROGRESS')

                logging.info(f"Processing video chunking for ID: {meta_data_idx}")
                
                # Download and process video
                if quotes:
                    logging.info(f"Processing video {len(quotes)} quotes for {podcast_title}/{episode_title}")
                    
                    video_quote_paths = process_video_quotes(podcast_title, \
                                                             episode_title, \
                                                             s3_video_key, \
                                                             snippets_info= quotes)
                    
                    if len(video_quote_paths) != int(num_quotes):
                        update_quote_video_status(podcast_title, episode_title, 'FAILED')
                        logging.error(f"Number of video quotes ({len(video_quote_paths)}) does not match number of quotes ({num_quotes})")
                    # Update metadata to mark chunking as completed
                    elif len(video_quote_paths) == int(num_quotes):
                        update_quote_video_status(podcast_title, episode_title, 'COMPLETED')
                        logging.info(f"video quotes completed for ID: {meta_data_idx}")
            
            logging.info(f"video quotes completed for ID: {meta_data_idx}")
        except Exception as e:
            # Log the exception
            logging.error(f"Error processing video quotes: {e}")
            update_quote_video_status(podcast_title, episode_title, 'FAILED')
            raise e

        ######## Processing Summaries ########
        
        try:
            if summarization_status == 'COMPLETED':
                # Get summary data and create SummaryTranscriptModel
                summary_data = get_summary_data(podcast_title, episode_title)
                if summary_data:
                    # Create summary transcript model from chunk data
                    chunk_models = get_all_chunks(podcast_title, episode_title, int(num_chunks))
                    summary_transcript = SummaryTranscriptModel.from_multiple_chunks(
                        chunk_models=chunk_models,
                        podcast_title=podcast_title,
                        episode_title=episode_title,
                        summary_text=summary_data.summary_text,
                        merge_threshold=1.0
                    )
                    
                    logging.info(f"Created summary transcript with {summary_transcript.total_chunks} merged chunks for ID: {meta_data_idx}")

                    if summaries_video_status == 'COMPLETED' and not force_video_summary_extraction:
                        logging.info(f"Summary video extraction already completed for ID: {meta_data_idx}, skipping processing...")
                    elif summaries_video_status == 'IN_PROGRESS':
                        logging.info(f"Summary video extraction in progress for ID: {meta_data_idx}, skipping processing...")
                    else:
                        logging.info(f"Summary video extraction not completed for ID: {meta_data_idx}, processing...")

                        # Update metadata to mark summary processing as in progress
                        update_video_summary_status(podcast_title, episode_title, 'IN_PROGRESS')

                        logging.info(f"Processing video summaries for ID: {meta_data_idx}")
                        
                        if summary_transcript.summary_chunk_timestamps:
                            logging.info(f"Processing {len(summary_transcript.summary_chunk_timestamps)} video summary segments for {podcast_title}/{episode_title}")
                            
                            video_summary_paths = process_video_summary(
                                podcast_title=podcast_title,
                                episode_title=episode_title,
                                s3_video_key=s3_video_key,
                                summaries_info=summary_transcript
                            )
                            
                            if len(video_summary_paths) == len(summary_transcript.summary_chunk_timestamps):
                                update_video_summary_status(podcast_title, episode_title, 'COMPLETED')
                                logging.info(f"Video summaries completed for ID: {meta_data_idx}")
                                summaries = summary_transcript.summary_chunk_timestamps
                            else:
                                update_video_summary_status(podcast_title, episode_title, 'FAILED')
                                logging.error(f"Number of video summaries ({len(video_summary_paths)}) does not match number of summary segments ({len(summary_transcript.summary_chunk_timestamps)})")
                        else:
                            logging.warning(f"No summary chunk timestamps found for ID: {meta_data_idx}")
                else:
                    logging.warning(f"No summary data found for ID: {meta_data_idx}")
            else:
                logging.info(f"Summarization not completed for ID: {meta_data_idx}, skipping summary video processing...")
                
        except Exception as e:
            logging.error(f"Error processing video summaries: {e}")
            update_video_summary_status(podcast_title, episode_title, 'FAILED')
            raise e

        return chunks, quotes, summaries, episode_metadata
    except Exception as e:
        # Log the exception
        logging.error(f"Error processing video chunks, quotes, and summaries: {e}")
        raise e