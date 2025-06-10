import os
import boto3
import tempfile
from pydub import AudioSegment
from boto3.dynamodb.conditions import Key
from pydub.utils import which
from typing import List, Optional

from utils.config import CHUNK_TABLE, PODCAST_METADATA_TABLE, QUOTES_TABLE
from utils.dynamo_att_to_types import dynamodb_attribute_to_python_type
from utils.logging_config import setup_custom_logger
from models.summary_transcript_model import SummaryTranscriptModel
from models.chunk_model import Chunk
from models.quote_model import Quote
logging = setup_custom_logger(__name__)


AudioSegment.converter = which("ffmpeg")
# AudioSegment.ffprobe = which("ffprobe")   



def process_audio_chunks(final_summary_chunks, AUDIO_CHUNK_BUCKET, SUMMARY_BUCKET):
    """
    Process and combine audio chunks for a podcast episode.
    """
    s3 = boto3.client('s3')  # type: ignore
    
    # os.makedirs('/tmp/audio_chunks', exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:  
        audio_chunks_path = os.path.join(temp_dir, "audio_chunks")  
        os.makedirs(audio_chunks_path, exist_ok=True)
        audio_segments = []
        summary_metadata = {
            "topic_metadata": {
                "topics": [],
                "start": [],
                "end": [],
                "chunk_nos": [],
            },
            "summary_duration": 0.0,
        }

        # Sort chunks to ensure chronological order
        sorted_chunks = sorted(
            final_summary_chunks, 
            key=lambda x: int(x["episode_title#chunk_no"].split("#")[1])
        )

        # Extract episode_title from first chunk to ensure it's available
        episode_title = sorted_chunks[0]["episode_title#chunk_no"].split("#")[0] if sorted_chunks else "unknown"
        podcast_title = sorted_chunks[0]["podcast_title"] if sorted_chunks else "unknown"
        logging.info(f"Processing {len(sorted_chunks)} audio chunks")
        # Download and process each audio chunk
        for chunk in sorted_chunks:
            podcast_title = chunk["podcast_title"]
            episode_title = chunk["episode_title#chunk_no"].split("#")[0]
            chunk_no = chunk["episode_title#chunk_no"].split("#")[1]
            episode_title_chunk_no = chunk["episode_title#chunk_no"]
            logging.info(f"Processing chunk {episode_title_chunk_no}")
            
            # Construct S3 key for the audio chunk
            s3_key = os.path.join(podcast_title, episode_title, episode_title_chunk_no + ".mp3")
            
            # Local path to save the downloaded chunk
            local_chunk_path = os.path.join(audio_chunks_path, f"{episode_title_chunk_no}.mp3")
            logging.info(f"Downloading chunk {s3_key} to {local_chunk_path}")
            try:
                # Download audio chunk from S3
                s3.download_file(AUDIO_CHUNK_BUCKET, s3_key, local_chunk_path)
                
                # Load audio segment
                audio_segment = AudioSegment.from_mp3(local_chunk_path)
                audio_segments.append({
                    "chunk_no": chunk_no,
                    "segment": audio_segment,
                    "topic": chunk["metadata"]["topic_label"],
                    "start": float(chunk["time_stamps"]["start"]),
                    "end": float(chunk["time_stamps"]["end"])
                })
            
            except Exception as e:
                print(f"Error processing chunk {s3_key}: {e}")
                continue
        logging.info(f"Processed {len(audio_segments)} audio chunks")
        
        if not audio_segments:
            logging.error("No audio segments to merge.")
            return None
        final_audio = AudioSegment.empty()
        # This tracks the "summary" timeline as we stitch chunks
        summary_offset = 0.0

        for i, item in enumerate(audio_segments):
            seg = item["segment"]
            duration = seg.duration_seconds  # length of this chunk in seconds

            if i > 0:
                gap_segment = AudioSegment.silent(duration=500) 
                final_audio += gap_segment
                summary_offset += 0.5

            final_audio += seg

            summary_start = summary_offset
            summary_end = summary_offset + duration

            summary_offset = summary_end

            # Fill in summary metadata
            summary_metadata["topic_metadata"]["topics"].append(item["topic"])
            summary_metadata["topic_metadata"]["chunk_nos"].append(item["chunk_no"])
            summary_metadata["topic_metadata"]["start"].append(str(round(summary_start, 2)))
            summary_metadata["topic_metadata"]["end"].append(str(round(summary_end, 2)))

        # We can compute total summary duration
        summary_metadata["summary_duration"] = str(round(summary_offset, 2))

        logging.info(f"Final summary duration: {summary_metadata['summary_duration']} seconds")

        merged_audio_filename = f"summary_{episode_title}.mp3"
        merged_audio_path = os.path.join(temp_dir, merged_audio_filename)
        final_audio.export(merged_audio_path, format="mp3")

        merged_audio_key = os.path.join(podcast_title, merged_audio_filename)
        logging.info(f"Uploading merged audio to {SUMMARY_BUCKET} => {merged_audio_key}")
        try:
            s3.upload_file(merged_audio_path, SUMMARY_BUCKET, merged_audio_key, ExtraArgs={"ContentType": "audio/mpeg", "ACL": "public-read"})
            logging.info(f"Successfully uploaded merged audio to {SUMMARY_BUCKET}")
            return merged_audio_path, summary_metadata
        except Exception as e:
            logging.error(f"Error uploading merged audio: {e}")
            return None

