import os
import streamlit as st
import pandas as pd
from PIL import Image
from typing import List
from enum import Enum
import traceback

from bgstools.stt import toggle_button

from sgu_seams_app.seafloor import substrates, phytobenthosCommonTaxa, \
STRATUM_ID, SPECIES_FLAGS, OTHER_BENTHOS_COVER_OR_BIOTURBATION, USER_DEFINED_TAXONS
from sgu_seams_app.services.survey_init import load_datastore
from sgu_seams_app.markers import create_bounding_box, markers_grid, floating_marker 
from sgu_seams_app.custom_options import SGU_custom_options


class Status(Enum):
    IN_PROGRESS = 'IN_PROGRESS'  # 'ICON': ':hourglass_flowing_sand:'
    COMPLETED = 'COMPLETED'   # 'ICON': ':white_check_mark:'
    NOT_STARTED = 'NOT_STARTED'   # 'ICON': ':no_entry:'
    ERROR = 'ERROR'  # 'ICON': ':warning:'
    UPDATED = 'UPDATED'   # 'ICON': ':star:'

# 224x224 image size coral net (https://coralnet.ucsd.edu/blog/a-new-deep-learning-engine-for-coralnet/)

def show_advanced_options()->dict:
    message_advanced_options = """
    **Advanced options** are available for users with a strong understanding of the tool's functionality. 
    These options directly influence the interpretation results by modifying the locations of the dot points 
    within the frame. It is crucial to exercise caution when using these settings, as altering the default values 
    can significantly impact the output. Only make changes if you possess a comprehensive understanding of the tool 
    and its implications.
    """    
    with st.sidebar.expander(label='**Advanced options**', expanded=False):
        st.info(message_advanced_options)
        
        # -------
        st.divider()
        col1, col2 = st.columns([1,1])
        with col1:
            n_rows = st.number_input(
                label='DotPoints rows', 
                min_value=3, 
                max_value=5, 
                value=3, 
                step=1, 
                help='Number of DotPoints rows in the grid', 
                
                )
        # --------
    
        with col2:
            noise_percent = st.slider(
                label='pepper and salt noise', 
                min_value=0.0, 
                max_value=1.0, 
                step=0.1, 
                )
        # -------
            
        DOTPOINTS_ADVANCED_OPTIONS = {
            'n_rows': n_rows,                
            'noise_percent': noise_percent,
            'enable_random': True,
        }
        return DOTPOINTS_ADVANCED_OPTIONS
        

def show_ai_options():
    with st.sidebar.expander('AI developement mode'):
        st.info('**AI developement mode** is for advanced users only and can change without any notice. It has no effect on the results as the AI model is not yet fully implemented.')
        enable_ai = st.checkbox(label='enable AI', value=False)


def build_header():
    st.title("SEAMS-App | benthos interpretation")
    st.sidebar.title("SEAMS-App | benthos interpretation")
    

def generate_new_dotpoints(
        MAXIMUM_DOTPOINTS:int = 10, 
        TAXONS:set() = None, 
        SUBSTRATE:str = None)->dict:
    
    DOTPOINTS_DICT = {}

    for i in range(0, MAXIMUM_DOTPOINTS):
        DOTPOINTS_DICT.update({})
    return DOTPOINTS_DICT


st.cache_data()
def convert_df(df:pd.DataFrame, index:bool=False, encoding:str='utf-8'):
    return df.to_csv(index=index).encode(encoding)


