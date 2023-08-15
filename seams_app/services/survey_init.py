import os
import streamlit as st
import pandas as pd
from bgstools.io import load_yaml, get_files_dictionary, create_new_directory, is_directory_empty, delete_directory_contents, extract_frames, select_random_frames
from bgstools.utils import colnames_dtype_mapping, get_nested_dict_value
from bgstools.datastorage import DataStore, YamlStorage
from bgstools.io.media import get_video_info, convert_codec
from bgstools.stt import display_image_carousel
import traceback


def show_survey_summary(STATIONS:dict):
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
    CONFIG_DIRPATH = st.session_state['APP']['CONFIG']['CONFIG_DIRPATH']
    STATION_CORE_COLUMNS_DTYPES = load_yaml(os.path.join(CONFIG_DIRPATH, FILENAME))
    station_colnames_mapping = colnames_dtype_mapping(STATION_CORE_COLUMNS_DTYPES)
    return station_colnames_mapping


def create_videos_dataframe():
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
    CONFIG_DIRPATH = st.session_state['APP']['CONFIG']['CONFIG_DIRPATH']
    DTYPES = st.session_state['APP']['CONFIG']['DTYPES']
    STATION_MEASUREMENT_COLUMNS_DTYPES = load_yaml(os.path.join(CONFIG_DIRPATH, DTYPES['STATION_MEASUREMENT_COLUMNS_DTYPES']))
    dtype_mapping= colnames_dtype_mapping(STATION_MEASUREMENT_COLUMNS_DTYPES)
    return dtype_mapping


def error_callback(error:str):
    st.error(error)


def get_videos_per_station(
        videos_df: pd.DataFrame, 
        linking_key:str = 'siteName', 
        subset_col: str = 'fileName',  
        callback: callable = error_callback) -> dict:
    _videos = {}
    if 'SELECTED' not in videos_df.columns:
        videos_df['SELECTED'] = False
    for siteName, subset in videos_df.groupby(linking_key):
        _videos[siteName] = dict(zip(subset[subset_col], subset['SELECTED']))       
    return _videos


def create_data_editor(df:pd.DataFrame, key:str):
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
    if A == B:
        return set()  # Return an empty set if sets A and B are equal
    else:
        return A - B  # Return the difference between sets A and B


def build_survey_stations(SURVEY_NAME:str = None, stations_dict:dict = None):

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
    if SURVEY_NAME is not None:
        videos_df = create_videos_dataframe()
        if videos_df is not None:
            return videos_df  


def build_header():
    st.title("SEAMS-App | survey initialization")
    st.sidebar.title("SEAMS-App | survey initialization")



def flatten_and_create_dataframe(input_dict, columns = ["siteName", "fileName", "SELECTED"]):
    flattened_data = []
    for site_name, files_info in input_dict.items():
        for file_name, selected_value in files_info.items():
            selected = selected_value if selected_value is not None else False
            flattened_data.append((site_name, file_name, selected))
    
    df = pd.DataFrame(flattened_data, columns=columns)
    return df

def partially_reset_session(keep_keys: list = ['CONFIG', 'SURVEY']):
    APP_KEYS = st.session_state['APP'].keys()

    for key in APP_KEYS:
        if key not in keep_keys:
            st.session_state['APP'][key] = {}


def find_yaml_files(directory):
    """
    This function walks through a directory and its subdirectories to find all YAML files.
    
    Parameters:
    directory (str): The directory to search for YAML files.
    
    Returns:
    dict: A dictionary where the keys are the filenames and the values are the paths to the files.
    
    Raises:
    FileNotFoundError: If the specified directory does not exist.
    """
    # Check if the directory exists
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"The directory {directory} does not exist.")
        
    yaml_files = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".yaml"):
                yaml_files[file] = os.path.join(root, file)
    return yaml_files


