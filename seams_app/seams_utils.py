import os
from bgsio import create_new_directory
import yaml
from bgstools.datastorage import DataStore, YamlStorage
import streamlit as st
import hashlib
import datetime


def logarithmic_scale(value, min_power, max_power):
    """
    Converts a linear value to a logarithmic scale.

    :param value: The linear value to be converted (e.g., the slider position).
    :param min_power: The minimum power of 10 in the logarithmic scale.
    :param max_power: The maximum power of 10 in the logarithmic scale.
    :return: The value on a logarithmic scale.
    """
    log_min = np.log10(10 ** min_power)
    log_max = np.log10(10 ** max_power)
    scale = (log_max - log_min) / (max_power - min_power)
    
    return 10 ** (log_min + scale * (value - min_power))


def str_as_dtype(datatype: str, callback: callable = None):
    """
    Converts a string representation of a data type to the corresponding Python data type.

    Args:
        datatype (str): The string representation of the data type.
        callback (callable, optional): A callback function to handle exceptions.

    Returns:
        The corresponding Python data type if `datatype` is a valid type, otherwise None.
        The exception is `datetime` which is returned as a string.

    Raises:
        TypeError: If `datatype` is not a string.
        ValueError: If `datatype` is not a recognized data type.

    Example:
        str_as_dtype('int')  # returns <class 'int'>
        str_as_dtype('bool')  # returns <class 'bool'>
    """
    try:
        if not isinstance(datatype, str):
            raise TypeError("Input 'datatype' must be a string.")

        if datatype == 'str':
            return str
        elif datatype == 'int':
            return int
        elif datatype == 'float':
            return float
        elif datatype == 'bool':
            return bool
        elif datatype == 'datetime':
            return datetime
        else:
            raise ValueError(f"Unrecognized data type: '{datatype}'")

    except Exception as e:
        if callback is not None and callable(callback):
            exception_message = f"**`str_as_dtype` exception occurred:** {e}"
            callback(exception_message)
        else:
            raise


def get_nested_dict_value(data_dict, keys_list, default=None):
    """
    This function retrieves a value from a nested dictionary using a list of keys. 
    If a KeyError is encountered at any level, the function will return a default value.

    Args:
        data_dict (dict): The dictionary from which to retrieve the value.
        keys_list (list): A list of keys, ordered by their level in the dictionary.
        default (any, optional): The default value to return if any key in keys_list is not found. 
            Defaults to None.

    Returns:
        The value at the nested key if it exists, otherwise the default value.
    """
    try:
        for key in keys_list:
            data_dict = data_dict.get(key, None)
        return data_dict
    except KeyError:
        return default
    

def colnames_dtype_mapping(colnames_dtype_dict: dict | list)-> dict:
    """
    Maps column names to their corresponding data types based on the provided dictionary.

    Args:
        colnames_dtype_dict (dict): A dictionary mapping column names to their data types.

    Returns:
        A new dictionary where keys are column names and values are the corresponding data types.

    Raises:
        TypeError: If `colnames_dtype_dict` is not a dictionary.
        ValueError: If `colnames_dtype_dict` is empty or contains invalid data types.

    Example:
        colnames_dtype_mapping({'col1': 'int', 'col2': 'str', 'col3': 'float'})
        # returns {'col1': <class 'int'>, 'col2': <class 'str'>, 'col3': <class 'float'>}
    """
    _colnames_dtype_dict = colnames_dtype_dict
    try:
        if isinstance(colnames_dtype_dict, list):
            for item in colnames_dtype_dict:
                _colnames_dtype_dict = {item['colname']: item['dtype'] for item in colnames_dtype_dict}

        if not isinstance(_colnames_dtype_dict, dict):
            raise TypeError("Input 'colnames_dtype_dict' must be a dictionary.")

        if not _colnames_dtype_dict:
            raise ValueError("Input 'colnames_dtype_dict' cannot be empty.")

        mapping = {}
        for colname, dtype in _colnames_dtype_dict.items():
            mapping[colname] = str_as_dtype(dtype)

        return mapping

    except (TypeError, ValueError) as e:
        # Handle the exception or re-raise it
        raise e


def toggle_button(on_sidebar=False, *args, key=None, **kwargs):
    """
    Creates a toggle button that retains its state across reruns of the script.

    The state of the button (pressed/unpressed) is stored in the Streamlit session state
    and is associated with a unique key.

    Parameters:
    *args: The arguments to pass to the Streamlit button function.
    key (str, optional): A unique key for the button. If not provided, a key is generated
        based on the args and kwargs.
    **kwargs: The keyword arguments to pass to the Streamlit button function.

    Returns:
    bool: The current state of the button (True for pressed, False for unpressed).
    """

    # Generate a key from the args and kwargs if none was provided.
    if key is None:
        key = hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()

    try:
        # Set the initial state of the button if it doesn't exist.
        if key not in st.session_state:
            st.session_state[key] = False

        # Set the button type based on the state.
        if "type" not in kwargs:
            kwargs["type"] = "primary" if st.session_state[key] else "secondary"
        
        if on_sidebar:
            # Toggle the state of the button if it's pressed.
            if st.sidebar.button(*args, **kwargs):
                st.session_state[key] = not st.session_state[key]
                st.rerun()
        else:
            # Toggle the state of the button if it's pressed.
            if st.button(*args, **kwargs):
                st.session_state[key] = not st.session_state[key]
                st.rerun()


    except Exception as e:
        st.error(f"Error occurred: {e}")

    return st.session_state[key]