def frame_results(
        SURVEY_NAME:str,
        STATION_NAME:str,
        SURVEY_DIRPATH:str,
        VIDEO_NAME:str,
        FRAME_INTERPRETATION:dict, 
        key:str= None):
    METADATA = FRAME_INTERPRETATION.get('METADATA', {})
    if len(METADATA) > 0:
            
        FRAME_NAME = METADATA['FRAME_NAME']
        with st.expander(label='Frame results', expanded=True):
            
            if len(FRAME_INTERPRETATION['DOTPOINTS']) > 0:
                _FRAME_INTERPRETATION = FRAME_INTERPRETATION
                _IDs = FRAME_INTERPRETATION['DOTPOINTS'].keys()
                for id in _IDs:
                    _FRAME_INTERPRETATION['DOTPOINTS'][id]['SUBSTRATE'] = [s for s in FRAME_INTERPRETATION['DOTPOINTS'][id]['SUBSTRATE']][0]
                    _FRAME_INTERPRETATION['DOTPOINTS'][id]['TAXONS'] = [t for t in FRAME_INTERPRETATION['DOTPOINTS'][id]['TAXONS']] 
                df = pd.DataFrame.from_dict(_FRAME_INTERPRETATION['DOTPOINTS'], orient='index')
                column_config = {                            
                    'TAXONS': {'editable': True, 'rename': False,},
                    'SUBSTRATE':  st.column_config.SelectboxColumn(
                        label='substrate',
                        width='medium',
                        options=[s[0] for s in substrates],                                
                        ),  
                    'frame_x_coord': {'editable': False, 'rename': False},
                    'frame_y_coord': {'editable': False, 'rename': False},
                    'DOTPOINT_ID': {'editable': False, 'rename': False},                            
                    } 
                
                data_editor = st.data_editor(
                    data=df,
                    num_rows=10,
                    column_config= column_config,
                    key=key,
                    use_container_width=True, 
                    hide_index=True,
                    column_order=['DOTPOINT_ID', 'frame_x_coord', 'frame_y_coord', 'TAXONS', 'SUBSTRATE'],
                    disabled=True,
                    )
                
                FRAME_TAXONS = set()
                
                frame_summary_dict = data_editor.set_index('DOTPOINT_ID', drop=False).to_dict(orient='index')
                for id in frame_summary_dict:
                    FRAME_TAXONS.update([t for t in frame_summary_dict[id]['TAXONS']])
                    substrate = frame_summary_dict[id]['SUBSTRATE']
                    frame_summary_dict[id][substrate] = 1
                    for taxon in FRAME_TAXONS:                    
                        frame_summary_dict[id][taxon] = 1
             
                # ------------------
                st.write('## Frame summary')
                df = pd.DataFrame.from_dict(frame_summary_dict, orient='index')
                df = df.drop(columns=['SUBSTRATE', 'TAXONS'])
                df['SURVEY_NAME'] = SURVEY_NAME
                df['STATION_NAME'] = STATION_NAME
                df['FRAME_NAME'] = FRAME_NAME
                df['VIDEO_NAME'] = VIDEO_NAME
                
                st.divider()
                st.dataframe(df)

                save_to_file = st.button(label='Save file `csv`', key=f'button_{key}')
                if save_to_file:
                    filename = os.path.join(SURVEY_DIRPATH, f'{SURVEY_NAME}_STATION_{STATION_NAME}_FRAME_{FRAME_NAME}_frame_summary.csv')
                    with st.spinner('Saving file...'):
                        
                        df.to_csv(
                            os.path.join(filename),
                            encoding='utf-8',
                            index=False,
                            )
                    
                    if os.path.exists(filename):
                        st.info(f'File saved: {filename}')
                        st.balloons()

                return frame_summary_dict
            
            else:
                st.warning('No dotpoints selected or saved')
    else:
        st.warning('No data saved for selected frame yet.')               


def initialize_benthos_interpretation(CURRENT:dict=None)->dict:

        SURVEY_NAME = CURRENT['SURVEY_NAME']
        SURVEY_FILEPATH = CURRENT['SURVEY_FILEPATH']        
        STATION_NAME = CURRENT['STATION_NAME']
        VIDEO_NAME = CURRENT['VIDEO_NAME']

        SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)
        SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data
        
        result = {
            'SURVEY_NAME': SURVEY_NAME,
            'STATION_NAME': STATION_NAME,
            'VIDEO_NAME': VIDEO_NAME,
            'SURVEY_DATASTORE': SURVEY_DATASTORE,
            'SURVEY_DATA': SURVEY_DATA,
            }

        return result


