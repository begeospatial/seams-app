import os
import re
import streamlit as st
import pandas as pd
from PIL import Image
from bgstools.io import get_files_dictionary, is_directory_empty, delete_directory_contents, extract_frames, select_random_frames
from bgstools.utils import colnames_dtype_mapping, get_nested_dict_value
from bgstools.datastorage import DataStore, YamlStorage
from bgstools.io.media import get_video_info, convert_codec
from bgsio import search_yaml_files_by_subdir_filtered, create_subdirectory, load_yaml, create_new_directory, check_directory_exist_and_writable
import traceback
import yaml
from h3 import h3
from seams_utils import find_first_level_yaml_files, get_surveys_available


def extract_sequence(filename: str) -> str:
    """Extracts the sequence number from the filename and returns in the format SEC_xxxxxx."""
    # Use regex to find a sequence of exactly 6 digits preceded by 'frame__'
    match = re.search(r'frame__([\d]{6})_sec\.png$', filename)
    if match:
        return f"SEC_{match.group(1)}"
    else:
        raise ValueError(f"Invalid filename format: {filename}")
    

def lat_lng_to_h3(lat:float, lng:float, resolution=10):
    """
    Convert latitude and longitude to H3 index.
    
    Parameters:
        lat (float): Latitude of the location.
        lng (float): Longitude of the location.
        resolution (int): Resolution level of the H3 index, between 0 and 15.
            the default resolution is 10 which is a close approximation to a 5-meter grid size.

    Returns:
        str: H3 index in hexadecimal string format.
    """
    try:
        h3_index = h3.geo_to_h3(lat, lng, resolution)
        return h3_index
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def update_station_data(STATION_DATA:dict, STATION_FILEPATH:str):
    # Save the station data to a file.
     with open(STATION_FILEPATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(STATION_DATA, f, allow_unicode=True)

def show_survey_summary(STATIONS:dict):
    """
    Displays a summary of the survey in the sidebar.

    Parameters:
    - STATIONS (dict): A dictionary containing information about the stations.

    Overview:
    - Uses the session state to retrieve the name of the current survey.
    - If the survey name and stations data are available:
        - Displays an expander in the sidebar titled 'Survey summary'.
        - Within the expander, it shows a metric indicating the total number of stations in the survey.
        - A help message provides additional information about the metric.
    - If no stations are available, a warning is shown in the sidebar.

    Note:
    - The survey summary provides a quick glance for users about the status of the current survey, 
      particularly the number of stations.
    """
    SURVEY_NAME = get_nested_dict_value(st.session_state, ['APP', 'SURVEY', 'SURVEY_NAME'])
    
    if STATIONS is not None and SURVEY_NAME is not None:        
        with st.sidebar.expander(label='**Survey summary**', expanded=True):
            with st.container():
                if len(STATIONS)>0:
                    st.metric(
                        label=f"**{SURVEY_NAME} | number of stations:**", 
                        value=len(STATIONS),
                        delta=None,
                        help="Number of stations in the survey. **Note:** this number is updated when station's surveys are added or removed after `save survey data`."
                        )
                else:
                    st.warning('**No data available**')
    else:
        st.sidebar.warning('**No stations available**')


def get_stations_colnames(FILENAME:str = 'station_core_columns_dtypes.yaml'):
    """
    Retrieves column names for stations from a configuration file.

    Parameters:
    - FILENAME (str, optional): Name of the yaml configuration file that contains 
                                station columns and their data types. 
                                Default is 'station_core_columns_dtypes.yaml'.

    Returns:
    - dict: A dictionary mapping column names to their data types for stations.

    Overview:
    - Uses the session state to determine the path to the application configuration directory.
    - Loads the yaml file specified by FILENAME to get station columns and their data types.
    - Uses the `colnames_dtype_mapping()` function to generate a mapping from column names to data types.
    - Returns this mapping.

    Note:
    - This function facilitates dynamic loading of station column names based on a configuration file,
      allowing for flexibility in defining station data structures in the application.
    """
    CONFIG_DIRPATH = st.session_state['APP']['CONFIG']['CONFIG_DIRPATH']
    STATION_CORE_COLUMNS_DTYPES = load_yaml(os.path.join(CONFIG_DIRPATH, FILENAME))
    station_colnames_mapping = colnames_dtype_mapping(STATION_CORE_COLUMNS_DTYPES)
    return station_colnames_mapping


def create_videos_dataframe():
    """
    Creates an empty DataFrame with video-related column names based on a configuration file.

    Returns:
    - pd.DataFrame: An empty DataFrame with columns for video-related data.

    Overview:
    - Uses the session state to determine the path to the application configuration directory.
    - Loads the yaml configuration file specified by the 'VIDEO_CORE_COLUMNS_DTYPES' key from the 
      session state to get video columns and their data types.
    - Uses the `colnames_dtype_mapping()` function to generate a mapping from column names to data types.
    - Creates an empty DataFrame with the specified column names and data types.
    - If 'SELECTED' is not already a column in the DataFrame, a new 'SELECTED' column is added 
      with a default value of False.
    - Returns the created DataFrame.

    Note:
    - This function facilitates dynamic creation of a DataFrame structure for videos based on a 
      configuration file, allowing for flexibility in defining video data structures in the application.
    """
    CONFIG_DIRPATH = st.session_state['APP']['CONFIG']['CONFIG_DIRPATH']
    DTYPES = st.session_state['APP']['CONFIG']['DTYPES']

    VIDEO_CORE_COLUMNS_DTYPES = load_yaml(os.path.join(CONFIG_DIRPATH, DTYPES['VIDEO_CORE_COLUMNS_DTYPES']))
    dtype_mapping = colnames_dtype_mapping(VIDEO_CORE_COLUMNS_DTYPES)
    df = pd.DataFrame(columns=dtype_mapping.keys(), ).astype(dtype_mapping)
    if 'SELECTED' not in df.columns:
        df['SELECTED'] = False
    return df


st.cache_data()
def load_station_measurement_types():
    """
    Loads the data types of station measurements from a configuration file.

    Returns:
    - dict: A dictionary mapping column names to data types for station measurements.

    Overview:
    - Uses the session state to determine the path to the application configuration directory.
    - Loads the yaml configuration file specified by the 'STATION_MEASUREMENT_COLUMNS_DTYPES' key 
      from the session state to get the station measurement columns and their data types.
    - Uses the `colnames_dtype_mapping()` function to generate a mapping from column names to data types.
    - Returns the generated mapping.

    Note:
    - The resulting dictionary provides a standardized way to handle data types for station measurements 
      throughout the application. This ensures consistent data processing and avoids data type-related errors.
    - The `st.cache_data()` decorator ensures that this function uses cached results, reducing redundant 
      IO operations and improving application performance.
    """
    CONFIG_DIRPATH = st.session_state['APP']['CONFIG']['CONFIG_DIRPATH']
    DTYPES = st.session_state['APP']['CONFIG']['DTYPES']
    STATION_MEASUREMENT_COLUMNS_DTYPES = load_yaml(os.path.join(CONFIG_DIRPATH, DTYPES['STATION_MEASUREMENT_COLUMNS_DTYPES']))
    dtype_mapping= colnames_dtype_mapping(STATION_MEASUREMENT_COLUMNS_DTYPES)
    return dtype_mapping


def error_callback(error:str):
    """
    Displays an error message on the Streamlit frontend.

    Parameters:
    - error (str): The error message to be displayed.

    Overview:
    - This function takes an error message string as input and uses Streamlit's st.error() method 
      to display the error on the frontend.
    - It provides a standardized way to handle errors and inform the user of any issues that may arise during
      the application's execution.
    - By abstracting error handling into this function, other parts of the application can easily notify 
      the user of errors without having to directly interact with the Streamlit frontend.

    Example Usage:
    ```python
    try:
        # Some operation that may fail
        ...
    except Exception as e:
        error_callback(str(e))
    ```

    Note:
    - The primary purpose of this function is to enhance user experience by providing clear and 
      actionable feedback in case of errors.
    """
    st.error(error)


def get_videos_per_station(
        videos_df: pd.DataFrame, 
        linking_key:str = 'siteName', 
        subset_col: str = 'fileName',  
        callback: callable = error_callback) -> dict:
    
    """
    Extracts a dictionary of videos grouped by a specific station/site from a given DataFrame.

    Parameters:
    - videos_df (pd.DataFrame): DataFrame containing video details.
    - linking_key (str, optional): The column name in the DataFrame used to group the videos. Defaults to 'siteName'.
    - subset_col (str, optional): The column name from which video names are extracted. Defaults to 'fileName'.
    - callback (callable, optional): A function to handle exceptions or errors. Defaults to `error_callback`.

    Returns:
    - dict: A dictionary where the keys are site names and the values are dictionaries containing video filenames
            and their selection status.

    Overview:
    - This function processes the `videos_df` DataFrame to group videos by a specific site or station. 
    - Each site is represented as a key in the returned dictionary, and the corresponding value is another dictionary
      with video filenames as keys and their selection status as values.
    - The selection status indicates whether a video is currently selected or not, which is useful for tracking user choices.

    Example Usage:
    ```python
    df = pd.DataFrame({
        'siteName': ['site1', 'site1', 'site2', 'site2'],
        'fileName': ['video1.mp4', 'video2.mp4', 'video3.mp4', 'video4.mp4'],
        'SELECTED': [True, False, True, True]
    })

    result = get_videos_per_station(df)
    print(result)
    # Output: 
    # {'site1': {'video1.mp4': True, 'video2.mp4': False},
    #  'site2': {'video3.mp4': True, 'video4.mp4': True}}
    ```

    Note:
    - This function provides a structured way to extract video details from a DataFrame and organize them by sites or stations.
      This is useful for applications that deal with video data collected from multiple locations.
    """
    _videos = {}
    if 'SELECTED' not in videos_df.columns:
        videos_df['SELECTED'] = False
    for siteName, subset in videos_df.groupby(linking_key):
        _videos[siteName] = dict(zip(subset[subset_col], subset['SELECTED']))       
    return _videos


def create_data_editor(df:pd.DataFrame, key:str):
    """
    Display a Streamlit data editor for the given DataFrame and return the edited data.

    Parameters:
    - df (pd.DataFrame): The DataFrame to display and edit.
    - key (str): A unique string to identify the widget.

    Returns:
    - pd.DataFrame: The edited DataFrame.

    Raises:
    - ValueError: If the returned data editor is None.

    Overview:
    - This function leverages Streamlit's data editor widget to allow users to interactively edit a given DataFrame.
    - The edited data is then returned for further use or processing.
    - If for some reason the widget does not return data (returns None), a ValueError exception is raised.

    Example Usage:
    ```python
    sample_df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    edited_df = create_data_editor(sample_df, key="sample_key")
    print(edited_df)
    ```

    Note:
    - This function simplifies the process of displaying a data editor in Streamlit and handling the edited data.
      It can be used in Streamlit apps that require data input or editing capabilities.
    """
    
    
    data_editor = st.data_editor(
        data=df, 
        num_rows='dynamic', 
        key=key, 
        hide_index=True, 
        use_container_width=True,
        )
    if data_editor is not None:
        return data_editor
    else:
        raise ValueError(f'**`create_data_editor` exception occurred:** data_editor is None')
        

def evaluate_sets(A, B):
    """
    Evaluate the difference between two sets, A and B.

    Parameters:
    - A (set): The first set.
    - B (set): The second set.

    Returns:
    - set: If sets A and B are identical, an empty set is returned. 
           Otherwise, the difference between sets A and B (i.e., elements in A that are not in B) is returned.

    Example:
    >>> evaluate_sets({1, 2, 3}, {3, 4, 5})
    {1, 2}

    >>> evaluate_sets({1, 2, 3}, {1, 2, 3})
    set()

    Notes:
    - The function does not handle cases where the input is not of type 'set'.
    """
    if A == B:
        return set()  # Return an empty set if sets A and B are equal
    else:
        return A - B  # Return the difference between sets A and B


def build_survey_stations(SURVEY_NAME:str = None, stations_dict:dict = None):
    """
    Build a pandas DataFrame representing survey stations based on a given survey name and an optional stations dictionary.

    Parameters:
    - SURVEY_NAME (str, optional): The name of the survey. If provided, will be used to fetch appropriate column names.
    - stations_dict (dict, optional): A dictionary containing station data. Keys are station names and values are dictionaries
      containing the column name as key and the corresponding data as value.

    Returns:
    - pd.DataFrame: A DataFrame containing the survey stations with appropriate columns.

    Workflow:
    - Fetches required column names for the stations based on the survey name.
    - If stations_dict is provided, constructs a DataFrame using the data.
    - If stations_dict is not provided, an empty DataFrame with appropriate columns is returned.
    - Optional measurement types can be selected and their corresponding columns are added to the DataFrame.

    Examples:
    (Add appropriate examples showcasing the function's behavior)

    Notes:
    - The function assumes the existence of auxiliary functions like 'get_stations_colnames', 'load_station_measurement_types', etc.
    - The function may reinitialize the DataFrame when adding or removing optional columns.

    Warnings:
    - Every time optional columns are added or deleted, the DataFrame is reinitialized. Ensure any crucial data is preserved before calling this function.

    Dependencies:
    - Requires pandas (as pd) and streamlit (as st) to be imported.
    """
    if SURVEY_NAME is not None:
        stations_colnames = get_stations_colnames()

        if stations_dict is not None and stations_colnames is not None and len(stations_colnames)>0:
            # Hack to ensure you get the same order in the columns
            first_station = next(iter(stations_dict))
            saved_colnames = set(stations_dict[first_station].keys())
            difference_colnames = sorted(list(evaluate_sets(saved_colnames, set(stations_colnames.keys()))))            
            columns_to_add = list(stations_colnames.keys()) + difference_colnames 
            stations_df = pd.DataFrame.from_dict(stations_dict, orient='index', columns=columns_to_add)
            stations_df.reset_index(inplace=True, drop=True)

        else:
            stations_df = pd.DataFrame(columns=stations_colnames.keys(), ).astype(stations_colnames)
            measurement_colnames_dtypes = load_station_measurement_types()
            selected_optional_measurements = st.multiselect(
                '**Select optional measurement types:**',
                options=sorted(measurement_colnames_dtypes.keys()),                    
                format_func=lambda x: x.replace('measurementType__',''))
                    
            if selected_optional_measurements:
                _dtype_mapping =  {k: measurement_colnames_dtypes[k] for k in selected_optional_measurements}
                # The core columns are added first, then the optional columns are added. It will always result in an empty dataframe.
                # WARNING: The  the dataframe is reinitialized from empty to add or remove the optional columns. Every time the optional columns are added or deleted, the dataframe is reinitialized.
                # workflow: add or remove extra columns then add data to the dataframe.
                stations_df = pd.concat([stations_df, pd.DataFrame(columns= sorted(_dtype_mapping.keys()), ).astype(_dtype_mapping)], axis=1)
        if stations_df is not None:
            return stations_df
        
                
def build_survey_videos(SURVEY_NAME:str):
    """
    Build a pandas DataFrame representing survey videos based on a given survey name.

    Parameters:
    - SURVEY_NAME (str): The name of the survey. This name is used to determine which videos to include.

    Returns:
    - pd.DataFrame or None: A DataFrame containing the survey videos. If no videos are associated with the survey or if any error occurs, `None` is returned.

    Workflow:
    - Checks if a valid SURVEY_NAME is provided.
    - Calls an auxiliary function 'create_videos_dataframe' to get a DataFrame of videos associated with the survey.
    - Returns the videos DataFrame if it exists.

    Notes:
    - The function assumes the existence of an auxiliary function 'create_videos_dataframe'.
    - If SURVEY_NAME is not provided or is None, the function will not proceed.

    Dependencies:
    - Requires pandas (assuming the return type of 'create_videos_dataframe' is a DataFrame).

    Example:
    >>> build_survey_videos('Survey123')
    (Output will be a DataFrame containing videos related to 'Survey123' or None if no videos exist for the survey.)

    """
    if SURVEY_NAME is not None:
        videos_df = create_videos_dataframe()
        if videos_df is not None:
            return videos_df  


def build_header():
    """
    Construct and display the main title and sidebar title for a Streamlit app, specifically for the 'SEAMS-App | survey initialization' section.

    Workflow:
    - Sets the main title of the Streamlit app page.
    - Sets the title for the Streamlit app's sidebar.

    Notes:
    - This function does not have any return values. Its primary purpose is to display titles on the Streamlit app interface.
    - Make sure this function is called at the start of the Streamlit app or wherever the title needs to appear.

    Dependencies:
    - Requires Streamlit (as st) to be imported.

    Example Usage in Streamlit App:
    >>> build_header()
    (This will display "SEAMS-App | survey initialization" as both the main title and sidebar title on the Streamlit app page.)
    """
    st.title("SEAMS-App | survey initialization")
    st.sidebar.title("SEAMS-App | survey initialization")



def flatten_and_create_dataframe(input_dict, columns = ["siteName", "fileName", "SELECTED"]):
    """
    Flatten a nested dictionary into a list and then convert it into a pandas DataFrame.

    Parameters:
    - input_dict (dict): A nested dictionary where the outer dictionary has site names as keys and 
      the inner dictionaries have file names as keys with selected values (usually True/False) as their values.
    - columns (list, optional): List of column names for the resulting DataFrame. Defaults to ["siteName", "fileName", "SELECTED"].

    Returns:
    - pd.DataFrame: A DataFrame where each row represents a flattened record from the input dictionary.

    Workflow:
    - Iterate over the outer and inner dictionaries to extract the site name, file name, and selection value.
    - If the selected value is None, default to False.
    - Append the flattened data as a tuple to the flattened_data list.
    - Convert the flattened_data list into a DataFrame using the provided columns.

    Example:
    >>> data = {
            "SiteA": {"file1": True, "file2": None},
            "SiteB": {"file3": False}
        }
    >>> flatten_and_create_dataframe(data)
       siteName fileName  SELECTED
    0     SiteA    file1      True
    1     SiteA    file2     False
    2     SiteB    file3     False

    Dependencies:
    - Requires pandas (as pd) to be imported.

    Notes:
    - This function is useful when there's a need to work with flattened structures, especially in data analysis or visualization tasks.
    """
    flattened_data = []
    for site_name, files_info in input_dict.items():
        for file_name, selected_value in files_info.items():
            selected = selected_value if selected_value is not None else False
            flattened_data.append((site_name, file_name, selected))
    
    df = pd.DataFrame(flattened_data, columns=columns)
    return df

def partially_reset_session(keep_keys: list = ['CONFIG', 'SURVEY']):
    """
    Partially reset the session state of the Streamlit app, while preserving specific keys and their associated values.

    Parameters:
    - keep_keys (list, optional): A list of keys to be preserved during the session reset. Defaults to ['CONFIG', 'SURVEY'].

    Returns:
    - None: This function does not return anything but modifies the session state in place.

    Workflow:
    - Fetch the current keys from the 'APP' key within the session state.
    - Iterate over each key in the 'APP' key's value.
    - If the key is not in the list of keys to keep (keep_keys), reset its value to an empty dictionary.

    Dependencies:
    - Requires Streamlit (as st) to be imported.

    Notes:
    - This function is useful when there's a need to clear out specific session data but retain certain configuration or survey data.
    - Modifying the session state directly may affect the app's behavior. Use with caution and ensure the intended keys are passed to the 'keep_keys' parameter.

    Example Usage in Streamlit App:
    >>> partially_reset_session(keep_keys=['CONFIG'])
    (This will reset all keys under st.session_state['APP'] except for 'CONFIG'.)
    """
    APP_KEYS = st.session_state['APP'].keys()

    for key in APP_KEYS:
        if key not in keep_keys:
            st.session_state['APP'][key] = {}




def DEPRECIATED_process_yaml_files(yaml_files):
    """
    Process each YAML file in the provided dictionary to extract specific benthos interpretation information.

    Parameters:
    - yaml_files (dict): Dictionary containing YAML filenames as keys and their respective file paths as values.

    Returns:
    - dict: A modified dictionary based on the input 'yaml_files' where each entry is augmented with benthos interpretation data, specifically 'FRAMES' and 'RANDOM_FRAMES'.

    Workflow:
    - For each file in the input dictionary, load its content.
    - Check if the YAML content has keys 'APP' and 'BENTHOS_INTERPRETATION'.
    - If the conditions are met, iterate over each station in 'BENTHOS_INTERPRETATION' and extract information about 'FRAMES' and 'RANDOM_FRAMES'.
    - Update the input dictionary with the extracted information.

    Dependencies:
    - Requires a function or module 'load_yaml' to load the content of a YAML file. This dependency is assumed to be defined elsewhere in the codebase.
    
    Example Usage:
    >>> yaml_dict = {
        'config.yaml': '/path/to/config.yaml'
    }
    >>> processed_files = process_yaml_files(yaml_dict)
    >>> processed_files
    {
        'config.yaml': {
            'STATIONS': {
                'station_1': {
                    'FRAMES': [...],
                    'RANDOM_FRAMES': [...]
                },
                ...
            }
        }
    }

    Notes:
    - Only YAML files containing both 'FRAMES' and 'RANDOM_FRAMES' under the 'BENTHOS_INTERPRETATION' key will have this data extracted and added to the result.
    - If a YAML file does not match the expected structure or lacks the required keys, it will remain unchanged in the returned dictionary.
    """
    for filename, filepath in yaml_files.items():
        content = load_yaml(filepath)

        if 'APP' in content and 'BENTHOS_INTERPRETATION' in content['APP']:
            video_interpretation = content['APP']['BENTHOS_INTERPRETATION']
            stations = {}
            
            for station_key, station_value in video_interpretation.items():
                has_frames = 'FRAMES' in station_value
                has_random_frames = 'RANDOM_FRAMES' in station_value

                if has_frames and has_random_frames:
                    stations[station_key] = {
                        'FRAMES': station_value['FRAMES'],
                        'RANDOM_FRAMES': station_value['RANDOM_FRAMES']
                    }
            
            yaml_files[filename]['STATIONS'] = stations
            
    return yaml_files





st.cache_data()
def load_datastore(survey_filepath:str):
    """
    Load data from a specified YAML file into a DataStore object.

    Parameters:
    - survey_filepath (str): Absolute path to the desired YAML file.

    Returns:
    - DataStore: An instance of the DataStore class containing the data loaded from the YAML file.

    Raises:
    - FileNotFoundError: If the provided file path does not point to an existing file.
    - ValueError: If there's a failure in loading the file content into a DataStore object.

    Workflow:
    - Check if the provided file path is valid and points to an existing file.
    - Attempt to instantiate a DataStore object with data from the specified YAML file.
    - If there are any issues with these operations, relevant exceptions are raised.

    Dependencies:
    - This function assumes the existence of:
        * DataStore class that can consume data from a storage mechanism.
        * YamlStorage class that can read YAML files and serve as a storage mechanism for DataStore.

    Example Usage:
    >>> datastore = load_datastore('/path/to/survey.yaml')
    >>> type(datastore)
    <class 'DataStore'>

    Notes:
    - This function uses Streamlit's caching mechanism (`@st.cache_data()`) to prevent unnecessary reloading of the same data, which can improve app performance, especially when dealing with large YAML files.
    """    
    if not os.path.isfile(survey_filepath):
        st.warning('**No survey data available**. GO to **MENU>Survey initialization** create a new survey using the **Survey data management** menu. Refresh the app and try again.')
        raise FileNotFoundError(f"The file `{survey_filepath}` does not exist.")
  
    try:
        datastore = DataStore(YamlStorage(file_path=survey_filepath))
    except Exception as e:
        raise ValueError(f"Failed to load data from {survey_filepath}: {str(e)}")
        
    return datastore




def survey_selector_box(SURVEYS_AVAILABLE:dict, index:int = 0, format_func: callable = lambda x:f'{x}')->tuple:
    """
    Presents a Streamlit selectbox widget for users to choose a survey from a list of available ones.

    Parameters:
    - SURVEYS_AVAILABLE (dict): Dictionary mapping available survey names (keys) to their corresponding filepaths (values).

    Returns:
    - tuple: Contains two elements:
      1. Name of the selected survey.
      2. Filepath corresponding to the selected survey.
      Returns None if there are no available surveys.

    Workflow:
    - If surveys are available (i.e., SURVEYS_AVAILABLE is not empty):
        1. Display a selectbox with the list of survey names.
        2. Extract the filepath corresponding to the user's selection.
        3. Return the survey name and filepath as a tuple.
    - If no surveys are available, return None.

    Dependencies:
    - Relies on the Streamlit library for UI rendering.

    Example Usage:
    >>> surveys = {'SurveyA': '/path/to/SurveyA.yaml', 'SurveyB': '/path/to/SurveyB.yaml'}
    >>> get_survey_selected(surveys)
    ('SurveyA', '/path/to/SurveyA.yaml')  # This is an example, actual output may vary based on user's selection.

    Notes:
    - The function assumes Streamlit is running, and the selectbox will be rendered as part of an active Streamlit app.
    """
    if SURVEYS_AVAILABLE is not None and len(SURVEYS_AVAILABLE)>0:
        SURVEY_NAME = st.selectbox(
            label='**Available survey(s):**', 
            options=sorted(list(SURVEYS_AVAILABLE.keys())), 
            index=index,
            key='survey_selector',
            help='Select a benthic interpretation survey.',
            format_func=format_func,
            )
        
        SURVEY_FILEPATH = SURVEYS_AVAILABLE[SURVEY_NAME]
        return SURVEY_NAME, SURVEY_FILEPATH
    else:
        return None

def display_image_carousel(image_paths_dict: dict, RANDOM_FRAMES:dict = {}):
    """
    Display an image carousel with navigation slider.

    Args:
        image_paths_dict (dict): Dictionary mapping image titles to their file paths.

    Returns:
        None

    """
    if image_paths_dict is not None:
            
        num_images = len(image_paths_dict)
        image_titles = list(image_paths_dict.keys())

        col1, _, col3, _ = st.columns([1,1,2,1])
        with col1:            
            # Create a number input for navigation
            frame_number = st.number_input(label= "**Preview frame:**",  
                                    min_value=1,  
                                    max_value=num_images,
                                    step=1,
                                    help="Use to navigate through the available frames.",                                
                                    value=1)
        with col3:
            # Get the selected image title and path
            selected_image_title = image_titles[frame_number - 1]
            selected_image_path = image_paths_dict[selected_image_title]
            #
            FRAME_NUMBER = str(frame_number).zfill(2)

            # Display the corresponding title next to the number input
            if selected_image_title in RANDOM_FRAMES:
                st.subheader(f":star: Frame **:blue[{FRAME_NUMBER}]** | KEY: **:green[{selected_image_title}]**")
            else:
                st.subheader(f"Frame **{FRAME_NUMBER}** | KEY: **`{selected_image_title}`**")
            
            
        # Load and display the selected image
        if os.path.exists(selected_image_path):
                
            image = Image.open(selected_image_path)
            # Open the selected image file

            st.image(image, caption=f'Frame {FRAME_NUMBER} | KEY: {selected_image_title}', use_column_width=True)
            # Display the image with its caption

        else:
            st.error(f"Frame image not found: {selected_image_path}")
            # Display an error message if the image file is not found
    else:
        st.error("Frame images dictionary is None.")



def show_random_frames(
        has_random_frames:bool, 

        SURVEY_NAME:str,
        SURVEY_FILEPATH:str,
        VIDEO_NAME:str, 
        STATION_NAME:str,
        STATION_FILEPATH:str,
        STATION_DATA:dict, 
        codec:str = None, 
        suffix:str = '***'):
    """
    Interactively displays and manages random frames for benthic interpretation in a Streamlit application.
    
    Parameters:
    - has_random_frames (bool): Whether random frames are available for the current survey.
    - SURVEY_DATASTORE (DataStore): The DataStore object to interact with survey data.
    - SURVEY_DATA (dict): Dictionary containing survey details and related metadata.
    - STATION_NAME (str): Name of the station to manage random frames for.
    - codec (str, optional): Video codec. Used for checking if random frames can be generated for the video. Defaults to None.
    
    Workflow:
    1. If random frames are available for the current station:
        a. Extract the available frames and associated random frames.
        b. Display instructions and a selector for random frames.
        c. Show a status of selected random frames (e.g., number selected, warning if <10 or >10 frames are chosen).
        d. Display a carousel of images corresponding to the selected random frames.
    2. If random frames are not available:
        a. Based on the video codec, attempt to automatically generate random frames.
        b. Display a warning or guide the user on selecting a video with the correct suffix.
    
    Notes:
    - This function assumes that it is being run within an active Streamlit app.
    - Uses several global variables like VIDEO_NAME, SURVEY_NAME, and SURVEY_FILEPATH.
    - Relies on external functions like display_image_carousel and select_random_frames.
    """    

    if has_random_frames:

        FRAMES_DIRPATH = STATION_DATA['BENTHOS_INTERPRETATION'].get('FRAMES_DIRPATH', None)
        AVAILABLE_FRAMES = get_files_dictionary(
            FRAMES_DIRPATH, 
            file_extension='png', 
            keep_extension_in_key=True)
        
        # NEW:
        AVAILABLE_FRAMES = {extract_sequence(filename): AVAILABLE_FRAMES[filename] for filename in sorted(AVAILABLE_FRAMES.keys())}
        
        # Aqui esta el error
        RANDOM_FRAMES = STATION_DATA['BENTHOS_INTERPRETATION'].get('RANDOM_FRAMES', None)
        st.session_state['RANDOM_FRAMES_IDS'] = list(RANDOM_FRAMES.keys())
        _VIDEO_NAME = STATION_DATA['BENTHOS_INTERPRETATION'].get('VIDEO_NAME', None)            
        if _VIDEO_NAME == VIDEO_NAME and RANDOM_FRAMES is not None and len(RANDOM_FRAMES)>0:
            show_station_is_ready = True
            is_ready_for_interpretation = False
            with st.expander('**Intructions**', expanded=True):
                instructions = """
                    **Step 1:** Utilize the **preview frame** as the starting point for selecting random frames.
                    **Step 2:** Refine the automatic selection process of random frames as needed to ensure a total of 10 frames are chosen.
                    **Step 3:** Verify the accuracy of the selected frames by checking the **:green[ready for interpretation]** status.
                    **Step 4:** Adjust the frames in the **random frames selector** if necessary, while maintaining a total of 10 selected frames.
                    **Step 5:** Take note that selected frames will be marked in the **random frames selector** with a :white_check_mark: suffix for the extracted second of the video, indicating their selection.
                """
                st.info(instructions)
            with st.expander('**Random frames available**', expanded=True):
               
                fco1, fcol4 = st.columns([3,1])
                with fco1:
                    RANDOM_FRAMES_IDS = st.multiselect(
                    label='**random frames:**',
                        options=AVAILABLE_FRAMES.keys(),
                        default=sorted(st.session_state.get('RANDOM_FRAMES_IDS', None)), 
                        max_selections=10,
                        help='Select 10 random frames for interpretation.',                        
                        )
                    st.session_state['RANDOM_FRAMES_IDS'] = RANDOM_FRAMES_IDS
                    if len(RANDOM_FRAMES_IDS) < 10:
                        st.warning(f'Less than 10 frames selected. Requirement is 10 frames. Select {10-len(RANDOM_FRAMES_IDS)} more frame(s).')
                        show_station_is_ready = False
                        # -----
                    elif len(RANDOM_FRAMES_IDS) > 10:
                        st.warning('More than 10 frames selected. Requirement is 10 frames')
                        show_station_is_ready = False

                    else:
                        show_station_is_ready = True
                        RANDOM_FRAMES = {k: {
                            'FILEPATH': AVAILABLE_FRAMES[k],
                            'INTERPRETATION': {
                                'DOTPOINTS': {}, 
                                'STATUS': "NOT_STARTED"
                            }, 
                            } for k in RANDOM_FRAMES_IDS}
                        
                        STATION_DATA['BENTHOS_INTERPRETATION']['RANDOM_FRAMES'] = RANDOM_FRAMES


                # --------------------        
                with fcol4:
                    if show_station_is_ready:
                        st.markdown(f'# total : :green[{len(RANDOM_FRAMES_IDS)}] / 10')
                        is_ready = st.button(
                            '**ready for interpretation**', 
                            help=f'Selected **{STATION_NAME}** is **:green[ready for interpretation]**. Click to save data, then Go to **MENU > Benthos interpretation** to start the interpretation workflow.')
                        if is_ready:
                            is_ready_for_interpretation = True
                            STATION_DATA['BENTHOS_INTERPRETATION']['IS_READY'] = is_ready_for_interpretation
                            
                            update_station_data(
                                STATION_DATA=STATION_DATA,
                                STATION_FILEPATH=STATION_FILEPATH,
                            )
                            
                            st.toast('go to **MENU > Benthos interpretation**')
                                                 
                    else:
                        st.subheader(f'**number of random frames:**')
                        st.markdown(f'# total : :red[{len(RANDOM_FRAMES_IDS)}] / 10')
                        
                        show_station_is_ready = False
                
                # --------------------
                display_image_carousel(AVAILABLE_FRAMES, list(RANDOM_FRAMES.keys()))
        else:
            if  codec is not None and codec == 'h264':
                # FUTURE DEVS: Separate the logic for the random frames from the video codec.
                st.warning(f'**No random frames available** for selected video or random frames available with in video with sufix: :blue[{suffix}]. Attempting automatic generation of random frames.  Refresh the app and try again.')
                RANDOM_FRAMES = select_random_frames(frames=AVAILABLE_FRAMES, num_frames=10)
                
                if RANDOM_FRAMES is not None and len(RANDOM_FRAMES)==10:
                    STATION_DATA['BENTHOS_INTERPRETATION']['RANDOM_FRAMES'] = RANDOM_FRAMES                    
                    
                    display_image_carousel(AVAILABLE_FRAMES, list(RANDOM_FRAMES.keys()))
            else:
                st.warning(f'**Random frames available** for other video in the station. Select video with sufix: :blue[{suffix}]. Refresh the app and try again.') 

st.cache_data()
def show_video_player(video_player: st.empty, LOCAL_VIDEO_FILEPATH:str, START_TIME_IN_SECONDS:int = 0):
    """
    Display a video player in a Streamlit application starting from a specific time.

    Parameters:
    - video_player (st.empty): A Streamlit placeholder for the video player.
    - LOCAL_VIDEO_FILEPATH (str): Path to the local video file to be displayed.
    - START_TIME_IN_SECONDS (int, optional): Time (in seconds) from where the video should start playing. Defaults to 0 (start of video).

    Notes:
    - The function assumes that it's being run within an active Streamlit application.
    - Utilizes Streamlit's native video function to render the video player.
    - Uses the `st.cache_data()` decorator to cache the data, enhancing the function's performance by avoiding redundant computations.

    Example:
        >>> video_space = st.empty()
        >>> show_video_player(video_space, "path/to/local/video.mp4", 30)
    """
    video_player.video(LOCAL_VIDEO_FILEPATH, 
                       start_time=START_TIME_IN_SECONDS if START_TIME_IN_SECONDS is not None else 0) 

# NEW:
def get_subdir_name(file_path):
    """
    Extract the subdirectory name right below a file.

    Parameters:
        file_path (str): Full path of the file.

    Returns:
        str: Name of the subdirectory right below the file.
    """
    try:
        # Get the directory name where the file is located
        dir_path = os.path.dirname(file_path)
        
        # Get the last part of the directory name
        subdir_name = os.path.basename(dir_path)
        
        return subdir_name
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    

def save_stations(STATIONS:dict, VIDEOS:dict, SURVEY_DIRPATH:str, fileExtension:str = '.yaml') -> dict:
    """
    Save station data to individual files with specified extension.

    Args:
    - STATIONS (dict): A dictionary containing station data.
    - SURVEY_DIRPATH (str): Base directory path where station data will be saved.
    - fileExtension (str, optional): File extension for the saved files. Defaults to '.yaml'.

    Returns:
    - dict: A dictionary mapping site names to their corresponding file paths.
    """
    
    # Ensure that the fileExtension starts with a dot.
    if not fileExtension.startswith('.'):
        fileExtension = '.' + fileExtension

    STATIONS_FILEPATHS = {}

    for i, (_, _station) in enumerate(STATIONS.items()):
        siteName = _station.get('siteName', None)
        H3_index =  h3.geo_to_h3(_station['decimalLatitude'], _station['decimalLongitude'], 10)
        _station['H3_index'] = H3_index
        
        station = {'METADATA': _station}

        station['VIDEOS'] = VIDEOS[siteName]
        station['BENTHOS_INTERPRETATION'] = {}
        # Check if the siteName is valid.
        if siteName and len(siteName) > 0:
            siteNameToFileName = siteName.strip().replace(' ', '_')
            subdir = f'{H3_index}_{str(i).zfill(5)}'
            STATION_DIRPATH = os.path.join(SURVEY_DIRPATH, 'STATIONS', subdir)

            # Create a new directory for the station if it doesn't exist.
            if not os.path.exists(STATION_DIRPATH):
                os.makedirs(STATION_DIRPATH)
            
            STATION_FILEPATH = os.path.join(STATION_DIRPATH, f"{siteNameToFileName}{fileExtension}")
            

            if os.path.exists(STATION_FILEPATH):
                STATIONS_FILEPATHS[siteName] =  STATION_FILEPATH

                # Save the station data to a file.
                saved_station = load_yaml(STATION_FILEPATH)
                keys_set = set(saved_station.keys()) | set(station.keys())
                # UPDATING saved_station with station
                updated_station = {k: station.get(k, saved_station[k]) for k in keys_set}
                # Ensuring that we allways keep the saved data from BENTHOS_INTEPRETATION
                updated_station['BENTHOS_INTERPRETATION'] = saved_station['BENTHOS_INTERPRETATION']
            else:
                updated_station = station
            
            # Save the station data to a file.
            with open(STATION_FILEPATH, 'w', encoding='utf-8') as f:
                yaml.safe_dump(updated_station, f, allow_unicode=True)


    if len(STATIONS_FILEPATHS)>0:
        st.session_state['STATIONS_FILEPATHS'] = STATIONS_FILEPATHS
        return STATIONS_FILEPATHS
    else:
        raise ValueError("No valid stations found to save.")        

# NEW:
def get_available_stations(STATIONS_DIRPATH:str):
    if os.path.isdir(STATIONS_DIRPATH):
        _stations = find_first_level_yaml_files(STATIONS_DIRPATH)
        stations = {os.path.splitext(filename)[0]: _stations[filename] for filename in _stations}
        return stations
    else:
        return
    

def survey_data_editor(SURVEY_DATA:dict, SURVEY_DATASTORE:DataStore)->bool:
    """
    Interactive data editor in Streamlit for editing and saving survey data.

    This function provides an interface to edit the survey data, particularly focusing on stations 
    and associated videos. It allows users to modify existing data, add new entries, and save them 
    into a DataStore. It also provides validation checks to ensure data consistency between stations 
    and videos.

    Parameters:
    - SURVEY_DATA (dict): The survey data dictionary containing the survey details, stations, 
                          videos, and reports.
    - SURVEY_DATASTORE (DataStore): An object for storing and retrieving the modified survey data.

    Returns:
    - bool: True if both stations and videos data are available, False otherwise.

    Functionality:
    1. Stations Data Editor:
       - Allows users to edit station data.
       - Provides an interface to choose optional measurements.
       - Presents a user-friendly interface to paste data into the application.

    2. Videos Data Editor:
       - Lets users edit video-related data.
       - Checks the link between videos and their respective stations, and warns if discrepancies are found.

    3. Data Saving:
       - Provides a button for users to save the modified survey data back to the DataStore.

    4. Data Validation:
       - After saving, validates the survey data to ensure stations are linked to videos and vice versa.
       - Presents warnings for any inconsistencies found.
    """

    # FUTURE: DEPRECIATED STATIONS AND VIDEOS FROM SURVEY_DATA
    if SURVEY_DATA is not None and len(SURVEY_DATA)>0:
        SURVEY_NAME= SURVEY_DATA.get('SURVEY', None).get('SURVEY_NAME', None)
        STATIONS_FILEPATHS = SURVEY_DATA.get('STATIONS_FILEPATHS', {})

        if len(STATIONS_FILEPATHS) >0:
            _STATIONS = {station: load_yaml(filepath)['METADATA'] for station, filepath in STATIONS_FILEPATHS.items()}
            _VIDEOS = {station: load_yaml(filepath)['VIDEOS'] for station, filepath in STATIONS_FILEPATHS.items()}
        else:
            _STATIONS = {}
            _VIDEOS = {}


    # Stations
    help_message= "**WORKFLOW:** Add or remove optional columns first then add data to the dataframe, matching the colums order. \n" \
            "**WARNING:** Every time the optional columns are added or deleted, the dataframe is reinitialized from scratch. \n" \
            " **NOTE**: `siteName` **:red[is case sensitive]**. You can also, ***Copy and Paste*** the stations information from Excel, just ensure to match the columns order. \n" \
            "**Customization is possible**. The optional columns are defined in the `config/station_measurement_columns_dtypes.yaml`." 
            
    with st.expander('**Stations data editor**', expanded=False):
            
        st.subheader(f'**{SURVEY_NAME}** | data editor')                           
        st.markdown('**Stations**' , help= help_message)

        # ----build_survey_stations

        stations_colnames = get_stations_colnames()

        if _STATIONS is not None and len(_STATIONS) >=1 and len(stations_colnames)>0:
            # Hack to ensure you get the same order in the columns
            first_station = next(iter(_STATIONS))
            saved_colnames = set(_STATIONS[first_station].keys())
            difference_colnames = sorted(list(evaluate_sets(saved_colnames, set(stations_colnames.keys()))))            
            columns_to_add = list(stations_colnames.keys()) + difference_colnames 
            stations_df = pd.DataFrame.from_dict(_STATIONS, orient='index', columns=columns_to_add)
            stations_df.reset_index(inplace=True, drop=True)

        else:

            stations_df = pd.DataFrame(columns=stations_colnames.keys(), ).astype(stations_colnames)
            measurement_colnames_dtypes = load_station_measurement_types()
            selected_optional_measurements = st.multiselect(
                '**Select optional measurement types:**',
                options=sorted(measurement_colnames_dtypes.keys()),                    
                format_func=lambda x: x.replace('measurementType__',''))
                    
            if selected_optional_measurements:
                _dtype_mapping =  {k: measurement_colnames_dtypes[k] for k in selected_optional_measurements}
                # The core columns are added first, then the optional columns are added. It will always result in an empty dataframe.
                # WARNING: The  the dataframe is reinitialized from empty to add or remove the optional columns. Every time the optional columns are added or deleted, the dataframe is reinitialized.
                # workflow: add or remove extra columns then add data to the dataframe.
                stations_df = pd.concat([stations_df, pd.DataFrame(columns= sorted(_dtype_mapping.keys()), ).astype(_dtype_mapping)], axis=1)

        # --------------------
       
        
        data_editor = create_data_editor(stations_df, key=f'stations_editor')
        STATIONS = data_editor.set_index('siteName', drop=False).to_dict(orient='index')

    
        # --------------------
        if _VIDEOS is not None and len(_VIDEOS)>0:
            _videos_df = flatten_and_create_dataframe(_VIDEOS, columns = ["siteName", "fileName", "SELECTED"])
        else:
            _videos_df = None
        # --------------------
        # Videos
        st.markdown('**Videos**', help="Add the relevant video stations to the videos table, including the site name and filename. "
                                        "You can also, ***Copy and Paste*** from Excel. Use the 'SELECT' indicator if the video is intended for benthos interpretation.  " 
                                        "Feel free to include multiple videos for each station (`siteName` :red[**is case-sensitive**]), if you have more than one per station. N")
        
        if _videos_df is not None and len(_videos_df)>0:
            videos_df = _videos_df
        else:
            videos_df = build_survey_videos(SURVEY_NAME=SURVEY_NAME)

        videos_data_editor_dict = create_data_editor(videos_df, key=f'videos_editor')
        VIDEOS = get_videos_per_station(videos_data_editor_dict)

        # FUTURE: DEPRECIATE
        #SURVEY_DATA['VIDEOS'] = VIDEOS
  
        VIDEOS_NOT_IN_STATIONS = {}
        for siteName, v in VIDEOS.items():
            if siteName not in STATIONS:
                VIDEOS_NOT_IN_STATIONS[siteName] = v
        if len(VIDEOS_NOT_IN_STATIONS)>0:
            st.warning(f'**Not stations found for videos in expected stations:** {VIDEOS_NOT_IN_STATIONS}')
        #    
        if STATIONS is not None and len(STATIONS) >0:
        
            STATIONS_WITHOUT_VIDEOS = set(STATIONS.keys()) - set(VIDEOS.keys())
            STATIONS_WITH_VIDEOS = set(STATIONS.keys()) & set(VIDEOS.keys())
            REPORT ={
                'STATIONS_WITH_VIDEOS': STATIONS_WITH_VIDEOS,
                'STATIONS_WITHOUT_VIDEOS': STATIONS_WITHOUT_VIDEOS,
                'VIDEOS_NOT_IN_STATIONS': VIDEOS_NOT_IN_STATIONS,
                }
            # SURVEY_DATA['REPORTS'].update(REPORT)

            st.info(f'Number of stations with videos: {len(STATIONS_WITH_VIDEOS)}')

            if STATIONS_WITH_VIDEOS is not None:
                # stations handler
                
                VIDEO_STATIONS = {station: STATIONS[station] for station in STATIONS if station in STATIONS_WITH_VIDEOS}
                #SURVEY_DATA['STATIONS'] = STATIONS_FILEPATHS

            if STATIONS_WITHOUT_VIDEOS is not None and  len(STATIONS_WITHOUT_VIDEOS)>0:
                st.warning(f'**Stations without videos:** {STATIONS_WITHOUT_VIDEOS}')

        
        # --------------------
        save_stations_btn = st.button('save survey data & continue', key=f'save_survey_data')
        
        IS_SURVEY_DATA_AVAILABLE = False        
        if save_stations_btn:
            if len(VIDEO_STATIONS) >0:
                STATIONS_FILEPATHS =  save_stations(STATIONS=VIDEO_STATIONS, VIDEOS=VIDEOS, SURVEY_DIRPATH=SURVEY_DATA['SURVEY']['SURVEY_DIRPATH'])
                SURVEY_DATA['STATIONS_FILEPATHS'] = STATIONS_FILEPATHS
                st.session_state['STATIONS_FILEPATHS'] = STATIONS_FILEPATHS
                IS_SURVEY_DATA_AVAILABLE = True
            else:
                IS_SURVEY_DATA_AVAILABLE = False

            
            with st.spinner('Saving survey data...'):
                try:
                    SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})                    
                except Exception as e:
                    st.error(f'**An exception ocurred saving the survey data:** {e}')                   
                else:        
                    st.success('Data saved. **Refresh the app and continue**.')
                     
        else:
            st.info('**Do not forget to save the survey data when you are done editing.**')

        return IS_SURVEY_DATA_AVAILABLE
        # --------------------