def find_first_level_yaml_files(directory):
    """
    Search for all YAML files within the first-level subdirectories of a specified directory.

    This function will traverse the immediate children of the provided directory. 
    It will look for files with a '.yaml' extension and compile a dictionary of their names 
    and absolute paths. If the directory does not exist, a FileNotFoundError will be raised.

    Parameters:
    - directory (str): The main directory from which to start the search.

    Returns:
    - dict: A dictionary with:
        - keys: filenames of the discovered YAML files.
        - values: absolute paths to those YAML files.

    Raises:
    - FileNotFoundError: If the specified directory does not exist or is not accessible.

    Dependencies:
    - Requires the os module for directory listing and path manipulation.

    Example Usage:
    >>> find_first_level_yaml_files('/path/to/directory')
    {
        'config.yaml': '/path/to/directory/subdir1/config.yaml',
        ...
    }

    Notes:
    - This function only considers the first level of directories inside the given directory.
    - Files with extensions other than '.yaml' are not included in the results.
    - An exception is raised immediately if the directory does not exist, avoiding further execution with invalid paths.
    """

    # Check if the directory exists to prevent searching in a non-existent location
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"The directory {directory} does not exist.")

    # Initialize a dictionary to store the YAML file names and their paths
    yaml_files = {}
    
    # Iterate over each item in the directory
    for subdir in os.listdir(directory):
        subdir_path = os.path.join(directory, subdir)  # Form the full path to the item
        
        # Proceed only if the item is a directory
        if os.path.isdir(subdir_path):
            
            # Iterate over each file in the first-level subdirectory
            for file in os.listdir(subdir_path):
                # Check if the file ends with the .yaml extension
                if file.endswith(".yaml"):
                    # Add the file and its absolute path to the dictionary
                    yaml_files[file] = os.path.join(subdir_path, file)

    # Return the dictionary containing YAML file names and paths
    return yaml_files


def get_surveys_available(surveys_dirpath:str):
    """
    Retrieve a dictionary of available surveys in a specified directory and its subdirectories by finding all YAML files.

    Parameters:
    - surveys_dirpath (str): The directory path where the search for YAML survey files should begin.

    """

  
    YAML_FILES_AVAILABLE =  find_first_level_yaml_files(surveys_dirpath)

    SURVEYS_AVAILABLE = {}
    if YAML_FILES_AVAILABLE is not None and len(YAML_FILES_AVAILABLE)>0:
        for filename, filepath in YAML_FILES_AVAILABLE.items():
            SURVEY_NAME = os.path.splitext(filename)[0]
            SURVEYS_AVAILABLE[SURVEY_NAME] = filepath
    
    if len(SURVEYS_AVAILABLE)>0:
        return SURVEYS_AVAILABLE
    

def get_stations_available(SURVEY_FILEPATH:str)->dict:
    """
    """
    STATIONS_AVAILABLE = {}
    if os.path.isfile(SURVEY_FILEPATH):
        SURVEY_DIRPATH = os.path.dirname(SURVEY_FILEPATH)
        STATIONS_DIRPATH = os.path.join(SURVEY_DIRPATH, 'STATIONS')
        if os.path.isdir(STATIONS_DIRPATH):
            stations = find_first_level_yaml_files(STATIONS_DIRPATH)
            # using only name of file without extension as key
            STATIONS_AVAILABLE = {os.path.splitext(filename)[0]: stations[filename] for filename in stations}
        else:
            create_new_directory(STATIONS_DIRPATH)
        
    return STATIONS_AVAILABLE
            
            
        
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

def update_station_data(STATION_DATA:dict, STATION_FILEPATH:str):
    # Save the station data to a file.
     with open(STATION_FILEPATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(STATION_DATA, f, allow_unicode=True)


def update_yaml_data(DATA:dict, YAML_FILEPATH:str):
    try:            
        with open(YAML_FILEPATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump(DATA, f, allow_unicode=True)
    except IOError as e:        
        print(e)



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
        st.warning('**No survey data available**. GO to **MENU>Survey initialization** create a new survey using the **Survey data management** menu.Refresh the browser window and try again.')
        raise FileNotFoundError(f"The file `{survey_filepath}` does not exist.")
  
    try:
        datastore = DataStore(YamlStorage(file_path=survey_filepath))
    except Exception as e:
        raise ValueError(f"Failed to load data from {survey_filepath}: {str(e)}")
        
    return datastore


def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"File '{file_path}' has been deleted.")
    except OSError as e:
        print(f"Error: {e}")