def benthos_main_menu(
        SURVEY_NAME:str, 
        STATION_NAME:str, 
        VIDEO_NAME:str, 
        STATION_BENTHOS_INTERPRETATION:dict):
    

    RANDOM_FRAMES = STATION_BENTHOS_INTERPRETATION['RANDOM_FRAMES']
    RANDOM_FRAMES_INDEX_DICT = {i+1:k for i, k in enumerate(RANDOM_FRAMES.keys())}

    with st.expander(label='**Benthos interpretation**', expanded=True):
        hcol1, hcol2, hcol3, hcol4 = st.columns([1,1,2,1])
        with hcol1:
            st.markdown('##### Survey')
            st.subheader(f'**{SURVEY_NAME}**')
        with hcol2:
            st.markdown('##### Station')
            st.subheader(f'**:blue[{STATION_NAME}]**')
        with hcol3:
            st.markdown('##### Video')
            st.subheader(f'**{VIDEO_NAME}**')
        with hcol4:
            FRAME_INDEX = st.selectbox(
                label='**current frame**', 
                options=list(RANDOM_FRAMES_INDEX_DICT.keys()),
                format_func=lambda i: f'{str(i).zfill(2)} | {RANDOM_FRAMES_INDEX_DICT[i]}',
                help='Select the frame to interpret', 
                label_visibility='hidden')
            
        FRAME_NAME = RANDOM_FRAMES_INDEX_DICT[FRAME_INDEX]
        FRAME_FILEPATH = STATION_BENTHOS_INTERPRETATION['FRAMES'][FRAME_NAME]
        result = {
            'FRAME_INDEX': FRAME_INDEX, 
            'FRAME_NAME': FRAME_NAME, 
            'FRAME_FILEPATH': FRAME_FILEPATH, 
            }
        return result
            

def generate_toggle_buttons_grid(n_rows=3):
    grid =[]
    counter = 0 
    for i in range(n_rows):
        row = []
        if i % 2 == 0:
            # Even row: divide into 3
            for j in range(3):
                counter += 1
                row.append(str(counter))  # __Row_{i+1}_Col{j+1}
        else:
            # Odd row: divide into 4
            for j in range(4):
                counter += 1
                row.append(str(counter))
        grid.append(row)

    return grid

def display_grid(grid, disable_dotpoints:list = [])->dict:
    """Displays the generated grid on Streamlit."""
    dotpoints_selected_dict = {}
    counter = 0
    for row in grid:
        cols= st.columns(len(row))        
        for col in cols:
            with col:
                counter += 1
                toggle_button(
                    label = str(counter), 
                    key=f'dotpoint_{counter}',
                    disabled= True if counter in disable_dotpoints else False, 
                    )
                # adds the dotpoint to the dictionary if it is selected
                if st.session_state[f'dotpoint_{counter}']:
                    dotpoints_selected_dict[counter] = True
                # removes the dotpoint from the dictionary if it is deselected
                else:
                    if counter in dotpoints_selected_dict:
                        del dotpoints_selected_dict[counter]
                    
    return dotpoints_selected_dict


def reset_dotpoints(dotpoint_grid_ids:dict, FRAME_INTERPRETATION:dict, key:str):
    #dotpoints_done = FRAME_INTERPRETATION.get('DOTPOINTS_DONE', {})
    #dotpoints = FRAME_INTERPRETATION['DOTPOINTS']

    with st.form(key=key, clear_on_submit=True):
        reset_dotpoints = st.multiselect(
            label='**dotpoints to reset**', 
            options=[str(i) for i in dotpoint_grid_ids.keys()])
        
        reset = st.form_submit_button(label='reset')
        if reset:
            counter = 0
            if len(reset_dotpoints) > 0:
                for dotpoint in reset_dotpoints:
                    FRAME_INTERPRETATION['DOTPOINTS'].pop(dotpoint, None)
                    FRAME_INTERPRETATION['DOTPOINTS_DONE'].pop(dotpoint, None)                                        
                    counter += 1
                return FRAME_INTERPRETATION
                #st.experimental_rerun()

