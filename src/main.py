import boto3
import json
import os
import sys
import time


from tools.components.video.video_summary_cutting_script import process_video_summary
from tools.generate_video_artifacts import generate_video_artifacts
from utils.config import QUEUE_URL
from utils.logging_config import setup_custom_logger
from utils.db_operations import get_all_chunks, process_audio_chunks

# Set up logging
logging = setup_custom_logger(__name__)

# LocalStack configuration for testing
USE_LOCALSTACK = os.getenv('USE_LOCALSTACK', 'false').lower() == 'true'

if USE_LOCALSTACK:
    # Initialize SQS client for LocalStack
    sqs = boto3.client(
        'sqs',
        endpoint_url='http://localhost:4566',
        region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )
    logging.info("Using LocalStack SQS endpoint")
else:
    # Initialize SQS client for AWS
    sqs = boto3.client('sqs', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    logging.info("Using AWS SQS endpoint")

# # SQS Queue URL - set this as an environment variable
# QUEUE_URL = os.getenv('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/MyQueue')
# CHUNK_TABLE = os.environ.get("CHUNK_TABLE", "TrancriptChunkStore")
# AUDIO_CHUNK_BUCKET = os.environ.get("AUDIO_CHUNK_BUCKET", "pd-audio-chunks-storage")
# SUMMARY_BUCKET = os.environ.get("SUMMARY_BUCKET", "pd-audio-summary-storage")

def process_sqs_message(message_body):
    """
    Process a single SQS message by extracting the metadata ID and generating video artifacts.
    
    Args:
        message_body (str): JSON string containing the message data
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    try:
        logging.debug(f"Raw message body: {message_body}")
        
        # Parse the message body
        message_data = json.loads(message_body)
        logging.debug(f"Parsed message data: {message_data}")
        
        # Extract metadata ID (adjust key name based on your message structure)
        meta_data_idx = message_data.get('id') or message_data.get('meta_data_idx') or message_data.get('episode_id')
        
        if not meta_data_idx:
            logging.error(f"No metadata ID found in message: {message_body}")
            logging.debug(f"Available keys in message: {list(message_data.keys())}")
            return False
        
        logging.info(f"Processing video artifacts for ID: {meta_data_idx}")
        
        # Process video artifacts
        chunks, quotes, summaries, metadata = generate_video_artifacts(
            meta_data_idx=meta_data_idx,
            force_video_chunking=False,
            force_video_quote_extraction=False,
            force_video_summary_extraction=False
        )
        
        logging.debug(f"Processing results - chunks: {len(chunks) if chunks else 0}, quotes: {len(quotes) if quotes else 0}, summaries: {len(summaries) if summaries else 0}")
        
        if metadata:
            logging.info(f"Successfully processed video artifacts for {metadata.get('podcast_title', 'Unknown')}/{metadata.get('episode_title', 'Unknown')}")
            return True
        else:
            logging.warning(f"No metadata returned for ID: {meta_data_idx}")
            return False
            
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in message body: {message_body}")
        logging.error(f"JSON decode error: {e}")
        return False
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        logging.exception("Full traceback:")
        return False

def create_queue_if_not_exists():
    """Create SQS queue if it doesn't exist (useful for LocalStack testing)"""
    if USE_LOCALSTACK and QUEUE_URL:
        try:
            queue_name = QUEUE_URL.split('/')[-1]
            response = sqs.create_queue(QueueName=queue_name)
            logging.info(f"Created or confirmed queue: {queue_name}")
            return response['QueueUrl']
        except Exception as e:
            logging.warning(f"Could not create queue: {e}")
    return QUEUE_URL

def poll_and_process_sqs_messages():
    """
    Main loop to poll SQS messages and process them.
    """
    if not QUEUE_URL:
        logging.error("SQS_QUEUE_URL environment variable not set")
        return
    
    # Create queue if using LocalStack
    queue_url = create_queue_if_not_exists()
    
    logging.info(f"Starting SQS message processing with queue: {queue_url}")
    
    while True:
        try:
            logging.debug("Polling for SQS messages...")
            
            # Poll for messages from SQS
            response = sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20  # Long polling
            )
            
            logging.debug(f"SQS response: {response}")
            
            messages = response.get('Messages', [])
            
            if not messages:
                logging.info("No messages in SQS queue. Waiting for new messages...")
                time.sleep(30)  # Wait 30 seconds before polling again
                continue
            
            logging.debug(f"Received {len(messages)} messages")
            
            for message in messages:
                message_body = message.get('Body')
                receipt_handle = message.get('ReceiptHandle')
                message_id = message.get('MessageId', 'Unknown')
                
                logging.debug(f"Message details - ID: {message_id}, Body: {message_body[:200] if message_body else 'None'}...")
                
                if not message_body:
                    logging.error(f"No Body found in message {message_id}, skipping...")
                    continue
                
                if not receipt_handle:
                    logging.error(f"No ReceiptHandle found in message {message_id}, skipping...")
                    continue
                
                logging.info(f"Received message: {message_id}")
                
                # Process the message
                success = process_sqs_message(message_body)
                
                if success:
                    # Delete the message from the queue after successful processing
                    try:
                        sqs.delete_message(
                            QueueUrl=QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        logging.info(f"Successfully processed and deleted message: {message_id}")
                    except Exception as delete_error:
                        logging.error(f"Failed to delete message {message_id}: {delete_error}")
                else:
                    logging.error(f"Failed to process message: {message_id}")
                logging.debug("Polling for next message...")
                
        except KeyboardInterrupt:
            logging.info("Received interrupt signal. Shutting down gracefully...")
            break
        except Exception as e:
            logging.error(f"Error polling SQS: {e}")
            logging.exception("Full traceback:")
            time.sleep(10) 

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
        force_summarization = event.get("force_video_summarization", False)
        force_audio_chunking = event.get("force_video_chunking", False)
        force_audio_quote_extraction = event.get("force_video_quote_extraction", False)

    except KeyError as e:
        print(f"Missing key in event data: {e}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
    
    try:
        # generate audio chunks
        logging.info(f"Generating audio video for ID: {meta_data_idx}")
        chunks_result, quotes_result, summary_result, episode_metadata = generate_video_artifacts(meta_data_idx, force_audio_chunking, force_audio_quote_extraction, force_summarization)       

    except Exception as e:
        print(f"Error generating video chunks: {e}")
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
    # if not summary_result:
    #     logging.error("No summary result found for the episode.")
    #     return {
    #         'statusCode': 500,
    #         'body': f"Error: No summary result found for the episode."
    #     }
    logging.info("Task complete.")

if __name__ == "__main__":
    poll_and_process_sqs_messages()
