import os
import streamlit as st
import shutil
from bgsio import get_available_services, create_directory_list, check_directory_exist_and_writable, path_exists
from bgstools.stt import build_activities_menu
from bgsio import load_toml_variables, create_subdirectory, create_new_directory
from bgstools.datastorage import DataStore, YamlStorage
from seams_utils import update_station_data

# --------------------
st.set_page_config(
    layout='wide',
    page_title='SEAMS-App',
    page_icon=':oyster:',
    initial_sidebar_state='expanded',
    )

def get_script_path():
    """
    Retrieves the directory path of the currently executing script.

    Returns:
    str: The absolute directory path of the current script.
    
    Note:
    This function makes use of the `os.path` module to get the directory of the script in which it resides. 
    This can be useful for relative file operations or when the script's directory serves as a reference point.
    """
    return os.path.dirname(os.path.realpath(__file__))


def init_session_state(default_data_subdirectory_name:str ='data', reset_session_state:bool = False):
    """
    Initializes and populates the Streamlit session state for managing application state across interactions. 
    This function ensures that specific keys are present in the session state.

    Parameters:
    - default_data_subdirectory_name (str, optional): Name of the default subdirectory where the data resides. 
      Defaults to 'data'.
    - reset_session_state (bool, optional): If True, the session state will be reset. Defaults to False.

    Returns:
    bool: True if initialization was successful and all required directories and files were found, otherwise False.

    Note:
    This function is mainly used at the start of the application to ensure a consistent state, 
    and is crucial for managing how data is handled and displayed throughout the application.
    """
    if 'APP' not in st.session_state or reset_session_state:
        st.session_state['APP'] = {}
    if 'CONFIG' not in st.session_state['APP']:
        st.session_state['APP']['CONFIG'] = {}    
    if 'SURVEY' not in st.session_state['APP']:
        st.session_state['APP']['SURVEY'] = {}
    if 'SURVEYS_AVAILABLE' not in st.session_state:
        st.session_state['SURVEYS_AVAILABLE'] = {}    
    if 'STATIONS' not in st.session_state['APP']:
        st.session_state['APP']['STATIONS'] = {}
    if 'VIDEOS' not in st.session_state['APP']:
        st.session_state['APP']['VIDEOS'] = {}
    if 'SUBSTRATES' not in st.session_state['APP']:
        st.session_state['APP']['SUBSTRATES'] = {}
    if 'TAXONS' not in st.session_state['APP']:
        st.session_state['APP']['TAXONS'] = {}        
    if 'REPORTS' not in st.session_state['APP']:
        st.session_state['APP']['REPORTS'] = {}    
    if 'BENTHOS_INTERPRETATION' not in st.session_state['APP']:
        st.session_state['APP']['BENTHOS_INTERPRETATION'] = {}

    # --------------------
    APP_DIRPATH = get_script_path()
    LOGOS_DIRPATH = os.path.join(APP_DIRPATH,'static', 'logos')
    st.session_state['LOGOS_DIRPATH'] = LOGOS_DIRPATH

    DATA_DIRPATH =  os.path.join(APP_DIRPATH, default_data_subdirectory_name)
    if check_directory_exist_and_writable(DATA_DIRPATH):
        st.session_state['APP']['CONFIG']['DATA_DIRPATH'] = DATA_DIRPATH
    else:
        st.error(f'**{DATA_DIRPATH}** does not exist or is not writable.')
        return False
    
    SURVEYS_DIRPATH = create_subdirectory(DATA_DIRPATH, 'SURVEYS')
    if SURVEYS_DIRPATH:
        st.session_state['APP']['CONFIG']['SURVEYS_DIRPATH'] = SURVEYS_DIRPATH
    # --------------------
    CONFIG_DIRPATH = os.path.join(APP_DIRPATH,'config')
    if path_exists(CONFIG_DIRPATH, 'local'):
        st.session_state['APP']['CONFIG']['CONFIG_DIRPATH'] = CONFIG_DIRPATH
    # Loading paths from config subdirectory
    FILEPATH = os.path.join(CONFIG_DIRPATH,'dtypes.toml')
    filedict = load_toml_variables(FILEPATH)
    if filedict:
        st.session_state['APP']['CONFIG']['DTYPES'] = filedict['DTYPES']
        return True
    else:
        st.error(f'**{FILEPATH}** does not exist or is not readable.')
        return False
   

