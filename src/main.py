import os
import json
import sys


from tools.components.video.video_summary_cutting_script import process_video_summary
from tools.generate_video_artifacts import generate_video_artifacts
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, process_audio_chunks

logging = setup_custom_logger(__name__)
# model = "r1-1776"

CHUNK_TABLE = os.environ.get("CHUNK_TABLE", "TrancriptChunkStore")
AUDIO_CHUNK_BUCKET = os.environ.get("AUDIO_CHUNK_BUCKET", "pd-audio-chunks-storage")
SUMMARY_BUCKET = os.environ.get("SUMMARY_BUCKET", "pd-audio-summary-storage")

def main():
    logging.info("Starting audio chunking and summarization process...")
    if len(sys.argv) < 2:
        logging.error("No event data received in command-line arguments.")
        return {
            'statusCode': 500,
            'body': "Error: No event data received in command-line arguments."
        }

    # The first argument after the script name is the JSON payload
    event_data = sys.argv[1]
    logging.info(f"Received event data: {event_data}")

    if not event_data:
        logging.error("No event data received.")
        return {
            'statusCode': 500,
            'body': "Error: No event data received."
        }

    # Parse the JSON message
    try:
        event = json.loads(event_data)
        meta_data_idx = event["id"]
        force_summarization = event.get("force_summarization", False)
        force_audio_chunking = event.get("force_audio_chunking", False)
        force_audio_quote_extraction = event.get("force_audio_quote_extraction", False)

    except KeyError as e:
        print(f"Missing key in event data: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
    
    try:
        # generate audio chunks
        logging.info(f"Generating audio chunks for ID: {meta_data_idx}")
        chunks_result, quotes_result, summary_result, episode_metadata = generate_video_artifacts(meta_data_idx, force_audio_chunking, force_audio_quote_extraction, force_summarization)       

    except Exception as e:
        print(f"Error generating audio chunks: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
    
    if not chunks_result:
        logging.error("No audio chunks found for the episode.")
        return {
            'statusCode': 500,
            'body': f"Error: No audio chunks found for the episode."
        }
    if not quotes_result:
        logging.error("No quotes found for the episode.")
        return {
            'statusCode': 500,
            'body': f"Error: No quotes found for the episode."
        }
    if not summary_result:
        logging.error("No summary result found for the episode.")
        return {
            'statusCode': 500,
            'body': f"Error: No summary result found for the episode."
        }
    logging.info("Task complete.")

if __name__ == "__main__":
    main()
    