def show_video_processing(
        SURVEY_NAME:str,
        STATION_NAME:str,
        STATION_DATA:dict,
        STATION_FILEPATH:str,
        VIDEO_NAME:str,
        LOCAL_VIDEOS:dict,
        SURVEY_DATA:dict,
        SURVEY_DATASTORE:DataStore):
    
    """
    Displays video processing operations in a Streamlit app.

    Parameters:
    ----------
    
    STATION_NAME : str
        The name of the station where the video was taken.
    
    VIDEO_NAME : str
        The name of the video file being processed.
    
    LOCAL_VIDEOS : dict
        A dictionary containing video names as keys and their respective file paths as values.
    
    SURVEY_DATA : dict
        A dictionary containing survey data.
    
    SURVEY_DATASTORE : DataStore
        An instance of a DataStore class for storing and retrieving survey data.
    
    Returns:
    -------
    None. This function uses Streamlit functions to display interactive components and messages directly on the app.
    
    Overview:
    --------
    This function performs several tasks:
    1. Verifies the existence of survey data and local videos.
    2. Checks the codec of the provided video and suggests conversion if necessary.
    3. Displays the video using a player.
    4. Provides an option to extract frames from the video at specified intervals.
    5. Saves the extracted frames and updates the SURVEY_DATA dictionary accordingly.
    
    Functionality:
    -------------
    1. Validates the presence of SURVEY_DATA and LOCAL_VIDEOS.
    2. Modifies the keys of LOCAL_VIDEOS to include the videos_file_extension.
    3. Fetches the video codec information.
    4. Warns if the video codec is unknown.
    5. Provides a decision tree for video codec types:
        - For H.265 (HEVC), it suggests converting to H.264.
        - For H.264 (AVC), it states no conversion is necessary.
        - For other codecs, it suggests converting to H.264.
    6. If required, it provides a button to convert the video codec.
    7. If the video codec is H.264, displays the video player.
    8. Enables frame extraction from the video, allowing the user to specify starting time and the frequency of frame extraction.
    9. Handles the storage and deletion of frames.
    10. Informs the user of the process's success or provides appropriate warnings if any issues arise.

    Notes:
    -----
    This function is specifically designed for use within a Streamlit app and may require modifications 
    if used in a different context.
    """
    if SURVEY_DATA is not None and len(SURVEY_DATA)>0:
        VIDEOS_DIRPATH = SURVEY_DATA['SURVEY']['VIDEOS_DIRPATH']
        VIDEO_NAMES  = STATION_DATA.get('VIDEOS', {})
        LOCAL_VIDEOS = {k: os.path.join(VIDEOS_DIRPATH, k) for k in VIDEO_NAMES.keys()}

        if LOCAL_VIDEOS is not None and len(LOCAL_VIDEOS)>0:
            
            with st.expander('**Video preprocessing:**', expanded=True):
                LOCAL_VIDEO_FILEPATH = LOCAL_VIDEOS.get(VIDEO_NAME, None)
                
                if LOCAL_VIDEO_FILEPATH is not None:
                    if VIDEO_NAME is not None:
                        video_info= get_video_info(LOCAL_VIDEO_FILEPATH)
                        if video_info is not None:
                            codec = video_info['codec']
                        else:
                            codec = None
                    else:
                        codec = None
                        video_info = None

                    if codec == None:
                        REQUIRES_VIDEO_CONVERSION = None
                        st.warning('**Video codec is unknown**. Ensure video is available in the VIDEOS folder. Refresh the app and try again.')
                        
                    elif codec == "hevc":
                        REQUIRES_VIDEO_CONVERSION = True
                        # st.info(f"When there are available frames, the selected station and video name will display a '***' suffix.")
                        st.warning(f'**{VIDEO_NAME}** **Video codec is H.265** High-Efficiency Video Coding (HEVC), also known as H.265 video. Convert to H.264 codec and extract frames.')
                    elif codec == "avc1" or codec == "h264" or codec == "h.264":
                        REQUIRES_VIDEO_CONVERSION = False
                        st.info('**Video codec is H.264** Advanced Video Coding (AVC), also known as H.264 video.')
                        st.success('No conversion needed. If no frames are available, use the **extract frames** button below.')
                    else:
                        REQUIRES_VIDEO_CONVERSION = True
                        st.warning(f'**Video codec is {codec}**. Convert to H.264 codec.')

                    vcol1, vcol2 = st.columns([3,2])
                    with vcol1:
                        st.markdown(f"### {STATION_NAME} | {VIDEO_NAME}")
                            
                    with vcol2:
                        if LOCAL_VIDEO_FILEPATH is not None and os.path.exists(LOCAL_VIDEO_FILEPATH):
                            missing_video = False

                            if REQUIRES_VIDEO_CONVERSION is not None and REQUIRES_VIDEO_CONVERSION:
                                convert_video_codec_btn = st.button(
                                    label=f'APPLY VIDEO CONVERSION',)
                                
                                if convert_video_codec_btn:
                                    with st.spinner():                                                
                                        converted_video_filename = f'SEAMS__{VIDEO_NAME}'                                            
                                        converted_video_filepath = os.path.join(VIDEOS_DIRPATH, converted_video_filename)
                                        VIDEO_CONVERSION_DONE = convert_codec(
                                            input_file=LOCAL_VIDEO_FILEPATH,
                                            output_file=converted_video_filepath,
                                            callback=error_callback
                                            )
                                    if VIDEO_CONVERSION_DONE:
                                        st.success(f'Video codec conversion successful. Output file: {converted_video_filename}')
                                        _VIDEO_NAME = converted_video_filename
                                        _VIDEO_FILEPATH = converted_video_filepath
                                        _VIDEO_DIRPATH = os.path.dirname(_VIDEO_FILEPATH)
                                        VIDEO_INFO = get_video_info(_VIDEO_FILEPATH)
                                        st.session_state['codec'] = VIDEO_INFO['codec']
                                                                                    
                                        VIDEO_INTERPRETATION = { 
                                                'REQUIRES_VIDEO_CONVERSION': REQUIRES_VIDEO_CONVERSION,
                                                'SURVEY_NAME': SURVEY_NAME,
                                                'SURVEY_DIRPATH': SURVEY_DIRPATH,
                                                'SURVEY_FILEPATH': SURVEY_FILEPATH,
                                                'STATION_NAME': STATION_NAME,
                                                'STATION_DIRPATH': STATION_DIRPATH,                                
                                                'VIDEO_NAME': _VIDEO_NAME, 
                                                'VIDEO_FILEPATH': _VIDEO_FILEPATH,
                                                'VIDEO_DIRPATH': _VIDEO_DIRPATH,
                                                'VIDEO_INFO': VIDEO_INFO,}
                                        
                                        SURVEY_DATA['VIDEOS'][STATION_NAME].update({_VIDEO_NAME: True, 
                                                                                    VIDEO_NAME: False})
                                        
                                        if STATION_NAME not in SURVEY_DATA['BENTHOS_INTERPRETATION']:
                                            SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME] = {}

                                        SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME].update(VIDEO_INTERPRETATION)
                                        
                                        SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})
                                        st.toast('Data saved. Ready for frames extraction.')
                                        st.rerun()
                            elif ~REQUIRES_VIDEO_CONVERSION:
                                VIDEO_FILEPATH = LOCAL_VIDEO_FILEPATH
                                VIDEO_DIRPATH = os.path.dirname(VIDEO_FILEPATH)

                                VIDEO_INFO = get_video_info(VIDEO_FILEPATH)
                                st.session_state['codec'] = VIDEO_INFO['codec']

                                VIDEO_INTERPRETATION = { 
                                    'REQUIRES_VIDEO_CONVERSION': REQUIRES_VIDEO_CONVERSION,
                                    'SURVEY_NAME': SURVEY_NAME,
                                    'SURVEY_DIRPATH': SURVEY_DIRPATH,
                                    'SURVEY_FILEPATH': SURVEY_FILEPATH,
                                    'STATION_NAME': STATION_NAME,
                                    'STATION_DIRPATH': STATION_DIRPATH,                                
                                    'VIDEO_NAME': VIDEO_NAME, 
                                    'VIDEO_FILEPATH': VIDEO_FILEPATH,
                                    'VIDEO_DIRPATH': VIDEO_DIRPATH,
                                    'VIDEO_INFO': VIDEO_INFO,}
                            
                                SURVEY_DATA['VIDEOS'][STATION_NAME].update({VIDEO_NAME: True})

                                if STATION_NAME not in SURVEY_DATA['BENTHOS_INTERPRETATION']:
                                    SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME] = {}

                                SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME].update(VIDEO_INTERPRETATION)
                                
                                SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})
                                st.toast('Data saved. Ready for frames extraction.')
                            

                    
                    # ------------------------------
                    if codec is not None and codec=='h264':
                        st.session_state['codec'] = codec
                        st.divider()
                        
                        c1, c2 = st.columns([3,1])
                        with c1:
                            video_player = st.empty()
                        with c2:
                            frames_message_00 = st.empty()
                            start_time_slider = st.empty()                    
                            extract_frames_num_input = st.empty()
                            confirm_btn = st.empty()
                            frames_message_01 = st.empty()
                            frames_message_02 = st.empty()
                        
                        _FRAMES = SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME].get('FRAMES', None)
                        _RANDOM_FRAMES = SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME].get('RANDOM_FRAMES', None)

                        if _FRAMES is not None and len(_FRAMES)>0:
                            _START_TIME_IN_SECONDS = _FRAMES.get('START_TIME_IN_SECONDS', 0)
                            _EXTRACT_ONE_FRAME_X_SECONDS = _FRAMES.get('EXTRACT_ONE_FRAME_X_SECONDS', 2)
                        else:
                            _START_TIME_IN_SECONDS = 0
                            _EXTRACT_ONE_FRAME_X_SECONDS = 2

                        if _FRAMES is not None and len(_FRAMES)>=10:
                            frames_message_00.success(f'**Frames available**. Total frames: {len(_FRAMES)}')
                            if _RANDOM_FRAMES is not None and len(_RANDOM_FRAMES)==10:
                                frames_message_01.success(f'**Random frames available**. Total frames: {len(_RANDOM_FRAMES)}')
                            else:
                                frames_message_01.warning(f'**No random frames available**. Attempting to generate random frames.')
                                _RANDOM_FRAMES = select_random_frames(frames=_FRAMES, num_frames=10)
                                
                                if _RANDOM_FRAMES is not None and len(_RANDOM_FRAMES)==10:
                                    STATION_DATA['BENTHOS_INTERPRETATION']['RANDOM_FRAMES'] = _RANDOM_FRAMES
                                    frames_message_02.success(f'Frames extracted successfully. Total frames: {len(_FRAMES)}. Refresh the app.')
                                else:
                                    _RANDOM_FRAMES = None

                                    frames_message_02.warning('**No random frames available**. Extract frames from the video.')                            
                        else:
                            frames_message_00.warning(f'**No frames available**. Extract frames from the video.')


                        max_value = int(video_info['duration'])                      
                        START_TIME_IN_SECONDS =  start_time_slider.slider(
                            label='**start time**:', 
                            min_value=0, 
                            max_value=max_value if max_value is not None else 0, 
                            value=_START_TIME_IN_SECONDS, 
                            step=1, format="%d sec")

                        if START_TIME_IN_SECONDS is not None:
                            show_video_player(
                                video_player=video_player, 
                                LOCAL_VIDEO_FILEPATH= LOCAL_VIDEO_FILEPATH, 
                                START_TIME_IN_SECONDS= START_TIME_IN_SECONDS)
                            
                            SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['START_TIME_IN_SECONDS'] = START_TIME_IN_SECONDS                            

                        max_value = int(video_info['duration'])
                        EXTRACT_ONE_FRAME_X_SECONDS =  extract_frames_num_input.number_input(
                            label=f'***n*-seconds** to extract a frame:', 
                                    min_value=1, 
                                    max_value=int(max_value / 10), 
                                    value= _EXTRACT_ONE_FRAME_X_SECONDS,
                                    help=f'Select the number of seconds to extract a one frame from the video. Default is **{_EXTRACT_ONE_FRAME_X_SECONDS} seconds.** ' \
                                        f'The maximum value is the **total video duration: {max_value} seconds** divided by 10 frames. ' \
                                        ' These frames will be randomized and selected to be used for benthic interpretation.' \
                                        ' **:red[WARNING. Frames already existing in the directory will be deleted.]**',                                        
                                    step=1,
                                    key='extract_frames_slider' 
                                    )
                        if EXTRACT_ONE_FRAME_X_SECONDS is not None:
                            SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['EXTRACT_ONE_FRAME_X_SECONDS'] = int(EXTRACT_ONE_FRAME_X_SECONDS)  
                            
                        if confirm_btn.button(label='extract frames', help='Extract frames from the video.'):
                            FRAMES_DIRPATH = os.path.join(STATION_DIRPATH, 'FRAMES')
                            create_new_directory(FRAMES_DIRPATH)
                            
                            if not is_directory_empty(FRAMES_DIRPATH):
                                try:
                                    st.warning('FRAMES EXISTS')
                                    delete_directory_contents(FRAMES_DIRPATH)
                                except EOFError as e:
                                    st.error(f'**`FRAMES_DIRPATH`: {FRAMES_DIRPATH} exception occurred:** {e}') 
                            
                            if is_directory_empty(FRAMES_DIRPATH):
                                frames_message_01.info(f'Extracting frames from video every **{EXTRACT_ONE_FRAME_X_SECONDS} seconds.** This may take a while...')
                                with st.spinner(text='Extracting frames from video...'):
                                    FRAMES = extract_frames(
                                        video_filepath=LOCAL_VIDEO_FILEPATH,
                                        frames_dirpath= FRAMES_DIRPATH,
                                        n_seconds=EXTRACT_ONE_FRAME_X_SECONDS,
                                        start_time_in_seconds=START_TIME_IN_SECONDS,
                                        kwargs={'survey_name': SURVEY_NAME, 
                                                'station_name': STATION_NAME
                                                })
                                st.success(f'Frames extracted successfully. **Total frames extracted: {len(FRAMES)}**. Refresh the app to continue.')

                                if FRAMES is not None and len(FRAMES)>10:
                                    RANDOM_FRAMES = select_random_frames(frames=FRAMES, num_frames=10)
                                    
                                    SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['FRAMES'] = FRAMES
                                    SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES'] = RANDOM_FRAMES

                                    frames_message_01.success(f'Frames extracted successfully. **Total frames extracted: {len(FRAMES)}**')
                                    frames_message_02.success(f'**Done!!! {len(RANDOM_FRAMES)} random frames** selected successfully. **Refresh the app to continue.**')
                                    st.toast('RANDOM FRAMES available')
                                    #SURVEY_DATASTORE.storage_strategy.data['APP'] = SURVEY_DATA
                                    SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})

        else:
            st.info(f'**Videos not available**. Copy the survey videos in the VIDEOS folder: **`/data/SURVEYS/{VIDEOS_DIRPATH.split("/data/SURVEYS/")[1]}`**. Ensure the video names match the videos in the VIDEOS folder. **Refresh the app and try again.**')
    else:
        st.write('**No survey data available**. Ensure survey data is available in the SURVEY folder or within the **<survey_file.yaml>**  Refresh the app and try again.')


