import os
import json
import sys


from tools.generate_video_artifacts import generate_video_chunks_and_quotes
from utils.logging_config import setup_custom_logger
# from utils.db_operations import get_all_chunks, process_audio_chunks, update_summarization_status

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
        filtered_chunks, quotes, episode_metadata = generate_video_chunks_and_quotes(meta_data_idx, force_audio_chunking, force_audio_quote_extraction)       

    except Exception as e:
        print(f"Error generating audio chunks: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
    
    if not filtered_chunks:
        logging.error("No audio chunks found for the episode.")
        return {
            'statusCode': 500,
            'body': f"Error: No audio chunks found for the episode."
        }

    if episode_metadata['summarization_status'] == "COMPLETED" and not force_summarization:
        logging.info(f"Summarization already completed for ID: {meta_data_idx}, skipping processing...")
        return {
            'statusCode': 200,
            'body': "Audio chunks already summarized."
        }

    # try:
    #     logging.info("Processing audio chunks for the final summary")
    #     if final_summary_chunks:
    #         # Process audio chunks
    #         merged_audio_path, summary_metadata = process_audio_chunks(
    #             final_summary_chunks, 
    #             AUDIO_CHUNK_BUCKET, 
    #             SUMMARY_BUCKET
    #         )

    #         # generate timestamps for summary
    #         summary_transcript_file_name = generate_summary_timestamps(
    #             final_summary_chunks,
    #             episode_metadata['podcast_title'],
    #             episode_metadata['episode_title'],
    #         )
    #         summary_metadata["summary_transcript_file_name"] = summary_transcript_file_name

    #         if merged_audio_path:
    #             # Update status in dynamodb
    #             update_summarization_status(episode_metadata["podcast_title"], episode_metadata["episode_title"], "COMPLETED", summary_metadata)

    #         return {
    #             'statusCode': 200,
    #             'body': f"Summary audio path: {merged_audio_path}"
    #         }
    
    # except Exception as e:
    #     logging.error(f"Error processing audio chunks: {e}")
    #     return {
    #         'statusCode': 500,
    #         'body': f"Error: {str(e)}"
    #     }
    logging.info("Task complete.")

if __name__ == "__main__":
    main()
    # python main.py '{"id": "84e9ae60-481d-428a-94d0-97456c8bb59e", "force_summarization": true, "force_audio_chunking": true, "force_audio_quote_extraction": true}'