st.cache_data()
def load_logos():
    """
    Loads logo paths from a TOML configuration file.

    Returns:
    dict: A dictionary containing paths to logos as defined in the TOML file.

    Note:
    The function relies on a configuration file named 'logos.toml' which is expected to be located in 
    the 'config' subdirectory of the main application directory. This TOML file contains paths to various 
    logo images used throughout the application. The function uses caching via `st.cache_data()` to ensure 
    efficient loading of the logos without unnecessary file reads on every invocation.
    """

    CONFIG_DIRPATH = get_script_path()
    LOGOS_FILEPATH = os.path.join(CONFIG_DIRPATH,'config/logos.toml')
    return load_toml_variables(LOGOS_FILEPATH)


def delete_subdirectory_with_confirmation(directory_path: str, btn_label: str = "Delete Subdirectory"):
    """
    Deletes a subdirectory after obtaining a confirmation from the user via the UI.

    Parameters:
    - directory_path (str): The path of the subdirectory to be deleted.
    - btn_label (str, optional): Label of the button that triggers the delete action. Defaults to "Delete Subdirectory".

    Returns:
    bool: True if the directory was successfully deleted, False otherwise.

    Note:
    The function first prompts the user for confirmation to delete the specified directory. Upon receiving 
    confirmation, the directory and its contents are deleted. Messages are displayed to the user to indicate 
    success or failure of the deletion process. Additionally, certain session state variables are reset 
    upon successful deletion.
    """
    if directory_path:
            
        delete_confirmation = st.checkbox(
            "I confirm that I want to delete survey and all its data. This action cannot be undone.", 
            key="delete_confirmation")

        if delete_confirmation==True:
            delete_button = st.button(btn_label, key="delete_button")

            if delete_button:
                try:
                    shutil.rmtree(directory_path)
                    message = f"Subdirectory deleted successfully."
                    st.toast(message)
                    st.success(message)
                    st.session_state['APP']['SURVEY']= {}
                    st.session_state['APP']['STATIONS']= {}
                    st.session_state['APP']['VIDEOS']= {}                    
                    st.session_state.pop('SURVEY_DATASTORE', None)
                    st.cache_data.clear()
                    st.cache_data()
                    st.session_state['CURRENT'] = {}
                    #delete_file(st.session_state.get('CURRENT_FILEPATH', None))
                    update_station_data({}, st.session_state['CURRENT_FILEPATH'])
                    st.rerun()
                except Exception as e:
                    st.error(f"An error occurred while deleting the subdirectory: {e}")
                    return False
        else:
            return False
    else:
        st.info("No previous surveys for deletion.")
        return False


def build_sidebar():
    """
    Constructs the sidebar for the Streamlit application.

    Details:
    The function performs the following main tasks:
    - Loads logos from a predefined path and displays the main logo on the sidebar.
    - Defines paths for the application's services and related directories.
    - Creates an expandable section titled 'SEAMS - PLAN SUBSIM' containing details about the application.
    - Provides a refresh button that clears all data caches and reruns the application.
    - Loads a list of available services (activities) from a specified YAML file and constructs a clickable menu for these services.

    Note:
    The function makes use of various Streamlit functions such as st.sidebar.image(), st.sidebar.expander(), and st.sidebar.button() 
    to generate the sidebar layout. 
    """
    
    logos = load_logos()
    LOGOS_DIRPATH = st.session_state['LOGOS_DIRPATH']
    LOGO_SIDEBAR_URL = os.path.join(LOGOS_DIRPATH, logos['LOGOS']['LOGO_SIDEBAR_URL'])
    LOGO_ODF_URL = os.path.join(LOGOS_DIRPATH, logos['LOGOS']['LOGO_ODF_URL'])
    LOGO_BEGEOSPATIAL = os.path.join(LOGOS_DIRPATH, logos['LOGOS']['LOGO_BEGEOSPATIAL'])

    if LOGO_SIDEBAR_URL: st.sidebar.image(
            LOGO_SIDEBAR_URL, 
            #width=150,
            caption= 'SEafloor Annotation and Mapping Support (SEAMS)'
            )

    # Load the available services
    SERVICES_FILEPATH = os.path.join(get_script_path(),'app_services.yaml')
    SERVICES_DIRPATH = os.path.join(get_script_path(),'services/')
    
    about_sidebar_expander = st.sidebar.expander(label='**SEAMS** - PLAN SUBSIM')
    
    with about_sidebar_expander:
        st.title('SEAMS')
        st.subheader('SEafloor Annotation and Mapping Support')
        st.markdown(
            """ *[PLAN-SUBSIM](https://oceandatafactory.se/plan-subsim/)*
            a national implementation of a PLatform for ANalysis of SUBSea IMages.
            """)
        if LOGO_ODF_URL: st.image(LOGO_ODF_URL)

        with st.container():
            st.divider()       
            st.markdown(""" <div style='text-align:center'> SEAMS-app mantained by:</div>""", unsafe_allow_html=True)
            st.image(LOGO_BEGEOSPATIAL)
    
        
    # Load the yaml with core services as activities    
    core_activities =  get_available_services(
        services_filepath=os.path.abspath(SERVICES_FILEPATH)        
    )
       
    build_activities_menu(
            activities_dict=core_activities, 
            label='**MENU:**', 
            key='activitiesMenu', 
            services_dirpath=os.path.abspath(SERVICES_DIRPATH),
            disabled=False
            )
    # --------------------
   