def get_available_videos(SURVEY_DATA:dict, STATION_NAME:str, VIDEOS_DIRPATH:str, videos_file_extension:str = '.mp4')->dict:
    """
    Retrieves a list of available video names based on the videos present in a given directory 
    and those registered in the survey data for a specific station.

    Parameters:
    ----------
    SURVEY_DATA : dict
        A dictionary containing the survey data. This data should have a key 'VIDEOS' 
        which contains registered video names for various stations.
    
    VIDEOS_DIRPATH : str
        The directory path where video files are located.

    videos_file_extension : str, optional
        The file extension for videos. Defaults to '.mp4'.

    Returns:
    -------
    dict:
        A dictionary of video names that are both present in the given directory 
        and registered in the SURVEY_DATA for a specific station. If no matches are found,
        None is returned.

    Overview:
    --------
    This function performs the following operations:
    1. Gets a list of all videos in the specified directory with the given file extension.
    2. Checks for registered videos in SURVEY_DATA under the 'VIDEOS' key for a specific station.
    3. Compares the local videos with the registered videos and returns the intersection.

    Notes:
    -----
    The function relies on the assumption that video names in SURVEY_DATA under 'VIDEOS' do 
    not include the file extension. The function appends the file extension to the video names 
    from the directory to make the comparison.
    """
    
    LOCAL_VIDEOS =  get_files_dictionary(VIDEOS_DIRPATH, file_extension=videos_file_extension)
    LOCAL_VIDEOS = {f'{k}{videos_file_extension}': v for k, v in LOCAL_VIDEOS.items()}
    SET_LOCAL_VIDEOS = set(LOCAL_VIDEOS.keys() )

    if LOCAL_VIDEOS is not None and len(LOCAL_VIDEOS)>0:
        # get the  for the selected station
        REGISTERED_VIDEOS = SURVEY_DATA.get('VIDEOS', {})

        if len(REGISTERED_VIDEOS)>0:
            EXPECTED_VIDEOS = REGISTERED_VIDEOS.get(STATION_NAME, {})
            # Ensuring that the selector only shows the videos available for the selected station
            SET_EXPECTED_VIDEOS = set(EXPECTED_VIDEOS.keys())                                
            AVAILABLE_VIDEOS = [v for v in SET_EXPECTED_VIDEOS if v in SET_LOCAL_VIDEOS]
            return AVAILABLE_VIDEOS



