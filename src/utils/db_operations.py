import os
import boto3
import tempfile
import json
# from pydub import AudioSegment
from boto3.dynamodb.conditions import Key
# from pydub.utils import which
from typing import List
from utils.dynamo_att_to_types import (
    flatten_timestamps, flatten_word_timestamps, flatten_list_field
)
from utils.config import CHUNK_TABLE, QUOTES_TABLE, SUMMARY_TRANSCRIPT_BUCKET
from utils.logging_config import setup_custom_logger
from models.summary_transcript_model import SummaryTranscriptModel
from models.chunk_model import Chunk
from models.quote_model import Quote
from utils.aws_clients import get_s3_client, get_dynamodb_resource
logging = setup_custom_logger(__name__)

try:
    AWS_CLIENTS_AVAILABLE = True
except ImportError:
    AWS_CLIENTS_AVAILABLE = False
    get_s3_client = None
    get_dynamodb_resource = None

def get_summary_data(podcast_title, episode_title) -> SummaryTranscriptModel | None:
    """
    Retrieve summary data for a specific podcast episode from Summary Transcript Bucket.
    """
    # Initialize S3 resource
    if AWS_CLIENTS_AVAILABLE and get_s3_client is not None:
        s3 = get_s3_client()
    else:
        s3 = boto3.client('s3')  # type: ignore
    try:
        logging.info(f"Retrieving summary data for {podcast_title} - {episode_title}")
        # Construct the S3 key for the summary transcript
        s3_key = os.path.join(podcast_title, f"summary_transcript-${episode_title}.json" )
        logging.info(f"Checking S3 for key: {s3_key}")
        # Check if the object exists in S3
        try:
            s3.head_object(Bucket=SUMMARY_TRANSCRIPT_BUCKET, Key=s3_key)
            logging.info(f"Summary transcript found for {podcast_title} - {episode_title}")
            # Download the summary transcript
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                temp_file_path = temp_file.name
                s3.download_file(SUMMARY_TRANSCRIPT_BUCKET, s3_key, temp_file_path)
                logging.info(f"Downloaded summary transcript to {temp_file_path}")
                # Read the summary transcript
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    summary_trancscript = f.read()
                    try:
                        logging.info(f"Parsing summary data for {podcast_title} - {episode_title}")
                        summary_trancscript = SummaryTranscriptModel.load_from_json(summary_trancscript)
                    except Exception as e:
                        logging.error(f"Error parsing summary data: ")
                        return None
                return summary_trancscript
        except s3.exceptions.ClientError as e:  
            if e.response.get('Error', {}).get('Code') == '404':
                logging.error(f"Summary transcript not found for {podcast_title} - {episode_title}")
                return None
            else:
                logging.error(f"Error checking S3 for summary transcript: ")
                return None
    except Exception as e:
        logging.error(f"Error retrieving summary data: ")
        return None
def get_all_chunks(podcast_title: str, episode_title: str, num_chunks: int) -> List[Chunk]:
    """
    Retrieve all chunks for a specific podcast episode from DynamoDB.
    Returns list of ChunkModel objects.
    """
    # Initialize DynamoDB resource
    if AWS_CLIENTS_AVAILABLE and get_dynamodb_resource is not None:
        dynamodb = get_dynamodb_resource()
    else:
        dynamodb = boto3.resource('dynamodb')
    chunk_table = dynamodb.Table(CHUNK_TABLE) # type: ignore

    try:
        logging.info(f"Retrieving chunks for {podcast_title} - {episode_title}")
        # Query the table using the partition key and a begins_with condition on the sort key
        last_evaluated_key = None
        items = []
        while True:
            if last_evaluated_key:
                response = chunk_table.query(
                    KeyConditionExpression=
                        Key('podcast_title').eq(podcast_title) & 
                        Key('episode_title#chunk_no').begins_with(episode_title),
                    ExclusiveStartKey=last_evaluated_key,
                    ConsistentRead=True
                )
            else:
                response = chunk_table.query(
                    KeyConditionExpression=
                        Key('podcast_title').eq(podcast_title) & 
                        Key('episode_title#chunk_no').begins_with(episode_title),
                    ConsistentRead=True
                )

            items.extend(response['Items'])

            if 'LastEvaluatedKey' not in response:
                break
            last_evaluated_key = response['LastEvaluatedKey']

        logging.info(f"Retrieved {len(items)} raw chunks from DynamoDB")        
        
        # Convert raw DynamoDB items to ChunkModel objects
        chunks = []
        for item in items:
            logging.debug(f"Processing chunk item: {item}")
            try:
                # Import the DynamoDB converter

                # Convert DynamoDB types to Python types with special handling for nested structures
                converted_item = {}
                for key, value in item.items():
                    if key == 'time_stamps' and isinstance(value, dict):
                        converted_item[key] = flatten_timestamps(value)
                    elif key == 'word_timestamps' and isinstance(value, list):
                        # Special handling for word timestamps
                        converted_item[key] = flatten_word_timestamps(value)
                    elif key in ['sentiment', 'speakers', 'topics'] and isinstance(value, list):
                        converted_item[key] = flatten_list_field(value)
                    else:
                        converted_item[key] = value
                chunk_model = Chunk.from_csv_row(converted_item)
                chunks.append(chunk_model)
            except Exception as e:
                logging.error(f"Error converting chunk to ChunkModel: {e}")
                continue
        
        # Sort chunks based on chunk number
        chunks = sorted(chunks, key=lambda x: int(x.chunk_number))
        
        # Validate the number of chunks
        if len(chunks) != num_chunks:
            logging.warning(f"Expected {num_chunks} chunks, but converted {len(chunks)} chunks")
        
        logging.info(f"Successfully converted {len(chunks)} chunks to ChunkModel objects")
        return chunks
    
    except Exception as e:
        logging.error(f"Error retrieving chunks: {e}")
        return []
    
