import ffmpeg
import os

def merge_audio_video(video_file, audio_file, output_file):
    """
    Merges a soundless video file with an audio file.

    Args:
        video_file (str): The path to the input video file (soundless).
        audio_file (str): The path to the input audio file.
        output_file (str): The path to the output video file.
    """
    # Check if input files exist
    if not os.path.exists(video_file):
        raise FileNotFoundError(f"Video file not found: {video_file}")
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    try:
        # Simple merge for soundless video + audio
        (
            ffmpeg
            .output(
                ffmpeg.input(video_file),
                ffmpeg.input(audio_file),
                output_file,
                vcodec='copy',  
                acodec='copy',  
                shortest=None   
            )
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
        print(f"Successfully merged '{video_file}' and '{audio_file}' into '{output_file}'")

    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode('utf8') if e.stderr else 'No stderr output'
        stdout_output = e.stdout.decode('utf8') if e.stdout else 'No stdout output'
        print(f"Error merging {video_file} and {audio_file}:")
        print("STDERR:", stderr_output)
        print("STDOUT:", stdout_output)
        raise