def get_filename_from_filepath(path: str):
    """
    Extracts the filename from a given file path.

    Parameters:
    - path (str): The full file path from which the filename needs to be extracted.

    Returns:
    - str: The extracted filename from the provided path.

    Examples:
    >>> get_filename_from_filepath("/home/user/documents/file.txt")
    'file.txt'

    >>> get_filename_from_filepath("/home/user/documents/folder/")
    'folder'

    Note:
    The function uses os.path.basename() and os.path.normpath() to extract the filename or the last directory name from the path.
    """
    return os.path.basename(os.path.normpath(path))


def get_dirpath_from_filepath(path: str):
    """
    Extracts the directory path from a given file or directory path.

    Parameters:
    - path (str): The full file or directory path from which the parent directory path needs to be extracted.

    Returns:
    - str: The parent directory path of the provided path.

    Examples:
    >>> get_dirpath_from_filepath("/home/user/documents/file.txt")
    '/home/user/documents'

    >>> get_dirpath_from_filepath("/home/user/documents/folder/")
    '/home/user/documents'

    Note:
    The function uses os.path.dirname() to extract the parent directory path from the given path.
    """
    return os.path.dirname(path)


def new_survey():
    """
    Create a new survey directory and associated files for the user.

    Workflow:
    1. Takes input for the survey name.
    2. Checks for uniqueness and sanitizes the survey name.
    3. Constructs the required directory and file paths for the new survey.
    4. Checks if a survey of the given name already exists.
    5. If not, it creates the necessary directories and files for the new survey.
    6. Initializes the session state with the new survey's details.
    7. Updates the data store with the session state details.
    8. Alerts the user upon successful creation or in case the survey name already exists.

    Streamlit UI Elements:
    - Input: Takes a string input for the survey name.
    - Buttons: 
        1. A form submission button to initiate the survey creation.
    - Feedback: Provides feedback to the user on the status of the creation.
    """
    with st.container():        
        with st.form(key='new_survey_datafile', clear_on_submit=True):
            SURVEY_NAME = st.text_input(
                '**NEW Survey:**', placeholder='survey name', help='**Please, write the `survey_name` replacing spaces with underscore.**')
            if SURVEY_NAME:
                SURVEY_NAME = SURVEY_NAME.strip().replace(' ', '_').replace('.','_')
                
            select_btn = st.form_submit_button(label='Create file')
            if select_btn and SURVEY_NAME:                
                SURVEY_DIRPATH = os.path.join(st.session_state['APP']['CONFIG']['SURVEYS_DIRPATH'], SURVEY_NAME)

                if not path_exists(SURVEY_DIRPATH, 'local'):
                    create_new_directory(SURVEY_DIRPATH)

                    SURVEY_FILEPATH = os.path.join(SURVEY_DIRPATH,f'{SURVEY_NAME}.yaml')
                    
                    if path_exists(SURVEY_DIRPATH, 'local'):
                        VIDEOS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'VIDEOS')
                        if not os.path.exists(VIDEOS_DIRPATH):
                            create_new_directory(VIDEOS_DIRPATH)

                        SELECTED = {                                
                                'SURVEY_DIRPATH': SURVEY_DIRPATH,
                                'SURVEY_NAME': SURVEY_NAME,
                                'SURVEY_FILEPATH': SURVEY_FILEPATH,
                                'VIDEOS_DIRPATH': VIDEOS_DIRPATH,
                                }
                        init_session_state(reset_session_state=True)
                        
                        st.session_state['APP']['SURVEY'].update(SELECTED)

                        data={'APP': st.session_state['APP']}
                        if 'STATION_INDEX' not in data['APP']:
                            data['APP']['STATION_INDEX'] = 0
                        if 'SURVEY_INDEX' not in data['APP']:
                            data['APP']['SURVEY_INDEX'] = 0
                        # --------------------
                        SURVEY_DATASTORE = DataStore(YamlStorage(file_path=SURVEY_FILEPATH))
                        _data = SURVEY_DATASTORE.storage_strategy.data
                        _data.update(data)
                        SURVEY_DATASTORE.storage_strategy.data = _data
                        SURVEY_DATASTORE.store_data(data=data)
                        # --------------------
                        st.session_state['SURVEY_DATASTORE'] = SURVEY_DATASTORE
                        st.session_state['SURVEYS_AVAILABLE'][SURVEY_NAME] = SURVEY_DIRPATH
                        st.session_state.update(_data)                        
                        # --------------------
                        st.toast(f'Survey: **{SURVEY_NAME}**  `SURVEY_DATASTORE` created and initialized')
                        # --------------------                        
                    st.success(f'Survey: **{SURVEY_NAME}** created')
                    st.rerun()                    
                        
                else:

                    st.warning(f'Survey **{SURVEY_NAME}**')                   