def get_all_quotes(podcast_title: str, episode_title: str) -> List[Quote]:
    """
    Retrieve all quotes for a specific podcast episode from DynamoDB.
    Returns list of Quote objects.
    """
    # Initialize DynamoDB resource
    if AWS_CLIENTS_AVAILABLE and get_dynamodb_resource is not None:
        dynamodb = get_dynamodb_resource()
    else:
        dynamodb = boto3.resource('dynamodb')
    quotes_table = dynamodb.Table(QUOTES_TABLE) # type: ignore

    try:
        logging.info(f"Retrieving quotes for {podcast_title} - {episode_title}")
        last_evaluated_key = None
        items = []
        while True:
            if last_evaluated_key:
                response = quotes_table.query(
                    KeyConditionExpression=
                        Key('podcast_title').eq(podcast_title) & 
                        Key('episode_title#quote_rank').begins_with(episode_title),
                    ExclusiveStartKey=last_evaluated_key,
                    ConsistentRead=True
                )
            else:
                response = quotes_table.query(
                    KeyConditionExpression=
                        Key('podcast_title').eq(podcast_title) & 
                        Key('episode_title#quote_rank').begins_with(episode_title)
                )
            items.extend(response['Items'])
            if 'LastEvaluatedKey' not in response:
                break
            last_evaluated_key = response['LastEvaluatedKey']
        logging.info(f"Retrieved {len(items)} raw quotes from DynamoDB")        
        
        # Convert raw DynamoDB items to Quote objects
        quotes = []
        for item in items:
            try:
                from utils.dynamo_att_to_types import (
                    flatten_timestamps, flatten_word_timestamps, flatten_list_field
                )
                converted_item = {}
                for key, value in item.items():
                    if key in ['context_timestamps', 'quote_timestamps'] and isinstance(value, dict):
                        converted_item[key] = flatten_timestamps(value)
                    elif key in ['absolute_context_word_timestamps', 'absolute_quote_word_timestamps', 
                                'transcript_level_context_word_timestamps', 'transcript_level_quote_word_timestamps'] and isinstance(value, str):
                        try:
                            cleaned_value = value.strip()
                            if not cleaned_value or cleaned_value in ['', '[]', '{}']:
                                converted_item[key] = []
                                continue
                            
                            parsed_value = json.loads(cleaned_value)
                            if isinstance(parsed_value, list):
                                converted_item[key] = flatten_word_timestamps(parsed_value)
                            else:
                                converted_item[key] = []
                        except (json.JSONDecodeError, TypeError, ValueError) as e:
                            logging.warning(f"Failed to parse JSON for {key}: {str(e)[:100]}... - setting to empty list")
                            converted_item[key] = []
                    elif key in ['absolute_context_word_timestamps', 'absolute_quote_word_timestamps', 
                                'transcript_level_context_word_timestamps', 'transcript_level_quote_word_timestamps'] and isinstance(value, list):
                        # Handle word timestamp arrays
                        try:
                            converted_item[key] = flatten_word_timestamps(value)
                        except Exception as e:
                            logging.warning(f"Failed to flatten word timestamps for {key}: {e} - setting to empty list")
                            converted_item[key] = []
                    elif key in ['sentiment'] and isinstance(value, list):
                        # Handle list fields
                        converted_item[key] = flatten_list_field(value)
                    else:
                        converted_item[key] = value
                
                # Create Quote from converted data
                quote = Quote(**converted_item)
                quotes.append(quote)
            except Exception as e:
                logging.error(f"Error converting quote to Quote model: {e}")
                continue
        
        # Sort quotes based on quote rank
        quotes = sorted(quotes, key=lambda x: x.quote_rank)
        
        logging.info(f"Successfully converted {len(quotes)} quotes to Quote objects")
        return quotes
    
    except Exception as e:
        logging.error(f"Error retrieving quotes: {e}")
        return []