def get_available_surveys():
    SURVEYS_DIRPATH = get_nested_dict_value(st.session_state, ['APP', 'CONFIG', 'SURVEYS_DIRPATH'])    
    SURVEYS_AVAILABLE = get_surveys_available(SURVEYS_DIRPATH)
    return SURVEYS_AVAILABLE


def stations_selector_box(STATIONS_AVAILABLE:dict, index:int = 0, format_func:callable = lambda x:f'{x}' ):
    # lambda x: f'{x} {suffix}' if 'FRAMES' in SURVEY_DATA.get('BENTHOS_INTERPRETATION', {}).get(x, {}) else x,
    if STATIONS_AVAILABLE is not None and len(STATIONS_AVAILABLE)>0:
            
        STATION_NAME = st.selectbox(
                        label='**Available station(s):**', 
                        options=STATIONS_AVAILABLE.keys(), 
                        index=index,
                        key='station_selector',
                        help='Select a station for benthic interpretation.',
                        format_func=format_func
                    )
        STATION_FILEPATH = STATIONS_AVAILABLE[STATION_NAME]
        
    else:
        STATION_NAME = None
        STATION_FILEPATH = None

    return STATION_NAME, STATION_FILEPATH


def run():
    """
    Main execution function for a Streamlit-based application to manage and view video-based survey data.

    Function Flow:
    -------------
    1. Retrieves application configurations (SURVEYS_DIRPATH, VIDEOS_DIRPATH, etc.) from the Streamlit session state.
    2. Checks for available surveys and prepares the necessary configurations.
    3. Displays a column-based layout using Streamlit.
    4. In the first column:
        - Enables selection of a survey from available surveys.
        - Loads the survey's data and manages directory paths.
        - Updates session state with the current survey's data.
    5. In the second column:
        - Checks for available stations with videos for the selected survey.
        - Displays a summary of the survey and allows for the selection of a station.
        - Retrieves the benthos interpretation data for the selected station.
    6. In the third column:
        - Checks and displays available videos for the selected station.
        - Allows for the selection of a video.
        - If the station already has interpreted frames, highlights this to the user.
    7. In the fourth column:
        - Displays success messages and additional controls based on the station's and video's data.
    8. Displays video processing and random frames extraction UI, if necessary.
    9. Allows for editing of the survey data.

    Prerequisites:
    -------------
    - A Streamlit session state (`st.session_state`) containing initial configurations like `APP`, `CONFIG`, etc.
    - Auxiliary functions such as `get_nested_dict_value`, `get_SURVEYS_AVAILABLE`, `load_datastore`, etc.
      must be correctly defined and available for use.

    Notes:
    -----
    - This function primarily controls the UI flow and data interactions for the application.
    - It heavily relies on Streamlit's session state mechanism to store and retrieve data across different steps.
    - The function's structure is columnar to make the most of Streamlit's layout capabilities.
    """
    # --------------------
    SURVEYS_DIRPATH = get_nested_dict_value(st.session_state, ['APP', 'CONFIG', 'SURVEYS_DIRPATH'])
    VIDEOS_DIRPATH = get_nested_dict_value(st.session_state, ['APP', 'CONFIG', 'VIDEOS_DIRPATH'])
    SURVEYS_AVAILABLE = get_surveys_available(SURVEYS_DIRPATH)
    suffix = '***'
    st.session_state['suffix'] = suffix

    # --------------------
    AVAILABLE_STATIONS_WITH_VIDEOS = None
    if SURVEYS_AVAILABLE is not None and len(SURVEYS_AVAILABLE) > 0:
        
        
        # --------------------
        suffix = st.session_state.get('suffix', '***')
        # --------------------
        col1, col2, col3, col4 = st.columns([2,1,2,1])

        with col1:
            SURVEY_SELECTED = survey_selector_box(SURVEYS_AVAILABLE)           
            if SURVEY_SELECTED is not None:
                SURVEY_NAME, SURVEY_FILEPATH = SURVEY_SELECTED
                SURVEY_DIRPATH = os.path.dirname(SURVEY_FILEPATH)
                VIDEOS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'VIDEOS')

                if not os.path.exists(VIDEOS_DIRPATH):
                    create_new_directory(VIDEOS_DIRPATH)
                else:
                    st.session_state['APP']['CONFIG']['VIDEOS_DIRPATH'] = VIDEOS_DIRPATH

                try:
                    # DATASTORE is initialized here
                    SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)
                    SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data.get('APP', {})
                except Exception as e:
                    st.error(f'An error ocurred loading the survey data. Check the **<survey_file.yaml>** is not empty. If empty, please delete the file and its subdirectory and start a new survey. **{e}**')
                    SURVEY_DATA = {}
                # --------------------
                if 'SURVEY_NAME' not in st.session_state['APP']['SURVEY']:
                    st.session_state['APP']['SURVEY']['SURVEY_NAME'] = SURVEY_NAME
                # --------------------

        
        with col2:
            STATIONS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'STATIONS')
            if os.path.isdir(STATIONS_DIRPATH):
                STATIONS_AVAILABLE = get_available_stations(STATIONS_DIRPATH=STATIONS_DIRPATH)
            else:
                STATIONS_AVAILABLE = {}
            
            
            # ---------
            show_survey_summary(STATIONS=STATIONS_AVAILABLE)
            # ------ 
            if len(STATIONS_AVAILABLE)==0:
                st.warning('**:red[Survey with no stations]**. Use the **Stations data editor** to add stations data and station video names to the survey. **Refresh the app and try again.**')

            else:                
                STATION_NAME = st.selectbox(
                    label='**Available station(s):**', 
                    options=STATIONS_AVAILABLE.keys(), 
                    #index=0,
                    key='station_selector',
                    help='Select a station for benthic interpretation.',
                    format_func=lambda x: f'{x} {suffix}' if 'FRAMES' in SURVEY_DATA.get('BENTHOS_INTERPRETATION', {}).get(x, {}) else x,
                )
        
       
                
        """
        with col3:
            if VIDEOS_DIRPATH is not None and os.path.exists(VIDEOS_DIRPATH):
                AVAILABLE_VIDEOS =  get_available_videos(
                    SURVEY_DATA = SURVEY_DATA,
                    STATION_NAME=STATION_NAME, 
                    VIDEOS_DIRPATH = VIDEOS_DIRPATH, 
                    videos_file_extension = '.mp4')

                if len(SURVEY_DATA.get['BENTHOS_INTERPRETATION'].get(STATION_NAME, {})) >0:
                    has_random_frames = 'RANDOM_FRAMES' in STATION_BENTHOS_INTERPRETATION
                    st.session_state['has_random_frames'] = has_random_frames
                else:
                    has_random_frames = False
                    st.session_state['has_random_frames'] = False
                
                _VIDEO_NAME = STATION_BENTHOS_INTERPRETATION.get('VIDEO_NAME', None)

                if AVAILABLE_VIDEOS is not None and len(AVAILABLE_VIDEOS)>0:
                    has_local_videos = True

                    VIDEO_NAME = st.selectbox(
                        '**Available video(s):**',
                        options=sorted(AVAILABLE_VIDEOS),
                        help='Select a video to extract frames from. **:red[If not videos are available]**, **:green[please add videos to the VIDEOS folder]**. Refresh the app and try again.',
                        key='video_selectbox',
                        format_func= lambda x: f'{x} {suffix}' if has_random_frames and x==_VIDEO_NAME else x)

                else:
                    AVAILABLE_VIDEOS = None
                    VIDEO_NAME = None
                    has_local_videos = False
                    st.warning('**:red[No videos available]**. Add the relevant videos in the survey **VIDEOS** folder. Refresh the app and try again.')
            else:
                st.error('**VIDEOS DIRPATH does not exist!**. Ensure the VIDEOS_DIRPATH exist and have writing access to the directory. Refresh the app and try again.')
                LOCAL_VIDEOS = None
                AVAILABLE_VIDEOS = None
                has_local_videos = False
            """            
        with col4:
            message_col4 = st.empty()
        """
        # --------------------------
        if has_random_frames and has_local_videos:
            message_col4.success(f'**`{suffix}`** | has random frames extracted')
            show_random_frames(
                has_random_frames= has_random_frames,
                SURVEY_DATASTORE=SURVEY_DATASTORE,
                SURVEY_DATA=SURVEY_DATA,
                SURVEY_NAME=SURVEY_NAME,
                SURVEY_FILEPATH=SURVEY_FILEPATH,
                STATION_NAME=STATION_NAME,
                VIDEO_NAME=VIDEO_NAME,
                codec = st.session_state.get('codec', None)) 
        """
        LOCAL_VIDEOS =  get_files_dictionary(VIDEOS_DIRPATH, file_extension='.mp4')

        if  len(SURVEY_DATA['VIDEOS'])>0 and len(SURVEY_DATA['STATIONS'])>0 and not has_random_frames:
            show_video_processing(
                SURVEY_NAME= SURVEY_NAME,
                STATION_NAME=STATION_NAME,
                VIDEO_NAME=VIDEO_NAME,
                LOCAL_VIDEOS=LOCAL_VIDEOS,
                SURVEY_DATA=SURVEY_DATA,
                SURVEY_FILEPATH=SURVEY_FILEPATH,
                SURVEY_DATASTORE=SURVEY_DATASTORE,
                SURVEY_DIRPATH=SURVEY_DIRPATH,
                STATION_DIRPATH=STATION_DIRPATH,
                VIDEOS_DIRPATH=VIDEOS_DIRPATH
                )

        IS_SURVEY_DATA_AVAILABLE = survey_data_editor(SURVEY_DATA, SURVEY_DATASTORE)
            # --------------------
        
    else:
        st.warning('**No previous surveys available**. Create a new survey using the **Survey data management** sidebar menu. Refresh the app and try again.')
        has_local_videos = False       
        has_random_frames = False