def remove_session_state(session_state_keys: list):
    """
    Remove specified keys from the Streamlit session state.

    Parameters:
    - session_state_keys (list): A list of keys to be removed from the session state.

    Notes:
    - If a key from the list is not found in the session state, it is simply ignored.
    - This function is useful for cleaning up or resetting specific parts of the session state without affecting other parts.

    Example:
    ```python
    remove_session_state(['key1', 'key2'])
    ```
    This would attempt to remove 'key1' and 'key2' from the session state.
    """
    for key in session_state_keys:
        if key in st.session_state:
            del st.session_state[key]
                    
def delete_survey():
    """
    Provides a Streamlit UI component for users to select a survey and delete it.

    Process:
    1. Fetches the directory path of available surveys.
    2. Lists available surveys for selection from a dropdown menu.
    3. Upon survey selection, prompts the user for confirmation to delete the selected survey.
    4. Deletes the survey if confirmed.

    Requirements:
    - This function relies on other utility functions like `create_directory_list()` and `delete_subdirectory_with_confirmation()`.
    - Assumes a certain structure in the session state to find available surveys.

    Note:
    - Deletion is permanent and will remove all related data of the selected survey.
    """
    st.divider()
    with st.container():
        SURVEYS_DIRPATH =  st.session_state.get('APP', {}).get('CONFIG', {}).get('SURVEYS_DIRPATH', None)
        if SURVEYS_DIRPATH is not None:
            available_surveys_dirpath = create_directory_list(SURVEYS_DIRPATH)
            options = {os.path.basename(os.path.normpath(survey_dirpath)): survey_dirpath for survey_dirpath in available_surveys_dirpath}
            selected_survey_dirname = st.selectbox(
                label='**DELETE survey :**',
                placeholder='select survey',
                options=options, 
                key='delete_survey_selectbox')
            if selected_survey_dirname:
                delete_subdirectory_with_confirmation(options[selected_survey_dirname], btn_label=f'Delete survey: **{selected_survey_dirname}**')
            
                

def survey_data_management():
    """
    Embeds survey management related activities within an expander in the Streamlit sidebar.

    Features:
    1. Offers an interface to create a new survey via the `new_survey()` function.
    2. Offers an interface to delete existing surveys via the `delete_survey()` function.

    Display:
    - The UI components for both creating and deleting surveys are embedded within separate containers.
    - This function is intended to be a part of the sidebar and provides a user-friendly way to manage surveys.
    """
    with st.sidebar.expander(label='**Survey data management**', expanded=False):
        with st.container():
            new_survey()
        with st.container():
            delete_survey()
        

def run():
    """
    Executes the primary sequence of operations for the Streamlit app.

    Sequence:
    1. Initializes session state variables for the app using `init_session_state()`.
    2. Constructs the sidebar interface with logos, about information, and core activities using `build_sidebar()`.
    3. Enables survey data management functionalities like creating and deleting surveys with `survey_data_management()`.

    Usage:
    - Typically called once when the Streamlit app is run to set up the main components and logic.
    """
    init_session_state()
    build_sidebar()
    survey_data_management()



if __name__ == '__main__':
    run()
else:
    st.error('The app failed initialization. Report issue to mantainers in github')