def create_markers_grid(FRAME_NAME:str, DOTPOINTS_ADVANCED_OPTIONS:dict, bbox:tuple):
    centroids = markers_grid(                                
        bbox, 
        n_rows=DOTPOINTS_ADVANCED_OPTIONS['n_rows'], 
        enable_random=True, 
        noise_percent=DOTPOINTS_ADVANCED_OPTIONS['noise_percent'])
    st.session_state['centroids'] = centroids
    st.session_state[FRAME_NAME] +=1

    # ------------------
    
    centroids_dict = { i+1: centroid for i, centroid in enumerate(centroids) }
    n_rows=DOTPOINTS_ADVANCED_OPTIONS['n_rows']
    st.session_state['n_rows'] = n_rows
    return n_rows, centroids, centroids_dict

def get_tab_suffix_icon(status):
    if status == 'IS_COMPLETE':
        tab_suffix = ':white_check_mark:'
    elif status == 'IN_PROGRESS':
        tab_suffix = ':hourglass_flowing_sand:'
    elif status == 'IS_ERROR':
        tab_suffix = ':warning:'
    elif status == 'IS_UPDATED':
        tab_suffix = ':star:'
    elif status == "NOT_STARTED":
        tab_suffix = ':no_entry:'
    else: 
        tab_suffix = ''
    return tab_suffix

st.cache_data()
def extended_taxons_list()->list:
    extended_list = sorted(list(list(phytobenthosCommonTaxa.keys()) + list(OTHER_BENTHOS_COVER_OR_BIOTURBATION) + list(USER_DEFINED_TAXONS)))
    return extended_list


def show_tabs(
        SURVEY_NAME:str = None,
        SURVEY_FILEPATH:str = None,
        STATION_NAME:str = None,            
        ):
    
    SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)

    if SURVEY_DATASTORE is not None:
        SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data        
        RANDOM_FRAMES = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES']
        VIDEO_NAME = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['VIDEO_NAME']

        SURVEY_DIRPATH = os.path.dirname(SURVEY_FILEPATH)
        if RANDOM_FRAMES is None or len(RANDOM_FRAMES) == 0:
            st.info('**No frames to display.**')
            return
        else: 
            # Generating FRAME_NAMES
            FRAME_NAMES = {i+1: k for i, k in enumerate(RANDOM_FRAMES.keys())}

            # Generating RANDOM_FRAMES_INDEX_DICT
            RANDOM_FRAMES_INDEX_DICT = {i: f'{k} {get_tab_suffix_icon(RANDOM_FRAMES[k]["INTERPRETATION"]["STATUS"])}' for i, k in FRAME_NAMES.items()}

            # Creating tab names list
            tab_names = [f'**{str(i).zfill(2)}** {RANDOM_FRAMES_INDEX_DICT[i]} |' for i in RANDOM_FRAMES_INDEX_DICT]

            # Adding 'RAW DATA' tab at the end
            tabs = st.tabs(tab_names + ['**RAW DATA** |'])

            # Show RAW DATA
            with tabs[-1]:
                st.write(SURVEY_DATA)            

            # Display frames using loop to avoid repetitive code
            for i in range(1, 11):  # Assuming 10 tabs are to be created for frames
                with tabs[i-1]:  # Using i-1 because list indexing starts at 0
                    FRAME_NAME = FRAME_NAMES[i]
                    frame_results(
                        SURVEY_NAME=SURVEY_NAME,
                        STATION_NAME=STATION_NAME,
                        VIDEO_NAME=VIDEO_NAME,
                        SURVEY_DIRPATH=SURVEY_DIRPATH,
                        FRAME_INTERPRETATION=RANDOM_FRAMES[FRAME_NAME]['INTERPRETATION'], 
                        key=f'xframe_{i}'
                    )
    else:
        st.info('**No frames to display.**')
        return