def get_all_chunks(podcast_title: str, episode_title: str, num_chunks: int) -> List[Chunk]:
    """
    Retrieve all chunks for a specific podcast episode from DynamoDB.
    Returns list of ChunkModel objects.
    """
    # Initialize DynamoDB resource
    dynamodb = boto3.resource('dynamodb')
    chunk_table = dynamodb.Table(CHUNK_TABLE) # type: ignore

    try:
        logging.info(f"Retrieving chunks for {podcast_title} - {episode_title}")
        # Query the table using the partition key and a begins_with condition on the sort key
        response = chunk_table.query(
            KeyConditionExpression=
                Key('podcast_title').eq(podcast_title) & 
                Key('episode_title#chunk_no').begins_with(episode_title)
        )
        logging.info(f"Retrieved {len(response['Items'])} raw chunks from DynamoDB")        
        
        # Convert raw DynamoDB items to ChunkModel objects
        chunks = []
        for item in response['Items']:
            try:
                # Convert DynamoDB types to Python types
                converted_item = {}
                for key, value in item.items():
                    converted_item[key] = dynamodb_attribute_to_python_type(value)
                
                # Create ChunkModel from converted data
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

def get_summary_data(podcast_title, episode_title) -> SummaryTranscriptModel | None:
    """
    Retrieve summary data for a specific podcast episode from Summary Transcript Bucket.
    """
    # Initialize S3 resource
    s3 = boto3.client('s3')  # type: ignore
    summary_transcript_bucket = os.environ.get("SUMMARY_TRANSCRIPT_BUCKET", "pd-summary-transcript-storage")
    
    try:
        logging.info(f"Retrieving summary data for {podcast_title} - {episode_title}")
        # Construct the S3 key for the summary transcript
        s3_key = f"{podcast_title}/{episode_title}/summary_transcript.json" 
        logging.info(f"Checking S3 for key: {s3_key}")
        # Check if the object exists in S3
        try:
            s3.head_object(Bucket=summary_transcript_bucket, Key=s3_key)
            logging.info(f"Summary transcript found for {podcast_title} - {episode_title}")
            # Download the summary transcript
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                temp_file_path = temp_file.name
                s3.download_file(summary_transcript_bucket, s3_key, temp_file_path)
                logging.info(f"Downloaded summary transcript to {temp_file_path}")
                # Read the summary transcript
                with open(temp_file_path, 'r') as f:
                    summary_data = f.read()
                    # Parsing the JSON data into a SummaryTranscriptModel object
                    try:
                        summary_data = SummaryTranscriptModel.load_from_json(summary_data)
                        logging.info(f"Successfully parsed summary data for {podcast_title} - {episode_title}")
                    except Exception as e:
                        logging.error(f"Error parsing summary data: {e}")
                        return None
                return summary_data
        except s3.exceptions.ClientError as e:  
            if e.response.get('Error', {}).get('Code') == '404':
                logging.error(f"Summary transcript not found for {podcast_title} - {episode_title}")
                return None
            else:
                logging.error(f"Error checking S3 for summary transcript: {e}")
                return None
    except Exception as e:
        logging.error(f"Error retrieving summary data: {e}")
        return None


    
def get_all_quotes(podcast_title: str, episode_title: str) -> List[Quote]:
    """
    Retrieve all quotes for a specific podcast episode from DynamoDB.
    Returns list of Quote objects.
    """
    # Initialize DynamoDB resource
    dynamodb = boto3.resource('dynamodb')
    quotes_table = dynamodb.Table(QUOTES_TABLE) # type: ignore

    try:
        logging.info(f"Retrieving quotes for {podcast_title} - {episode_title}")
        # Query the table using the partition key and a begins_with condition on the sort key
        response = quotes_table.query(
            KeyConditionExpression=
                Key('podcast_title').eq(podcast_title) & 
                Key('episode_title#quote_rank').begins_with(episode_title)
        )
        logging.info(f"Retrieved {len(response['Items'])} raw quotes from DynamoDB")        
        
        # Convert raw DynamoDB items to Quote objects
        quotes = []
        for item in response['Items']:
            try:
                # Convert DynamoDB types to Python types
                converted_item = {}
                for key, value in item.items():
                    converted_item[key] = dynamodb_attribute_to_python_type(value)
                
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

