import os


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