from typing import List, Tuple
import ffmpeg
import sys
import os.path

def extract_audio_snippets(input_file:str, snippets_info:List[Tuple[str,float,float]], overwrite=True):
    """
    Cuts multiple audio snippets from a single input file in one ffmpeg process.

    Args:
        input_file (str): Path to the input audio file.
        snippets_info (list): A list of tuples, where each tuple contains:
                              (output_file_path, start_time, end_time)
                              e.g., [("snippet1.mp3", 10, 20),
                                     ("snippet2.mp3", 30, 35)]
        overwrite (bool): Whether to overwrite output files if they exist.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    if not snippets_info:
        print("No snippets defined to process.")
        return

    print(f"Processing multiple snippets from: {input_file}")

    try:
        in_stream = ffmpeg.input(input_file)
        output_streams = []

        for i, (output_file, start_time, end_time) in enumerate(snippets_info):
            print(f"  Defining snippet: {output_file} (Start: {start_time}, End: {end_time})")
            

            processed_segment = (
                in_stream['a']
                .filter('atrim', start=start_time, end=end_time)
                .filter('asetpts', 'PTS-STARTPTS')
            )
            output_streams.append(
                processed_segment.output(output_file, acodec='aac')
            )

        command_args = ffmpeg.get_args(tuple(output_streams), overwrite_output=overwrite)
        print("\nGenerated ffmpeg command:")
        print("ffmpeg " + " ".join(command_args) + "\n")
        
        process = ffmpeg.run(tuple(output_streams), capture_stdout=True, capture_stderr=True, overwrite_output=overwrite)
        
        print("All snippets processed successfully.")
    except ffmpeg.Error as e:
        print(f"Error during ffmpeg-python processing:")
        print("ffmpeg stdout:", e.stdout.decode('utf8') if e.stdout else 'N/A')
        print("ffmpeg stderr:", e.stderr.decode('utf8') if e.stderr else 'N/A')
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)