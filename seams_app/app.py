import os
import streamlit as st
import shutil
from bgstools.io import get_available_services, create_directory_list, check_directory_exist_and_writable, path_exists
from bgstools.stt import build_activities_menu
from bgstools.io import load_toml_variables, create_subdirectory, create_new_directory
from sgu_seams_app.datastore_utils import update_DATASTORE

# --------------------
st.set_page_config(
    layout='wide',
    page_title='SEAMS-App',
    page_icon=':oyster:',
    initial_sidebar_state='expanded',
    )

def get_script_path():
    return os.path.dirname(os.path.realpath(__file__))

def init_session_state(default_data_subdirectory_name:str ='data', reset_session_state:bool = False):

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

    CONFIG_DIRPATH = get_script_path()
    LOGOS_FILEPATH = os.path.join(CONFIG_DIRPATH,'config/logos.toml')
    return load_toml_variables(LOGOS_FILEPATH)


def delete_subdirectory_with_confirmation(directory_path: str, btn_label: str = "Delete Subdirectory"):
    """
    Deletes a subdirectory with all its elements, showing a warning message with confirmation.

    Parameters:
    - directory_path: The path of the subdirectory to be deleted.

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
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"An error occurred while deleting the subdirectory: {e}")
                    return False
        else:
            return False
    else:
        st.info("No previous surveys for deletion.")
        return False


def build_sidebar():
    
    logos = load_logos()
    LOGO_SIDEBAR_URL = logos['LOGOS']['LOGO_SIDEBAR_URL']
    LOGO_ODF_URL = logos['LOGOS']['LOGO_ODF_URL']
    LOGO_BEGEOSPATIAL = logos['LOGOS']['LOGO_BEGEOSPATIAL']

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

    
    refresh_button = st.sidebar.button("Refresh")
    if refresh_button:
        # Clear values from *all* all in-memory and on-disk data caches:
        st.cache_data.clear()
        st.experimental_rerun()
        
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
   



def get_filename_from_filepath(path: str):
    return os.path.basename(os.path.normpath(path))

def get_dirpath_from_filepath(path: str):
    return os.path.dirname(path)



def new_survey():
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
                        update_DATASTORE({'APP': st.session_state['APP']}, callback_message=st.error)
                        st.toast(f'Survey: **{SURVEY_NAME}**  `SURVEY_DATASTORE` created and initialized')
                        
                        
                    st.success(f'Survey: **{SURVEY_NAME}** created')
                    st.experimental_rerun()                    
                        
                else:

                    st.error(f'Survey **{SURVEY_NAME}** already exists. Please, choose another name.')                   

def remove_session_state(session_state_keys: list):
    for key in session_state_keys:
        if key in st.session_state:
            del st.session_state[key]
                    
def delete_survey():
    st.divider()
    with st.container():
        SURVEYS_DIRPATH =  st.session_state.get('APP', {}).get('CONFIG', {}).get('SURVEYS_DIRPATH', None)
        if SURVEYS_DIRPATH is not None:
            available_surveys_dirpath = create_directory_list(SURVEYS_DIRPATH)
            options = {os.path.basename(os.path.normpath(survey_dirpath)): survey_dirpath for survey_dirpath in available_surveys_dirpath}
            selected_survey_dirname = st.selectbox('**DELETE survey :**', options=options, key='delete_survey_selectbox')
            if selected_survey_dirname:
                delete_subdirectory_with_confirmation(options[selected_survey_dirname], btn_label=f'Delete survey: **{selected_survey_dirname}**')
            
                

def survey_data_management():
    with st.sidebar.expander(label='**Survey data management**', expanded=False):
        with st.container():
            new_survey()
        with st.container():
            delete_survey()
        
                

def run():
    init_session_state()
    build_sidebar()
    survey_data_management()



if __name__ == '__main__':
    run()
else:
    st.error('The app failed initialization. Report issue to mantainers in github')