try:
    build_header()
    SURVEY_NAME = None
    SURVEYS_AVAILABLE = None
    SURVEY_DATASTORE = None
    SURVEY_DATA = None
    STATIONS_AVAILABLE = None
    VIDEOS_AVAILABLE = None
    STATION_NAME = None
    STATION_FILEPATH = None
    show_stations_data_editor = False


    col1, col2, col3 = st.columns([1,1,1])

    with col1:
        SURVEYS_AVAILABLE = get_available_surveys()
        if SURVEYS_AVAILABLE is not None and len(SURVEYS_AVAILABLE)>0:
            SURVEY_NAME, SURVEY_FILEPATH = survey_selector_box(
                SURVEYS_AVAILABLE, 
                index=0,
                format_func=lambda x: f'{x}')

            try:
                # DATASTORE is initialized here
                SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)
                SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data.get('APP', {})
            except Exception as e:
                st.error(f'An error ocurred loading the survey data. Check the **<survey_file.yaml>** is not empty. If empty, please delete the file and its subdirectory and start a new survey. **{e}**')
                SURVEY_DATA = {}
            # --------------------
        else:
            st.warning('**No surveys available**. Create a new survey using the **Survey data management** sidebar menu.')
    
    with col2:            
        if SURVEY_NAME is not None:
            SURVEY_DIRPATH = os.path.dirname(SURVEY_FILEPATH)
            STATIONS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'STATIONS')
            if os.path.isdir(STATIONS_DIRPATH):
                STATIONS_AVAILABLE = get_available_stations(STATIONS_DIRPATH=STATIONS_DIRPATH)
            else:
                create_new_directory(STATIONS_DIRPATH)
                STATIONS_AVAILABLE = {}
            
            if STATIONS_AVAILABLE is not None and len(STATIONS_AVAILABLE)>0:
                show_survey_summary(STATIONS=STATIONS_AVAILABLE)

                STATION_NAME, STATION_FILEPATH = stations_selector_box(
                    STATIONS_AVAILABLE, 
                    index=0,
                    format_func=lambda x:f'{x}')
            else:
                st.warning('**:red[Survey with no stations]**. Use the **Stations data editor** to add stations data and station video names to the survey. **Refresh the app and try again.**')
                show_stations_data_editor = True
    
    with col3:
        st.write(STATION_NAME, STATION_FILEPATH)
    
    # ----
    st.write(SURVEY_DATA)

    
    
    
    #run()

except Exception as e:
    trace_error = traceback.print_exc()
    if trace_error is None:
        trace_error= ''
    else:        
        st.error(f'**Survey initializaton exception:** {trace_error} {e} | **Refresh the app and try again**')