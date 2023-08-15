import streamlit as st
from bgstools.datastorage import DataStore, YamlStorage


def run():
    st.title("SEAMS-App | troubleshooter")
    st.sidebar.title("SEAMS-App | troubleshooter")

    if 'SELECTED_SURVEY' in st.session_state:
        st.write(f"**SELECTED_SURVEY:** {st.session_state['SELECTED_SURVEY']}")
        
    if 'SELECTED_SURVEY_FILEPATH' in st.session_state:
        st.write(f"**SELECTED_SURVEY_FILEPATH:** {st.session_state['SELECTED_SURVEY_FILEPATH']}")
        SURVEY_DATASTORE = DataStore(YamlStorage(st.session_state['SELECTED_SURVEY_FILEPATH']))
        SURVEY_DATASTORE.load_data()

        with st.expander('SURVEY_DATASTORE', expanded=False):
            if SURVEY_DATASTORE:
                st.json(SURVEY_DATASTORE.storage_strategy.data)
            else:
                st.write('SURVEY_DATASTORE not available. Please select a survey.')


    with st.expander("Session State", expanded=False):
        st.write(st.session_state)

try:
    run()

except Exception as e:
    st.error(f'`Troubleshooter` **RUN exception:** {e}')
    st.stop()