def frame_dashboard(
        SURVEY_NAME:str, 
        STATION_NAME:str, 
        VIDEO_NAME:str, 
        STATION_BENTHOS_INTERPRETATION:dict):

    # --------------------
    frame_selected = benthos_main_menu(
        SURVEY_NAME=SURVEY_NAME,
        STATION_NAME=STATION_NAME,
        VIDEO_NAME=VIDEO_NAME,   
        STATION_BENTHOS_INTERPRETATION=STATION_BENTHOS_INTERPRETATION
    )
    # --------------------
    FRAME_INDEX = frame_selected.get('FRAME_INDEX', None)
    FRAME_NAME = frame_selected.get('FRAME_NAME', None)
    FRAME_FILEPATH = frame_selected.get('FRAME_FILEPATH', None)
    FRAME_INTERPRETATION = RANDOM_FRAMES[FRAME_NAME]['INTERPRETATION']
    FRAME_INTERPRETATION['METADATA'] = frame_selected

    # --------------------
    if FRAME_NAME not in st.session_state:
        st.session_state[FRAME_NAME] = 0
    
    # --------------------
    image = Image.open(FRAME_FILEPATH)       
    # create bounding box polygon
    bbox = create_bounding_box(image=image)

    DOTPOINTS_ADVANCED_OPTIONS = show_advanced_options()

    # --------------------
    recol1, _= st.columns([4,1])
    with recol1:
            
        clear_recalculate = st.button(
            label='Re-calculate dotpoints', 
            help='Clear and re-calculate the dotpoints with the **advanced options**. Only for **advanced users**',
            disabled=True if len(st.session_state.get('dotpoints_done', {})) > 0 else False,
            )
            
    if clear_recalculate:
        n_rows, centroids, centroids_dict= create_markers_grid(
            FRAME_NAME=FRAME_NAME, 
            DOTPOINTS_ADVANCED_OPTIONS=DOTPOINTS_ADVANCED_OPTIONS,             
            bbox=bbox)
        

    elif st.session_state[FRAME_NAME] == 0:
        n_rows, centroids, centroids_dict= create_markers_grid(
            FRAME_NAME=FRAME_NAME, 
            DOTPOINTS_ADVANCED_OPTIONS=DOTPOINTS_ADVANCED_OPTIONS,             
            bbox=bbox)
        
    else:
        centroids = st.session_state['centroids']
        centroids_dict = { i+1: centroid for i, centroid in enumerate(centroids) }
        n_rows=st.session_state['n_rows']


    centroids_dict = { i+1: centroid for i, centroid in enumerate(centroids) }
    grid = generate_toggle_buttons_grid(n_rows=n_rows)                        

    with st.container():
        icol1, icol2 = st.columns([5,1])                
        with icol1:
            
            modified_image = floating_marker(image, centroids_dict=centroids_dict)
            st.image(modified_image)

        with icol2:
            dotpoints_done = FRAME_INTERPRETATION.get('DOTPOINTS_DONE', {})
            dotpoints_selected_dict = display_grid(
                grid=grid, 
                disable_dotpoints=list(dotpoints_done))
            
        
            if len(dotpoints_selected_dict) > 10:
                st.warning(f'You can only select up to 10 dotpoints. Deselect one or more dotpoints to proceed.')
                FRAME_INTERPRETATION = reset_dotpoints(
                    key='too_many_dotpoints',
                    dotpoint_grid_ids=dotpoints_selected_dict, 
                    FRAME_INTERPRETATION=FRAME_INTERPRETATION,
                    )
    
            substrate = st.selectbox(
                label='**Substrates**',
                options=[s[0] for s in substrates],
                help='Select the **substrate** present for the selected `dotpoints` in the frame.',
                placeholder='Select substrate',                            
                )
            
            
            _taxons = st.multiselect(
                label='**Taxons**',
                default=['Bare substrate'],
                options= extended_taxons_list(),
                help='Select the **taxons** present under the selected `dotpoints` in the frame.',
                placeholder='Select taxa',
                key='taxons_multiselect'

                )
            
            taxa_to_flag = [t for t in _taxons]

            # ----------------           
            with st.expander(label='**Taxa flags**', expanded=False):
                    
                if len(taxa_to_flag) > 0:
                    flag_taxa = st.selectbox(
                        label = 'Taxa to flag', 
                        options=['---'] + taxa_to_flag if taxa_to_flag is not None  and len(taxa_to_flag)>0 else [],
                        index=0,
                        help='Select **taxa** to apply flags',
                        placeholder='Select a taxa to apply flags',)
                    
                    if flag_taxa != '---':
                            
                        SFLAG_options = [s for s in SPECIES_FLAGS['SFLAG']]
                        SFLAG = st.selectbox(
                            label = 'SFLAG(s)', 
                            options=['---'] + SFLAG_options if SFLAG_options is not None  and len(SFLAG_options)>0 else [],
                            help='Select the **taxon flags** present in the selected taxa',)
                        
                        SFLAG_string = f'SFLAG {SFLAG}' if SFLAG != '---' else ''
                        
                        if SFLAG != '---':
                            st.info(SPECIES_FLAGS['SFLAG'][SFLAG])
                        
                        STRID_options = sorted([s for s in STRATUM_ID['CODE']])
                        STRID = st.selectbox(
                            label = 'STRID - Stratum ID', 
                            options=['---'] + STRID_options if STRID_options is not None  and len(STRID_options)>0 else [],
                            help='Select the **taxon rid** present in the selected taxa',)

                        if STRID != '---':
                            st.info(STRATUM_ID['CODE'][STRID])
                    # ------------------

                        STRID_string = STRID if STRID != '---' else ''

                        flag_taxa_string = f'{flag_taxa} {SFLAG_string} {STRID_string}'
                        flagged_taxa = flag_taxa_string.strip()
                        
                        if STRID != '---' or SFLAG != '---':
                            keep_only_flagged_taxa = st.checkbox(
                                label=f'**keep only :blue[{flagged_taxa}]** and remove **:red[{flag_taxa}]**', 
                                value=True, 
                                help=f'If enabled, ***{flag_taxa}*** will removed from the taxons and only **{flagged_taxa}** will be kept.')
                            if not keep_only_flagged_taxa:
                                taxa_to_flag.append(flagged_taxa)
                                
                            else:
                                taxa_to_flag.remove(flag_taxa)
                                taxa_to_flag.append(flagged_taxa)
            # ------------------
            overall_taxons = {i:True for i in taxa_to_flag}
            _substrate = {substrate:True}
            dotpoints_to_save = set(dotpoints_selected_dict).difference(set(dotpoints_done))
            dotpoints = {i : {
                    'DOTPOINT_ID': i,
                    'frame_x_coord': int(centroids_dict[i].x),
                    'frame_y_coord': int(centroids_dict[i].y),
                    'TAXONS': overall_taxons,
                    'SUBSTRATE':_substrate,
                    'boundary_width':224,
                    'boundary_height':224, } for i in dotpoints_to_save}
            
            st.session_state['dotpoints'] = dotpoints
            # ------------------
            FRAME_INTERPRETATION = RANDOM_FRAMES[FRAME_NAME]['INTERPRETATION']
                
            if 'DOTPOINTS' not in FRAME_INTERPRETATION:
                FRAME_INTERPRETATION['DOTPOINTS'] = dotpoints                                
            else:
                FRAME_INTERPRETATION['DOTPOINTS'].update(dotpoints)

            with st.expander(label = '**General in frame**'):                        
                GENERAL_IN_FRAME = st.multiselect(
                    label='**Other cover or bioturbation**',
                    options= extended_taxons_list(),
                    help='Select the **other benthos cover or bioturbation** present in the frame.',
                    placeholder='Select other benthos cover or bioturbation',
                    key='general_multiselect'
                )
                _GENERAL_IN_FRAME = {k:True for k in GENERAL_IN_FRAME}
                if 'GENERAL_IN_FRAME' not in FRAME_INTERPRETATION:                               
                    FRAME_INTERPRETATION['GENERAL_IN_FRAME'] = _GENERAL_IN_FRAME
                else:
                    FRAME_INTERPRETATION['GENERAL_IN_FRAME'].update(_GENERAL_IN_FRAME)

            with st.expander(label='**Custom**', expanded=False):
                custom_options =  SGU_custom_options()
                
                if 'CUSTOM_OPTIONS' not in FRAME_INTERPRETATION:
                    FRAME_INTERPRETATION['CUSTOM_OPTIONS'] = custom_options
                else:
                    FRAME_INTERPRETATION['CUSTOM_OPTIONS'].update(custom_options)
            # -------------------
            overall_substrates = _substrate
            SURVEY_DATASTORE.storage_strategy.data['APP']['SUBSTRATES'].update(overall_substrates)
            SURVEY_DATASTORE.storage_strategy.data['APP']['TAXONS'].update(overall_taxons)                        
            # ------------------
            confirm = st.button(label='confirm')
            
            with st.expander(label='**Reset dotpoints**', expanded=False):
                FRAME_INTERPRETATION = reset_dotpoints(
                    key='reset_dotpoints',
                    dotpoint_grid_ids=dotpoints_selected_dict, 
                    FRAME_INTERPRETATION=FRAME_INTERPRETATION,
                    )

            if confirm:
                if len(dotpoints_to_save) == 0:
                    st.warning('**Dotpoints** not selected')

                if len(_taxons) == 0:
                    st.warning('**Taxa** is not selected')
                else:
                    DOTPOINTS_DONE = {k:True for k in FRAME_INTERPRETATION['DOTPOINTS'].keys() if len(FRAME_INTERPRETATION['DOTPOINTS'][k]) >0}
                    FRAME_INTERPRETATION['DOTPOINTS_DONE'] = DOTPOINTS_DONE
                    st.session_state['dotpoints_done'] = DOTPOINTS_DONE
                    if len(FRAME_INTERPRETATION.get('DOTPOINTS_DONE', {})) == 10:
                        FRAME_INTERPRETATION['STATUS'] = Status.COMPLETED.value
                    elif len(FRAME_INTERPRETATION.get('DOTPOINTS_DONE', {})) > 0:
                        FRAME_INTERPRETATION['STATUS'] = Status.IN_PROGRESS.value
                    else:
                        FRAME_INTERPRETATION['STATUS'] = Status.NOT_STARTED.value

                    # ---------

                    try:
                        SURVEY_DATASTORE.storage_strategy.data = SURVEY_DATA
                        SURVEY_DATASTORE.store_data(data=SURVEY_DATA)
                        st.success('**Dotpoints** saved')
                    except Exception as e:
                        st.error(traceback.print_exc())
                        st.error('**Dotpoints** not saved')
                    else:
                        return FRAME_INTERPRETATION

