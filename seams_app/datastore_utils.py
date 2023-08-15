import streamlit as st
from bgstools.datastorage import DataStore, YamlStorage


def get_DATASTORE()->DataStore:
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
        
