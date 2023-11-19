import os
import cv2
import random
import subprocess
from enum import Enum
from pathlib import Path
import json
from urllib.parse import urlparse
from urllib.request import urlopen

class Status(Enum):
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    NOT_STARTED = 'NOT_STARTED'
    ERROR = 'ERROR'
    UPDATED = 'UPDATED'


def is_url(url:str):
    """
    Function to check if an URL is valid or not.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def get_video_info(video_path: str):
    """
    This function takes the path (or URL) of a video and returns a dictionary with fps and duration information.

    Args:
        video_path (str): The path (or URL) of the video.

    Raises:
        ValueError: If the video doesn't have any frames, or the path/link is incorrect.

    Returns:
        dict: A dictionary containing video information such as fps, duration, frame count, size, codec, video name, and video path.
    """
    cap = cv2.VideoCapture(video_path)

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # prevent issues with missing videos
    if int(frame_count) | int(fps) == 0:
        raise ValueError(f"{video_path} doesn't have any frames, check the path/link is correct.")
    else:
        duration = frame_count / fps

    duration_mins = duration / 60

    # Check codec info
    h = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = (chr(h & 0xFF) + chr((h >> 8) & 0xFF) + chr((h >> 16) & 0xFF) + chr((h >> 24) & 0xFF))
  
    # Check if the video is accessible locally
    if os.path.exists(video_path):
        # Store the size of the video
        size = os.path.getsize(video_path)

    # Check if the path to the video is a URL
    elif is_url(video_path):
        # Store the size of the video
        size = urlopen(video_path).length

    # Calculate the size:duration ratio
    sizeGB = size / (1024 * 1024 * 1024)
    size_duration = sizeGB / duration_mins

    return {
        'fps': fps, 
        'duration': duration,
        'frame_count': frame_count,
        'duration_mins': duration_mins,
        'size': size,
        'sizeGB': sizeGB,
        'size_duration': size_duration,
        'codec': codec,
        'video_name': os.path.basename(video_path),
        'video_path': video_path 
    }


def calculate_frames(duration_in_seconds:int, start_time_in_seconds:int, fps:float, n_seconds:int) -> int:
    """ 
    Calculates the number of frames that will be extracted from a video given its duration, start time, frame rate, and the interval at which frames will be extracted.

    Args:
        duration_in_seconds (int): The duration of the video in seconds.
        start_time_in_seconds (int): The start time in seconds from which frames should be extracted.
        fps (float): The frame rate of the video (frames per second).
        n_seconds (int): The interval in seconds at which frames should be extracted from the video.

    Returns:
        int: The number of frames that will be extracted.

    Raises:
        ValueError: If the calculated number of frames is less than 10.
    """
    # Calculate the total number of frames in the video
    total_frames = duration_in_seconds * fps

    # Calculate the starting frame
    start_frame = start_time_in_seconds * fps

    # Calculate the number of frames that will be extracted
    step = n_seconds * fps
    num_frames = (total_frames - start_frame) // step

    # Check if the calculated number of frames is less than 10
    if num_frames < 10:
        raise ValueError("The calculated number of frames is less than 10. Please adjust the input parameters.")

    return num_frames


def select_random_frames(frames: dict, num_frames: int = 10) -> dict:
    """
    Selects a specified number of frames at random from a given dictionary of video frames.
    
    Args:
        frames (dict): A dictionary representing video frames. The keys are the frame numbers, 
                       and the values are the file paths where each frame is stored.
                       
        num_frames (int, optional): The number of frames to sample from the `frames` dictionary. 
                                    Defaults to 10.
                                    
    Returns:
        dict: A dictionary where each key-value pair corresponds to a randomly selected frame. 
              The keys are frame numbers, and the values are dictionaries with:
              - FILEPATH: The path to the frame's file.
              - INTERPRETATION: A dictionary that includes:
                - DOTPOINTS: Initially an empty dictionary. Expected to store IDs of points in the frame, 
                             and corresponding dictionaries with `x`, `y` coordinates and annotations.
                - STATUS: Initialized to 'NOT_STARTED'. Can be updated to any other value from the `Status` Enum 
                          (`IN_PROGRESS`, `COMPLETED`, `ERROR`, `UPDATED`).

    Raises:
        ValueError: If `num_frames` is greater than the number of available frames in `frames`.
    """
    if num_frames > len(frames):
        raise ValueError("Number of frames to select is greater than the available frames")

    selected_keys = random.sample(sorted(frames.keys()), num_frames)
    result = {
        key: {
            'FILEPATH': frames[key], 
            'INTERPRETATION': {
                'DOTPOINTS': {}, 
                'STATUS': Status.NOT_STARTED.value
            }
        } for key in sorted(selected_keys)
    }
    return result


def convert_codec(input_file, output_file, callback:callable=None)->bool:
    """
    Converts video codec from 'hvc1' to 'h264' using FFmpeg.
    This function requires FFmpeg to be installed and in PATH.

    Args:
        input_file (str): The path to the input video file.
        output_file (str): The path to the output video file.
        callback (callable, optional): A callback function to report progress. Defaults to None.
    
    Returns:
        bool: True if successful else False
    """
    # Check if FFmpeg is installed
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        message = 'FFmpeg is not installed or is not in PATH'
        print(message)
        if callback: 
            callback(message)        
        return False

    # Check if the input file exists
    if not os.path.isfile(input_file):
        message = f'Input file {input_file} does not exist'
        print(message)
        callback(message)        
        return False

    # Execute FFmpeg command
    try:
        subprocess.run(['ffmpeg', '-i', input_file, '-vcodec', 'libx264', '-acodec', 'copy', '-y', output_file], check=True)
    except subprocess.CalledProcessError as e:
        message = f'Error occurred while converting the file: {e.stderr.decode("utf-8")}'
        print(message)
        callback(message)        
        return False
    else:
        return True




def extract_frames_every_n_seconds(video_filepath: str, frames_dirpath: str, prefix: str, n_seconds: int, start_time_in_seconds: int) -> dict:
    """
    Extracts video frames every `n_seconds` from a video starting from `start_time` and saves them in `output_dir`.

    Args:
        video_filepath (str): Path to the video file.
        frames_dirpath (str): Directory where the extracted frames will be saved.
        prefix (str): Prefix to be used for the frame file names.
        n_seconds (int): The interval in seconds at which frames should be extracted from the video.
        start_time_in_seconds (int): The start time in seconds from which frame extraction should begin.

    Returns:
        dict: A dictionary where the keys are the timestamps and the values are the corresponding frame file paths.
    """
    video_path = Path(video_filepath)
    frames_dir = Path(frames_dirpath)
    frames_dict = {}
    step = n_seconds
    start_time = float(start_time_in_seconds)

    # Check if the video file exists
    if not video_path.is_file():
        raise ValueError(f"Video file not found: {video_filepath}")

    # Check if output directory exists, if not create it
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Get the total duration of the video in seconds
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(video_path)]
    output = subprocess.check_output(cmd).decode('utf-8')
    duration = float(json.loads(output)['format']['duration'])

    # Ensure that the start time is not greater than the total duration of the video
    if start_time > duration:
        raise ValueError(f"Start time {start_time} exceeds video duration {duration}")

    for i in range(int(start_time), int(duration), step):
        frame_file_path = frames_dir / f'{prefix}_{i:06d}_sec.png'
        try:
            subprocess.run(['ffmpeg', '-ss', str(i), '-i', str(video_path), '-frames:v', '1', str(frame_file_path)], check=True)
        except Exception as e:
            raise ValueError(f"Error extracting frame at {i} seconds: {e}")
        else:
            frames_dict[f"SEC_{i:06d}"] = str(frame_file_path)

    return frames_dict



def extract_frames(video_filepath: str, frames_dirpath: str, start_time_in_seconds:int = 1, n_seconds: int = 5,  callback: callable = None, kwargs: dict = None):
    """
    Extract frames from a video file and save them to a specified directory every n seconds starting from a specific time in seconds.

    Args:
        video_filepath (str): Path to the video file.
        frames_dirpath (str): Directory where the extracted frames will be saved.
        
        start_time_in_seconds (int, optional): The time in seconds from where frames should be extracted. Defaults to 1.
        n_seconds (int, optional): The interval in seconds at which frames should be extracted from the video. Defaults to 5.
        callback (callable, optional): A callable object (function) that will be called with the video_info dictionary. Defaults to None.
        **kwargs (dict): Additional arguments as key-value pairs. Defaults to None. Dictionary keys: 'survey_name', 'station_name'. 
            example of kwargs:  {survey_name (str): The name of the survey. , 
                                station_name (str): The name of the station.}

    Returns:
        dict or None: Dictionary mapping from each second mark (for which a frame is extracted) to the corresponding frame file path. None if frame extraction failed.
    """
    # Check if the video file exists
    if video_filepath is None or not os.path.isfile(video_filepath):
        raise ValueError(f"Video file not found: {video_filepath}")

    survey_name = kwargs.get('survey_name')
    station_name = kwargs.get('station_name')

 
    # Get information about the video using the 'get_video_info' function
    video_info = get_video_info(video_path=video_filepath)

    # Call the 'callback' function (if provided) with the video_info dictionary
    if callback is not None:
        callback(video_info)

    # Extract the video_name from the video_filepath
    video_filename = os.path.basename(video_filepath)
    video_name, _ = os.path.splitext(video_filename)

    # Generate prefix string, conditionally including survey and station names
    prefix = f"{survey_name + '_' if survey_name else ''}{station_name + '_' if station_name else ''}{video_name}_frame_"


    # Extract frames from the video using the 'extract_frames_every_n_seconds' function
    # and save them to the specified frames_dirpath
    frames_dict = extract_frames_every_n_seconds(
        video_filepath=video_filepath,
        frames_dirpath=frames_dirpath,
        prefix=prefix,        
        n_seconds=n_seconds,
        start_time_in_seconds=start_time_in_seconds
    )

    # If frames were extracted and saved successfully, return the frames_dict
    if not frames_dict:
        raise Exception(f'Error extracting frames from video: {video_filepath} to {frames_dirpath}. `frames_dict`: {frames_dict}')

    return frames_dict
