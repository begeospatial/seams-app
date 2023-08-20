import streamlit as st
from bgstools.datastorage import DataStore, YamlStorage


def get_DATASTORE()->DataStore:
    """
    Retrieves the DataStore instance from the Streamlit session state.

    Functionality:
    --------------
    1. Checks if 'SURVEY_DATASTORE' is available in the Streamlit session state.
       If present, returns this DataStore instance.
    2. If 'SURVEY_DATASTORE' is not present in the session state, the function 
       attempts to initialize a new DataStore instance using the 'SURVEY_FILEPATH' 
       from the session state. 
    3. If the 'SURVEY_FILEPATH' is available and valid, initializes a DataStore instance 
       with YamlStorage based on this filepath, updates the session state with this 
       new DataStore instance, and returns it.
    4. If 'SURVEY_FILEPATH' is not found or invalid, returns None.

    Returns:
    -------
    DataStore:
        An instance of the DataStore class representing the survey data, or None if 
        'SURVEY_FILEPATH' is not available or valid.

    Notes:
    -----
    - The function is designed for integration within a Streamlit application.
    - It is assumed that the DataStore class and YamlStorage class are defined elsewhere 
      in the codebase and are used to manage and persist survey data.
    """
    if 'SURVEY_DATASTORE' in st.session_state:
        return st.session_state['SURVEY_DATASTORE']
    else:
        SURVEY_FILEPATH = st.session_state.get('APP', {}).get('SURVEY', {}).get('SURVEY_FILEPATH', None)
        if SURVEY_FILEPATH is not None:                
            SURVEY_DATASTORE = DataStore(YamlStorage(file_path=SURVEY_FILEPATH))
            st.session_state['SURVEY_DATASTORE'] = SURVEY_DATASTORE
            return SURVEY_DATASTORE
        else:
            return None

def update_DATASTORE(data: dict, callback_message:callable = None)->DataStore:
    """
    Updates the stored survey data in the DataStore instance with new data.

    Parameters:
    -----------
    data : dict
        Dictionary containing the new data to be updated in the DataStore.

    callback_message : callable, optional
        A callback function to handle messages or errors during the update process. 
        The function should take a string as a parameter. If not provided, error 
        messages will not be displayed.

    Functionality:
    --------------
    1. Checks if the provided data is valid.
    2. If 'SURVEY_DATASTORE' is available in the Streamlit session state, the function 
       retrieves the current stored data, updates it with the new data, and then 
       persists this updated data.
    3. If 'SURVEY_DATASTORE' is not present in the session state, the function 
       initializes a new DataStore instance using the get_DATASTORE() function. It then 
       retrieves the current stored data, updates it with the new data, and persists 
       the updated data.
    4. If the provided data is invalid, and the callback_message function is provided, 
       an error message is sent to the callback.

    Returns:
    -------
    DataStore:
        An instance of the DataStore class representing the updated survey data. If 
        the provided data is invalid, returns None.

    Notes:
    -----
    - The function is designed for integration within a Streamlit application.
    - It is assumed that the DataStore class and its associated storage strategy are 
      defined elsewhere in the codebase and are used to manage and persist survey data.
    """
   
    if data is not None and isinstance(data, dict):                
        if 'SURVEY_DATASTORE' in st.session_state:
            _data = st.session_state['SURVEY_DATASTORE'].storage_strategy.data
            _data.update(data)
            st.session_state['SURVEY_DATASTORE'].storage_strategy.data = _data
            st.session_state['SURVEY_DATASTORE'].store_data(data=_data)
            return _data
        else:        
                SURVEY_DATASTORE = get_DATASTORE()                
                _data = SURVEY_DATASTORE.storage_strategy.data
                _data.update(data)
                SURVEY_DATASTORE.storage_strategy.data = _data
                SURVEY_DATASTORE.store_data(data=_data)
                st.session_state['SURVEY_DATASTORE'] = SURVEY_DATASTORE
                return SURVEY_DATASTORE
    else:
        if callback_message is not None:
            callback_message('update_DATASTORE: **data** is not defined or is not a dictionary.')
        return None                
        