def process_yaml_files(yaml_files):
    """
    Process each YAML file in the dictionary to extract specific information.

    Parameters:
    yaml_files (dict): Dictionary of YAML files with filenames as keys and file paths as values.

    Returns:
    dict: A dictionary with additional keys added to each YAML file entry.
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




def get_SURVEYS_AVAILABLE(surveys_dirpath:str):
    """
    This function finds all YAML files in the specified directory and its subdirectories, 
    and returns a dictionary with survey names as keys and their corresponding filepaths as values.

    Parameters:
    surveys_dirpath (str): The directory to search for YAML files.

    Returns:
    dict: A dictionary where the keys are the names of the surveys (filename without extension) 
    and the values are the paths to the corresponding YAML files.

    Notes:
    This function assumes that the 'find_yaml_files' function exists and is capable of finding all YAML 
    files in a given directory and its subdirectories.
    """
    YAML_FILES_AVAILABLE =  find_yaml_files(surveys_dirpath)

    SURVEYS_AVAILABLE = {}
    if YAML_FILES_AVAILABLE is not None and len(YAML_FILES_AVAILABLE)>0:
        for filename, filepath in YAML_FILES_AVAILABLE.items():
            ## SURVEY_NAME == filename_without_extension
            SURVEY_NAME = os.path.splitext(filename)[0]
            SURVEYS_AVAILABLE[SURVEY_NAME] = filepath
    
    if len(SURVEYS_AVAILABLE)>0:
        return SURVEYS_AVAILABLE


st.cache_data()
def load_datastore(survey_filepath:str):
    """
    This function loads the data from a YAML file into a DataStore object.

    Parameters:
    survey_filepath (str): The path to the YAML file.

    Returns:
    DataStore: A DataStore object with the data from the YAML file.

    Raises:
    FileNotFoundError: If the specified file does not exist.
    ValueError: If the file cannot be loaded into a DataStore object.
    """
    if not os.path.isfile(survey_filepath):
        st.warning('**No survey data available**. GO to **MENU>Survey initialization** create a new survey using the **Survey data management** menu. Refresh the app and try again.')
        raise FileNotFoundError(f"The file `{survey_filepath}` does not exist.")
        
        
    try:
        datastore = DataStore(YamlStorage(file_path=survey_filepath))
    except Exception as e:
        raise ValueError(f"Failed to load data from {survey_filepath}: {str(e)}")
        
    return datastore


def get_survey_selected(SURVEYS_AVAILABLE:dict)->tuple:
    """
    This function creates a selectbox widget for choosing a survey, using the Streamlit library.

    Parameters:
    SURVEYS_AVAILABLE (dict): A dictionary with survey names as keys and their corresponding filepaths as values.

    Returns:
    tuple: A tuple containing the name of the selected survey, the filepath of the selected survey. 
   
    The function will return None if there are no surveys available.

    
    """
    if SURVEYS_AVAILABLE is not None and len(SURVEYS_AVAILABLE)>0:
        SURVEY_NAME = st.selectbox(
            label='**Available survey(s):**', 
            options=sorted(list(SURVEYS_AVAILABLE.keys())), 
            index=0,
            key='survey_selector',
            help='Select a benthic interpretation survey.',
            )
        
        SURVEY_FILEPATH = SURVEYS_AVAILABLE[SURVEY_NAME]
        

        return SURVEY_NAME, SURVEY_FILEPATH
    else:
        return None


def show_random_frames(
        has_random_frames:bool, 
        SURVEY_DATASTORE:DataStore, 
        SURVEY_DATA:dict, 
        STATION_NAME:str, 
        codec:str = None):
    if has_random_frames:
        FRAMES = SURVEY_DATA['BENTHOS_INTERPRETATION'].get(STATION_NAME, {}).get('FRAMES', None)
        # Aqui esta el error
        RANDOM_FRAMES = SURVEY_DATA['BENTHOS_INTERPRETATION'].get(STATION_NAME, {}).get('RANDOM_FRAMES', None)
        st.session_state['RANDOM_FRAMES_IDS'] = RANDOM_FRAMES.keys()
        _VIDEO_NAME = SURVEY_DATA['BENTHOS_INTERPRETATION'].get(STATION_NAME, {}).get('VIDEO_NAME', None)            
        if _VIDEO_NAME == VIDEO_NAME and RANDOM_FRAMES is not None and len(RANDOM_FRAMES)>0:
            show_station_is_ready = True
            is_ready_for_interpretation = False
            with st.expander('**Intructions**', expanded=True):
                instructions = """
                    **Step 1:** Utilize the **preview frame** as the starting point for selecting random frames.
                    **Step 2:** Refine the automatic selection process of random frames as needed to ensure a total of 10 frames are chosen.
                    **Step 3:** Verify the accuracy of the selected frames by checking the **:green[ready for interpretation]** status.
                    **Step 4:** Adjust the frames in the **random frames selector** if necessary, while maintaining a total of 10 selected frames.
                    **Step 5:** Take note that selected frames will be marked in the **random frames selector** with a :star: prefix for the frame number and a :white_check_mark: suffix for the extracted second of the video, indicating their selection.
                """
                st.info(instructions)
            with st.expander('**Random frames available**', expanded=True):
               
                fco1, fcol4 = st.columns([3,1])
                with fco1:
                    RANDOM_FRAMES_IDS = st.multiselect(
                    label='**random frames:**',
                        options=FRAMES.keys(),
                        default=sorted(st.session_state.get('RANDOM_FRAMES_IDS', None)), 
                        max_selections=10,
                        help='Select 10 random frames for interpretation.',                        
                        )
                    st.session_state['RANDOM_FRAMES_IDS'] = RANDOM_FRAMES_IDS
                    if len(RANDOM_FRAMES_IDS) < 10:
                        st.warning(f'Less than 10 frames selected. Requirement is 10 frames. Select {10-len(RANDOM_FRAMES_IDS)} more frame(s).')
                        show_station_is_ready = False
                        # -----
                        if 'CURRENT' in st.session_state:
                            st.session_state.pop('CURRENT')
                        # -----
                    elif len(RANDOM_FRAMES_IDS) > 10:
                        st.warning('More than 10 frames selected. Requirement is 10 frames')
                        show_station_is_ready = False

                        if 'CURRENT' in st.session_state:
                            st.session_state.pop('CURRENT')

                    else:
                        show_station_is_ready = True
                        RANDOM_FRAMES = {k: {
                            'FILEPATH': FRAMES[k],
                            'INTERPRETATION': {
                                'DOTPOINTS': {}, 
                                'STATUS': "NOT_STARTED"
                            }, 
                            } for k in RANDOM_FRAMES_IDS}
                        
                        SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES'] = RANDOM_FRAMES
                        
                        st.session_state.update({
                                'CURRENT': {
                                    'SURVEY_NAME': SURVEY_NAME, 
                                    'STATION_NAME': STATION_NAME,
                                    'VIDEO_NAME': VIDEO_NAME,
                                    'SURVEY_FILEPATH': SURVEY_FILEPATH,                                    
                                    }})

                        
                with fcol4:
                    if show_station_is_ready:
                        st.markdown(f'# total : :green[{len(RANDOM_FRAMES_IDS)}] / 10')
                        is_ready = st.button(
                            '**ready for interpretation**', 
                            help=f'Selected **{STATION_NAME}** is **:green[ready for interpretation]**. Click to save data, then Go to **MENU > Benthos interpretation** to start the interpretation workflow.')
                        if is_ready:
                            is_ready_for_interpretation = True
                            SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['IS_READY'] = is_ready_for_interpretation
                            SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})
                            st.toast('go to **MENU > Benthos interpretation**')
                                                 
                    else:
                        st.subheader(f'**number of random frames:**')
                        st.markdown(f'# total : :red[{len(RANDOM_FRAMES_IDS)}] / 10')
                        
                        show_station_is_ready = False
                
                # --------------------
                display_image_carousel(FRAMES, list(RANDOM_FRAMES.keys()))
        else:
            if  codec is not None and codec == 'h264':
                # FUTURE DEVS: Separate the logic for the random frames from the video codec.
                st.warning(f'**No random frames available** for selected video or random frames available with in video with sufix: :blue[{suffix}]. Attempting automatic generation of random frames.  Refresh the app and try again.')
                RANDOM_FRAMES = select_random_frames(frames=FRAMES, num_frames=10)
                
                if RANDOM_FRAMES is not None and len(RANDOM_FRAMES)==10:
                    SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES'] = RANDOM_FRAMES                    
                    #SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})
                    display_image_carousel(FRAMES, list(RANDOM_FRAMES.keys()))
            else:
                st.warning(f'**Random frames available** for other video in the station. Select video with sufix: :blue[{suffix}]. Refresh the app and try again.') 

st.cache_data()
def show_video_player(video_player: st.empty, LOCAL_VIDEO_FILEPATH:str, START_TIME_IN_SECONDS:int = 0):
    video_player.video(LOCAL_VIDEO_FILEPATH, 
                       start_time=START_TIME_IN_SECONDS if START_TIME_IN_SECONDS is not None else 0) 


def survey_data_editor(SURVEY_DATA:dict, SURVEY_DATASTORE:DataStore)->bool:
    if SURVEY_DATA is not None and len(SURVEY_DATA)>0:
        SURVEY_NAME= SURVEY_DATA.get('SURVEY', None).get('SURVEY_NAME', None)
        _STATIONS = SURVEY_DATA.get('STATIONS', {})
        _VIDEOS = SURVEY_DATA.get('VIDEOS', {})


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
        SURVEY_DATA['STATIONS'] = STATIONS
    
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
        SURVEY_DATA['VIDEOS'] = VIDEOS

  
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
            SURVEY_DATA['REPORTS'].update(REPORT)

            if STATIONS_WITHOUT_VIDEOS is not None and  len(STATIONS_WITHOUT_VIDEOS)>0:
                st.warning(f'**Stations without videos:** {STATIONS_WITHOUT_VIDEOS}')
        
        # --------------------
        save_stations_btn = st.button('save survey data & continue', key=f'save_survey_data')
        if save_stations_btn:
            with st.spinner('Saving survey data...'):
                try:
                    SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})                    
                except Exception as e:
                    st.error(f'**An exception ocurred saving the survey data:** {e}')                   
                else:        
                    st.success('Data saved. **Refresh the app and continue**.')
                     
        else:
            st.info('**Do not forget to save the survey data when you are done editing.**')

        if len(STATIONS)>0 and len(VIDEOS)>0:
            IS_SURVEY_DATA_AVAILABLE = True
        else:
            IS_SURVEY_DATA_AVAILABLE = False

        return IS_SURVEY_DATA_AVAILABLE
        # --------------------


def show_video_processing(
        SURVEY_NAME:str,
        STATION_NAME:str,
        VIDEO_NAME:str,
        LOCAL_VIDEOS:dict,
        SURVEY_DATA:dict, 
        SURVEY_DATASTORE:DataStore, 
        
        videos_file_extension:str = '.mp4'):
    if SURVEY_DATA is not None and len(SURVEY_DATA)>0:
            
        if LOCAL_VIDEOS is not None and  len(LOCAL_VIDEOS)>0:
            LOCAL_VIDEOS = {f'{k}{videos_file_extension}': v for k, v in LOCAL_VIDEOS.items()}

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
                                        st.experimental_rerun()
                    
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
                                    SURVEY_DATA['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES'] = _RANDOM_FRAMES
                                    #SURVEY_DATASTORE.storage_strategy.data['APP'] = SURVEY_DATA
                                    #SURVEY_DATASTORE.store_data({'APP': SURVEY_DATA})
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


def get_available_videos(SURVEY_DATA:dict, VIDEOS_DIRPATH:str, videos_file_extension:str = '.mp4')->dict:
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

def get_available_stations_with_videos(SURVEY_DATA:dict, VIDEOS_DIRPATH:str, videos_file_extension:str = '.mp4')->dict:
    AVAILABLE_STATIONS_WITH_VIDEOS = {}
    LOCAL_VIDEOS =  get_files_dictionary(VIDEOS_DIRPATH, file_extension=videos_file_extension)
    LOCAL_VIDEOS = {f'{k}{videos_file_extension}': v for k, v in LOCAL_VIDEOS.items()}

    EXPECTED_STATIONS_WITH_VIDEOS = SURVEY_DATA.get('VIDEOS', {})
    
    for station_name, station_videos in EXPECTED_STATIONS_WITH_VIDEOS.items():
        for video_key in station_videos.keys():
            if video_key in LOCAL_VIDEOS:
                AVAILABLE_STATIONS_WITH_VIDEOS[station_name] = True
    
    return AVAILABLE_STATIONS_WITH_VIDEOS        


def station_selector(SURVEY_DIRPATH:str, AVAILABLE_STATIONS_WITH_VIDEOS:dict, suffix:str = '***'):
    STATIONS = SURVEY_DATA.get('STATIONS', {})
    if STATIONS is not None and len(STATIONS)>0 and AVAILABLE_STATIONS_WITH_VIDEOS is not None and len(AVAILABLE_STATIONS_WITH_VIDEOS)>0:
        STATION_NAME = st.selectbox(
            label='**Available station(s):**', 
            options=sorted(AVAILABLE_STATIONS_WITH_VIDEOS), 
            index=0,
            key='station_selector',
            help='Select a station for benthic interpretation.',
            format_func=lambda x: f'{x} {suffix}' if 'FRAMES' in SURVEY_DATA.get('BENTHOS_INTERPRETATION', {}).get(x, {}) else x,
            )
        # --------------------
        st.session_state['STATIONS'] = STATIONS
        # --------------------
        STATION_DIRPATH = os.path.join(SURVEY_DIRPATH, STATION_NAME)
        if STATION_DIRPATH is not None and not os.path.exists(STATION_DIRPATH):
            create_new_directory(dirpath=STATION_DIRPATH)
        return STATION_NAME, STATION_DIRPATH
        
    else:
        STATION_NAME = None
        STATION_DIRPATH = None

        return STATION_NAME, STATION_DIRPATH

       


try:

    build_header()
    
    # --------------------
    SURVEYS_DIRPATH = get_nested_dict_value(st.session_state, ['APP', 'CONFIG', 'SURVEYS_DIRPATH'])
    VIDEOS_DIRPATH = get_nested_dict_value(st.session_state, ['APP', 'CONFIG', 'VIDEOS_DIRPATH'])
    SURVEYS_AVAILABLE = get_SURVEYS_AVAILABLE(SURVEYS_DIRPATH)
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
            SURVEY_SELECTED = get_survey_selected(SURVEYS_AVAILABLE)           
            if SURVEY_SELECTED is not None:
                SURVEY_NAME, SURVEY_FILEPATH = SURVEY_SELECTED
                SURVEY_DIRPATH = os.path.dirname(SURVEY_FILEPATH)
                VIDEOS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'VIDEOS')

                if not os.path.exists(VIDEOS_DIRPATH):
                    create_new_directory(VIDEOS_DIRPATH)
                else:
                    st.session_state['APP']['CONFIG']['VIDEOS_DIRPATH'] = VIDEOS_DIRPATH

                try:
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
            AVAILABLE_STATIONS_WITH_VIDEOS = get_available_stations_with_videos(
                    SURVEY_DATA=SURVEY_DATA, 
                    VIDEOS_DIRPATH=VIDEOS_DIRPATH, 
                    videos_file_extension = '.mp4')
            
            __STATIONS = SURVEY_DATA.get('STATIONS', {})
            # ---------
            show_survey_summary(STATIONS=AVAILABLE_STATIONS_WITH_VIDEOS)
            # ------ 
            if len(__STATIONS)==0:
                st.warning('**:red[Survey with no stations]**. Use the **Stations data editor** to add stations data and station video names to the survey. **Refresh the app and try again.**')

                

            STATION_NAME, STATION_DIRPATH = station_selector(
                SURVEY_DIRPATH=SURVEY_DIRPATH, 
                AVAILABLE_STATIONS_WITH_VIDEOS=AVAILABLE_STATIONS_WITH_VIDEOS)
            STATION_BENTHOS_INTERPRETATION = SURVEY_DATA['BENTHOS_INTERPRETATION'].get(STATION_NAME, {})
                
            
        with col3:
            if VIDEOS_DIRPATH is not None and os.path.exists(VIDEOS_DIRPATH):
                AVAILABLE_VIDEOS =  get_available_videos(
                    SURVEY_DATA = SURVEY_DATA, 
                    VIDEOS_DIRPATH = VIDEOS_DIRPATH, 
                    videos_file_extension = '.mp4')

                if len(SURVEY_DATA['BENTHOS_INTERPRETATION'].get(STATION_NAME, {})) >0:
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
        
        with col4:
            message_col4 = st.empty()
        
        # --------------------------
        if has_random_frames and has_local_videos:
            message_col4.success(f'**`{suffix}`** | has random frames extracted')
            show_random_frames(has_random_frames, SURVEY_DATASTORE, SURVEY_DATA, STATION_NAME, codec = st.session_state.get('codec', None)) 
        
        LOCAL_VIDEOS =  get_files_dictionary(VIDEOS_DIRPATH, file_extension='.mp4')

        if  len(SURVEY_DATA['VIDEOS'])>0 and len(SURVEY_DATA['STATIONS'])>0 and not has_random_frames:
            show_video_processing(
                SURVEY_NAME= SURVEY_NAME,
                STATION_NAME=STATION_NAME,
                VIDEO_NAME=VIDEO_NAME,
                LOCAL_VIDEOS=LOCAL_VIDEOS,
                SURVEY_DATA=SURVEY_DATA,
                SURVEY_DATASTORE=SURVEY_DATASTORE,
                )

        IS_SURVEY_DATA_AVAILABLE = survey_data_editor(SURVEY_DATA, SURVEY_DATASTORE)
            # --------------------
        
    else:
        st.warning('**No previous surveys available**. Create a new survey using the **Survey data management** sidebar menu. Refresh the app and try again.')
        has_local_videos = False       
        has_random_frames = False

            
       
except Exception as e:
    trace_error = traceback.print_exc()
    if trace_error is None:
        trace_error= ''
    else:        
        st.error(f'**Survey initializaton exception:** {trace_error} {e} | **Refresh the app and try again**')