try:
    suffix = st.session_state.get('suffix', '***')

    build_header()

    CURRENT = st.session_state.get('CURRENT', None)
    # --------------------
    if CURRENT is None:
        st.info('**Fresh current state.**')
    

    SURVEY_NAME = CURRENT.get('SURVEY_NAME', None)
    STATION_NAME = CURRENT.get('STATION_NAME', None)
    VIDEO_NAME = CURRENT.get('VIDEO_NAME', None)
    SURVEY_FILEPATH = CURRENT.get('SURVEY_FILEPATH', None)
    
    

    if SURVEY_FILEPATH is not None:
        SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)
        if VIDEO_NAME is None:
            st.warning('Station with incompatible video selected or survey not initialized properly. Ensure the selected station and available video has the suffix **(***)**. Go to **Menu>Survey initialization** to initialize the survey.')
            st.stop()            
       
        SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data
        STATION_BENTHOS_INTERPRETATION = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]
        RANDOM_FRAMES = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES']

        FRAME_INTERPRETATION = frame_dashboard(
            SURVEY_NAME=SURVEY_NAME,
            STATION_NAME=STATION_NAME,
            VIDEO_NAME=VIDEO_NAME,            
            STATION_BENTHOS_INTERPRETATION=STATION_BENTHOS_INTERPRETATION,                      
        )

        # ----
                    
        show_tabs(
            SURVEY_NAME=SURVEY_NAME,            
            SURVEY_FILEPATH=SURVEY_FILEPATH,
            STATION_NAME=STATION_NAME,
            
           )
    else:
        st.warning('Survey not initialized. Go to **Menu>Survey initialization** to initialize the survey.')
        

except Exception as e:
    trace_error = traceback.print_exc()
    if trace_error is None:
        trace_error= ''
    else:        
        st.error(f'**Benthos interpretation exception:** {trace_error} {e} | **Refresh the app and try again**')
    