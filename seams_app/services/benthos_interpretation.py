import os
import random
import streamlit as st
import pandas as pd
from PIL import Image
from typing import Literal
from enum import Enum
import traceback
from bgstools.datastorage import DataStore
from bgsio import load_yaml

from seafloor import substrates, phytobenthosCommonTaxa, \
STRATUM_ID, SPECIES_FLAGS, OTHER_BENTHOS_COVER_OR_BIOTURBATION, USER_DEFINED_TAXONS

from markers import create_bounding_box, markers_grid, floating_marker 
from custom_options import SGU_custom_options
from seams_utils import update_station_data, load_datastore, toggle_button

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
        n_rows = 3
        # TOBE DEPRECATED
        #col1, col2 = st.columns([1,1])
        #with col1:
        #    n_rows = st.number_input(
        #        label='DotPoints rows', 
        #        min_value=3, 
        #        max_value=5, 
        #        value=3, 
        #        step=1, 
        #        help='Number of DotPoints rows in the grid',                 
        #        )
        # --------    
        #with col2:
        noise_percent = st.slider(
            label='pepper and salt noise', 
            min_value=0.0, 
            max_value=1.0, 
            step=0.1, 
            )
    # -------

        recalculate_dotpoints = st.button(
            label='Re-calculate dotpoints', 
            help='Clear and re-calculate the dotpoints',
            disabled=True if len(st.session_state.get('dotpoints_done', {})) > 0 else False,
            )

                        
        DOTPOINTS_ADVANCED_OPTIONS = {
            'n_rows': n_rows,                
            'noise_percent': noise_percent,
            'enable_random': True,
            'recalculate_dotpoints': recalculate_dotpoints
        }
    

        return DOTPOINTS_ADVANCED_OPTIONS
        

def build_header():
    hcol1, hcol2 = st.columns([3,1])
    with hcol1:
        st.subheader("SEAMS | benthos interpretation")
    with hcol2:
        frame_info = st.empty()            
    return frame_info
    

st.cache_data()
def convert_df(df:pd.DataFrame, index:bool=False, encoding:str='utf-8'):
    return df.to_csv(index=index).encode(encoding)


def station_results(STATION_DATA, taxons:list = [], substrates:list = []):
    df = []    
    summary = {}
    STATION_NAME = STATION_DATA['METADATA']['siteName']
    SURVEY_NAME = STATION_DATA['BENTHOS_INTERPRETATION']['SURVEY_NAME']
    VIDEO_NAME = STATION_DATA['BENTHOS_INTERPRETATION']['VIDEO_NAME']
    STATION_DIRPATH = os.path.dirname(STATION_DATA['BENTHOS_INTERPRETATION']['STATION_FILEPATH'])

    for FRAME_NAME in STATION_DATA['BENTHOS_INTERPRETATION']['RANDOM_FRAMES']:
        FRAME_INTERPRETATION = STATION_DATA['BENTHOS_INTERPRETATION']['RANDOM_FRAMES'][FRAME_NAME]['INTERPRETATION']

        METADATA = FRAME_INTERPRETATION.get('METADATA', {})
        if len(METADATA) > 0:            
            if len(FRAME_INTERPRETATION['DOTPOINTS']) > 0:
                _FRAME_INTERPRETATION = FRAME_INTERPRETATION
                _IDs = FRAME_INTERPRETATION['DOTPOINTS'].keys()
                _df = pd.DataFrame.from_dict(_FRAME_INTERPRETATION['DOTPOINTS'], orient='index')
                _df['SURVEY_NAME'] = SURVEY_NAME
                _df['STATION_NAME'] = STATION_NAME
                _df['VIDEO_NAME'] = VIDEO_NAME
                _df['FRAME_NAME'] = FRAME_NAME
                for t in taxons:
                    _df[t] = None
                    summary[t] = 0                                                       
                for s in substrates:
                    _df[s] = None
                    summary[s] = 0

                for id in _IDs:
                    is_id = _df['DOTPOINT_ID'] == id
                    _subtrate = _df.loc[is_id, 'SUBSTRATE']
                    _taxons = _df.loc[is_id, 'TAXONS'].tolist()[0]
                    if isinstance(_taxons, dict):
                        _taxons = list(_taxons.keys())
                    if isinstance(_subtrate, dict):
                        _subtrate = list(_subtrate.keys())[0]

                    #st.write(_subtrate, _taxons)

                    if _subtrate in substrates:
                        _df.loc[is_id, _subtrate] = 1
                        

                    for t in _taxons:
                        if t is not None:                                        
                            if t in taxons:
                                _df.loc[is_id, t] = 1
                                

                df.append(_df)
                
                                            
        #df = pd.concat(df)
        #df = df.drop(columns=['SUBSTRATE', 'TAXONS'])

        is_station = df['STATION_NAME'] == STATION_NAME

        for t in taxons:
            summary[t] = df.loc[is_station, t].sum()
        for s in substrates:
            summary[s] = df.loc[is_station, s].sum()


        column_config = {                                        
           
            'frame_x_coord': {'editable': False, 'rename': False},
            'frame_y_coord': {'editable': False, 'rename': False},
            'DOTPOINT_ID': {'editable': False, 'rename': False},                            
            } 
        
        st.markdown(f'## Percent cover `{STATION_NAME}`')
        st.dataframe(pd.DataFrame.from_dict(summary, orient='index').T, hide_index=True)
        st.markdown('## Survey results')
        data_editor = st.data_editor(
            data=df.drop(columns=['SUBSTRATE', 'TAXONS']),
            #num_rows=10,
            column_config= column_config,
            key='data_editor_survey',
            use_container_width=True, 
            hide_index=True,
            column_order=['SURVEY_NAME', 'STATION_NAME', 'VIDEO_NAME', 'FRAME_NAME', 'DOTPOINT_ID', 'frame_x_coord', 'frame_y_coord']+ taxons + substrates,
            disabled=True,
            )
        

        st.write(summary)
        st.divider()           

        save_to_file = st.button(label='Save file `csv`', key=f'button_save_survey')
        if save_to_file:
            filename = os.path.join(STATION_DIRPATH, f'SEAMS_{SURVEY_NAME}_RESULTS_{STATION_NAME}.csv')
            with st.spinner('Saving file...'):
                   df.to_csv(
                       os.path.join(filename),
                        encoding='utf-8',
                        index=False,
                        )
                
            if os.path.exists(filename):
                st.info(f'File saved: {filename}')
                st.balloons()



def survey_results(SURVEY_DATA):

    df = []
    stations = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'].keys()
    SURVEY_DIRPATH = SURVEY_DATA['APP']['SURVEY']['SURVEY_DIRPATH']

    taxons = list(SURVEY_DATA['APP']["TAXONS"].keys())
    substrates = list(SURVEY_DATA['APP']["SUBSTRATES"].keys())

    summary = {}

    if len(taxons) > 0:            
        for STATION_NAME in stations:
            FRAMES = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES']
            for FRAME_NAME in FRAMES:
                FRAME_INTERPRETATION = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['RANDOM_FRAMES'][FRAME_NAME]['INTERPRETATION']

                METADATA = FRAME_INTERPRETATION.get('METADATA', {})
                if len(METADATA) > 0:            
                    if len(FRAME_INTERPRETATION['DOTPOINTS']) > 0:
                        _FRAME_INTERPRETATION = FRAME_INTERPRETATION
                        _IDs = FRAME_INTERPRETATION['DOTPOINTS'].keys()
                        _df = pd.DataFrame.from_dict(_FRAME_INTERPRETATION['DOTPOINTS'], orient='index')
                        _df['SURVEY_NAME'] = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['SURVEY_NAME']
                        _df['STATION_NAME'] = STATION_NAME
                        _df['VIDEO_NAME'] = SURVEY_DATA['APP']['BENTHOS_INTERPRETATION'][STATION_NAME]['VIDEO_NAME']
                        _df['FRAME_NAME'] = FRAME_NAME
                        for t in taxons:
                            _df[t] = None
                            summary[t] = 0                                                       
                        for s in substrates:
                            _df[s] = None
                            summary[s] = 0

                        for id in _IDs:
                            is_id = _df['DOTPOINT_ID'] == id
                            _subtrate = _df.loc[is_id, 'SUBSTRATE'].tolist()[0]
                            _taxons = _df.loc[is_id, 'TAXONS'].tolist()[0]
                            if isinstance(_taxons, dict):
                                _taxons = list(_taxons.keys())
                            if isinstance(_subtrate, dict):
                                _subtrate = list(_subtrate.keys())[0]

                            #st.write(_subtrate, _taxons)

                            if _subtrate in substrates:
                                _df.loc[is_id, _subtrate] = 1
                                

                            for t in _taxons:
                                if t is not None:                                        
                                    if t in taxons:
                                        _df.loc[is_id, t] = 1
                                        

                        df.append(_df)
                        
                                            
        df = pd.concat(df)
        df = df.drop(columns=['SUBSTRATE', 'TAXONS'])

        is_station = df['STATION_NAME'] == STATION_NAME

        for t in taxons:
            summary[t] = df.loc[is_station, t].sum()
        for s in substrates:
            summary[s] = df.loc[is_station, s].sum()


        column_config = {                                        
           
            'frame_x_coord': {'editable': False, 'rename': False},
            'frame_y_coord': {'editable': False, 'rename': False},
            'DOTPOINT_ID': {'editable': False, 'rename': False},                            
            } 
        
        st.markdown(f'## Percent cover `{STATION_NAME}`')
        st.dataframe(pd.DataFrame.from_dict(summary, orient='index').T, hide_index=True)
        st.markdown('## Survey results')
        data_editor = st.data_editor(
            data=df,
            #num_rows=10,
            column_config= column_config,
            key='data_editor_survey',
            use_container_width=True, 
            hide_index=True,
            column_order=['SURVEY_NAME', 'STATION_NAME', 'VIDEO_NAME', 'FRAME_NAME', 'DOTPOINT_ID', 'frame_x_coord', 'frame_y_coord']+ taxons + substrates,
            disabled=True,
            )
        
        st.divider()           

        save_to_file = st.button(label='Save file `csv`', key=f'button_save_survey')
        if save_to_file:
            filename = os.path.join(SURVEY_DIRPATH, f'SEAMS_SURVEY_RESULTS_{SURVEY_NAME}.csv')
            with st.spinner('Saving file...'):
                   df.to_csv(
                       os.path.join(filename),
                        encoding='utf-8',
                        index=False,
                        )
                
            if os.path.exists(filename):
                st.info(f'File saved: {filename}')
                st.balloons()


def frame_results(
        STATION_DATA:dict,        
        FRAME_NAME:str,        
        key:str= None):
    
    FRAME_INTERPRETATION = STATION_DATA.get('BENTHOS_INTERPRETATION', {}).get('RANDOM_FRAMES', {}).get(FRAME_NAME, {}).get('INTERPRETATION', {})
    METADATA = FRAME_INTERPRETATION.get('METADATA', {})
    if len(METADATA) > 0:            
        if len(FRAME_INTERPRETATION['DOTPOINTS']) > 0:
            _FRAME_INTERPRETATION = FRAME_INTERPRETATION
            _IDs = FRAME_INTERPRETATION['DOTPOINTS'].keys()
            for id in _IDs:
                _FRAME_INTERPRETATION['DOTPOINTS'][id]['SUBSTRATE'] = [s for s in FRAME_INTERPRETATION['DOTPOINTS'][id]['SUBSTRATE']][0]
                _FRAME_INTERPRETATION['DOTPOINTS'][id]['TAXONS'] = [t for t in FRAME_INTERPRETATION['DOTPOINTS'][id]['TAXONS']] 
            df = pd.DataFrame.from_dict(_FRAME_INTERPRETATION['DOTPOINTS'], orient='index')
            df['FRAME_NAME'] = FRAME_NAME

            column_config = {                            
                'TAXONS': {'editable': False, 'rename': False,},
                'SUBSTRATE':  st.column_config.SelectboxColumn(
                    label='SUBSTRATE',
                    width='medium',
                    options=[s[0] for s in substrates],                                
                    ),  
                'frame_x_coord': {'editable': False, 'rename': False},
                'frame_y_coord': {'editable': False, 'rename': False},
                'DOTPOINT_ID': {'editable': False, 'rename': False},                            
                } 
            
            st.data_editor(
                data=df,
                num_rows=10,
                column_config= column_config,
                key='data_editor_frames',
                use_container_width=True, 
                hide_index=True,
                column_order=['FRAME_NAME', 'DOTPOINT_ID', 'frame_x_coord', 'frame_y_coord', 'TAXONS', 'SUBSTRATE'],
                disabled=True,
                )
            
        
        else:
            st.warning('No dotpoints selected or saved')
    else:
        st.warning('No data saved for selected frame yet.')               


def benthos_main_menu(
        SURVEY_NAME:str, 
        STATION_NAME:str, 
        VIDEO_NAME:str, 
        RANDOM_FRAMES:dict, 
        ):
    
    RANDOM_FRAMES_INDEX_DICT = {i+1:k for i, k in enumerate(RANDOM_FRAMES.keys())}

    with st.sidebar.expander(label='**Benthos interpretation**', expanded=True):
        
        st.markdown('##### Survey')
        st.subheader(f'**:blue[{SURVEY_NAME}]**')
        
        st.markdown('##### Station')
        st.subheader(f'**:blue[{STATION_NAME}]**')
        
        st.markdown('##### Video')
        st.subheader(f'**{VIDEO_NAME}**')
        
        FRAME_INDEX = st.selectbox(
            label='**current frame**', 
            options=list(RANDOM_FRAMES_INDEX_DICT.keys()),
            format_func=lambda i: f'{str(i).zfill(2)} | {RANDOM_FRAMES_INDEX_DICT[i]}',
            help='Select the frame to interpret', 
            label_visibility='hidden')
        
        FRAME_NAME = RANDOM_FRAMES_INDEX_DICT[FRAME_INDEX]        
        FRAME_FILEPATH = RANDOM_FRAMES[FRAME_NAME]['FILEPATH']


        result = {
            'FRAME_INDEX': FRAME_INDEX, 
            'FRAME_NAME': FRAME_NAME, 
            'FRAME_FILEPATH': FRAME_FILEPATH,             
            }
        
        
        st.session_state['FRAME_NAME'] = FRAME_NAME
        st.session_state['FRAME_INDEX'] = FRAME_INDEX
        st.session_state['FRAME_FILEPATH'] = FRAME_FILEPATH
        
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
    if grid is not None and len(grid) > 0:
        for row in grid:
            cols= st.columns(len(row))        
            for col in cols:
                with col:
                    counter += 1
                    toggle_button(                    
                        label = str(counter), 
                        key=f'dotpoint_{counter}',
                        disabled= True if str(counter) in disable_dotpoints else False,
                        on_sidebar=True, 
                        )
                    # adds the dotpoint to the dictionary if it is selected

                    st.session_state['COUNTER'] = counter

                    if st.session_state[f'dotpoint_{counter}']:
                        dotpoints_selected_dict[counter] = True                
            
    return dotpoints_selected_dict



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
    
    extended_list = sorted(list(phytobenthosCommonTaxa.keys()) + list(OTHER_BENTHOS_COVER_OR_BIOTURBATION) + list(USER_DEFINED_TAXONS))    
    
    return extended_list


def toggle_dotpoint(dotpoint_number, dotpoints_type: Literal['taxon', 'substrate']='taxon')->dict:
    dictionary = st.session_state
    key = None
    if dotpoints_type == 'taxon':
        key = f"{dotpoints_type}_dotpoint_{dotpoint_number}"
    if dotpoints_type == 'substrate':
        key = f"{dotpoints_type}_dotpoint_{dotpoint_number}"
    
    if key is not None and key in dictionary:
        dictionary[key] = not dictionary[key]

    st.session_state = dictionary
    return dictionary

def set_dotpoints(dotpoint_indexes:list, value:bool =True, dotpoints_type: Literal['taxon', 'substrate']='taxon')->dict:
    dictionary = st.session_state
    for dotpoint_index in dotpoint_indexes:
        key = f"{dotpoints_type}_dotpoint_{dotpoint_index}"
        if key in dictionary:
            dictionary[key] = value
    st.session_state = dictionary
    return dictionary


def flatten_list(input_list:list)->list:
    flattened = [value for sublist in input_list for value in sublist]
    return flattened


def show_tabs(        
        SURVEY_FILEPATH:str = None,        
        STATION_DATA:dict = {},
        FRAME_NAME:str = None,            
        ):
    
    SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)

    if STATION_DATA is not None:
        SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data        
        RANDOM_FRAMES = STATION_DATA.get('BENTHOS_INTERPRETATION', {}).get('RANDOM_FRAMES', {})
        TAXONS = list(SURVEY_DATA['APP']["TAXONS"].keys())
        SUBSTRATES = list(SURVEY_DATA['APP']["SUBSTRATES"].keys())

        
        if RANDOM_FRAMES is None or len(RANDOM_FRAMES) == 0:
            st.info('**No frames to display.**')
            return
        else: 
            # Generating FRAME_NAMES
            FRAME_NAMES = {i+1: k for i, k in enumerate(RANDOM_FRAMES.keys())}

            # Adding 'RAW DATA' tab at the end
            tabs = st.tabs(['**STATION RESULTS** |', '**RAW DATA** |'])

            # Show RAW DATA
            with tabs[-1]:
                st.write(STATION_DATA) 

            # Show SURVEY SUMMARY
            with tabs[0]:
                with st.expander(label='**STATION SUMMARY**', expanded=True):
                    _status = [f"{i} | {k}" for i, k in FRAME_NAMES.items() if RANDOM_FRAMES[k]["INTERPRETATION"]["STATUS"] == "COMPLETED"]
                    
                    col1, col2 = st.columns([1,1])

                    with col1:
                        st.write(f'**FRAMES COMPLETED** : {len(_status)} / {len(FRAME_NAMES)}')

                    with col2:
                        if len(_status) > 0:
                            st.multiselect(
                                label='FRAMES COMPLETED', 
                                options=_status,
                                default=_status, 
                                disabled=True,)
                    
                    frame_results(
                            STATION_DATA=STATION_DATA,                            
                            FRAME_NAME=FRAME_NAME,                            
                            key=f'xframe_{FRAME_NAME}'
                        )
                #TODO: Show survey results
                with st.expander(label='**SURVEY RESULTS**', expanded=True):
                    station_results(STATION_DATA, taxons=TAXONS, substrates=SUBSTRATES)
                    #survey_results(STATIONS_DIRPATH)

                    
    else:
        st.info('**No frames to display.**')
        return


# --------------
def dict_to_dataframe(DOTPOINTS:dict):
    frame_data = []
    for frame_key, frame_info in RANDOM_FRAMES.items():
        for dotpoint_id in range(1,11):

            st.info(DOTPOINTS[str(dotpoint_id)])
            
            
            taxons_list = [taxon for taxon, value in DOTPOINTS[str(dotpoint_id)].get("TAXONS", {}).items() if value]
            substrate_list = [substrate for substrate, value in DOTPOINTS[str(dotpoint_id)].get("SUBSTRATE", {}).items() if value]

            row_data = {
                "FRAME_KEY": frame_key,                
                "DOTPOINT_ID": dotpoint_id,
                #"frame_x_coord": dotpoint_info.get("frame_x_coord", None),
                #"frame_y_coord": dotpoint_info.get("frame_y_coord", None),
                "TAXONS": taxons_list,
                "SUBSTRATE": substrate_list,
                #"boundary_width": dotpoint_info.get("boundary_width", None),
                #"boundary_height": dotpoint_info.get("boundary_height", None),
                "FILEPATH": frame_info["FILEPATH"]
            }
            frame_data.append(row_data)

    df = pd.DataFrame(frame_data)
    return df


def show_frame_select_menu(
        SURVEY_NAME:str, 
        STATION_NAME:str, 
        VIDEO_NAME:str, 
        RANDOM_FRAMES:dict):
    """_summary_

    Args:
        SURVEY_NAME (str): _description_
        STATION_NAME (str): _description_
        VIDEO_NAME (str): _description_
        RANDOM_FRAMES (dict): _description_

    Returns:
        _type_: _description_
    """
    frame_selected_dict = benthos_main_menu(
        SURVEY_NAME=SURVEY_NAME,
        STATION_NAME=STATION_NAME,
        VIDEO_NAME=VIDEO_NAME,   
        RANDOM_FRAMES=RANDOM_FRAMES,
    )
    
    # --------------------    
    FRAME_FILEPATH = frame_selected_dict.get('FRAME_FILEPATH', None)
    FRAME_NAME = frame_selected_dict.get('FRAME_NAME', None)
    FRAME_INDEX = frame_selected_dict.get('FRAME_INDEX', None)


    # Required to know if the frame has been dotpoints drawed before.
    if FRAME_NAME not in st.session_state:        
        st.session_state[FRAME_NAME] = 0
    
    # --------------------
    image = Image.open(FRAME_FILEPATH)
    return frame_selected_dict, image


def taxons_interpretation(SPECIES_FLAGS:dict, STRATUM_ID:dict)->dict:

    _taxons = st.multiselect(
        label='**Taxons**',
        options= extended_taxons_list(),
        help='Select the **taxons** present under the selected `dotpoints` in the frame.',
        placeholder='Select taxa',
        key='taxons_multiselect',
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
                        st.session_state['CURRENT']['taxa_to_flag'] = taxa_to_flag
                        
                    else:
                        taxa_to_flag.remove(flag_taxa)
                        taxa_to_flag.append(flagged_taxa)
                        st.session_state['CURRENT']['taxa_to_flag'] = taxa_to_flag
    # ------------------
    # Overall taxons
    result_taxons = {i:True for i in taxa_to_flag}  

    return result_taxons

def substrates_interpretation(substrates:dict)->dict:
    substrate = st.selectbox(
                    label='**Substrates**',
                    options=[s[0] for s in substrates],
                    help='Select the **substrate** present for the selected `dotpoints` in the frame.',
                    placeholder='Select substrate',
                    key='substrates_selectbox',
                    index=None
                    )
    
    if substrate is not None:
        return {substrate:True}
    else:
        return {}



def seafloor_interpretation_data_editor(
        data_config_dict:dict, 
        colnames: list=range(1,11),         
        df:pd.DataFrame = None,  
        num_rows='dynamic', 
        width='small'):
    """
    Visualizes a table with 10 columns, named 1 to 10, with a single row that can be added to, where the user can use a Streamlit single-select selectbox in each cell of the data editor to select a single taxon from a list of taxons.

    Args:
        taxons: A list of taxons to display in the selectbox widget.

    Returns:
        A Pandas DataFrame containing the user's selections.
    """
    options = data_config_dict['options']
    # Create a Pandas DataFrame with a single row and 10 columns, named 1 to 10.
    if df is None:
        df = pd.DataFrame({i: [None] for i in colnames})
    
    dotpoint_type = data_config_dict['dotpoint_type']

    
    st.markdown(
        f'DotPoints **{str(dotpoint_type).upper()}**', 
        help=f'Select the **{str(dotpoint_type).upper()}** present for the selected `dotpoints` in the frame. Double click in the cell to select {str(dotpoint_type).upper()}',
    )
    
    # Create a Streamlit data editor widget for the DataFrame.
    edited_df = st.data_editor(
        df,
        hide_index=True,
        num_rows=num_rows,
        use_container_width=True,
        column_config={
            f'{i}': st.column_config.SelectboxColumn(
                label=f'{i}',
                options=options,
                width=width,
                required=True,
                default=None,
                )
                for i in colnames},

        key=f'data_editor_{dotpoint_type}',
        
        )
    # Return the user's selections.
    return edited_df


def search_value_in_dataframe(df:pd.DataFrame, target:str)->dict:
    """
    Search for a target value in a Pandas DataFrame and retrieve a dictionary
    of the row and column indices where the value was found.

    Parameters:
    - df (pandas.DataFrame): The DataFrame to search.
    - target (str): The target value to search for.

    Returns:
    - dict: A dictionary containing (index, column) tuples as keys and
      corresponding cell values as values.
    """

    result = {}
    for index, row in df.iterrows():
        for column, value in row.iteritems():
            if value == target:
                result[(index, column)] = value
    return result


def taxons_selector(taxa_to_flag: list, SPECIES_FLAGS:dict=SPECIES_FLAGS, STRATUM_ID:dict=STRATUM_ID)->str:

    # ----------------           

    if len(taxa_to_flag) > 0:
        tscol1, tscol2, tscol3, tscol4, tscol5 = st.columns([1,1,1,2,1])
        
        with tscol1:
                
            flag_taxa = st.selectbox(
                label = 'Taxa to flag', 
                options=['---'] + taxa_to_flag if taxa_to_flag is not None  and len(taxa_to_flag)>0 else [],
                index=0,
                help='Select **taxa** to apply flags',
                placeholder='Select a taxa to apply flags',)
        
        with tscol2:

            if flag_taxa != '---':
                flagged_taxa = flag_taxa
                    
                SFLAG_options = [s for s in SPECIES_FLAGS['SFLAG']]
                SFLAG = st.selectbox(
                    label = 'SFLAG(s)', 
                    options=['---'] + SFLAG_options if SFLAG_options is not None  and len(SFLAG_options)>0 else [],
                    help='Select the **taxon flags** present in the selected taxa',)
                
                SFLAG_string = f'SFLAG {SFLAG}' if SFLAG != '---' else ''
                if SFLAG != '---':
                    st.info(SPECIES_FLAGS['SFLAG'][SFLAG])
            
                with tscol3:
                    
                    
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
                    
                with tscol4:

                    if STRID != '---' or SFLAG != '---':
                        
                        confirm_taxa_to_flag = st.button(label=f'ADD: **{flagged_taxa}**', help=f'Confirm the **taxa** to add to the available taxa list')
                        if confirm_taxa_to_flag:
                            taxa_to_flag.remove(flag_taxa)
                            taxa_to_flag.append(flagged_taxa)
                
                            if flag_taxa != flagged_taxa:                                
                                return flagged_taxa
                                
                    
def get_unique_values(df: pd.DataFrame)->list:
    """
    Retrieves all the unique values in all the columns and rows of a Pandas DataFrame.

    Args:
    df: A Pandas DataFrame.

    Returns:
    A list of all the unique values in the DataFrame.
    """

    # Create a list to store all the unique values.
    unique_values = set()

    # Iterate over all the columns in the DataFrame.
    for column in df.columns:
        # Get the unique values in the column.
        unique_column_values = df[column].unique()

        # Add the unique column values to the list of all the unique values.
        unique_values.update(unique_column_values)

    # Return the list of all the unique values.
    result = [val for val in unique_values if unique_values is not None and val is not None]
    if len(result)> 0:
        return result
    else:
        return []
    
def translate_dictionary(input_dict):
    """
    Translate the given dictionary to a new format.

    Parameters:
    - input_dict (dict): Dictionary to be translated.

    Returns:
    - dict: Translated dictionary.
    """
    translated_dict = {}

    # Iterate over the keys in the input dictionary
    for key, inner_dict in input_dict.items():
        # Iterate over the items in the inner dictionary
        for species, value in inner_dict.items():
            # If the species is not in the translated dictionary, add it with an empty dictionary
            if species not in translated_dict:
                translated_dict[species] = {}

            # Add the value to the corresponding key in the translated dictionary
            translated_dict[species][key] = value

    return translated_dict
    
st.cache_data()    
def show_modified_image(image, centroids_dict:dict, show_dotpoints_overlay:bool=True):
    
    if show_dotpoints_overlay:
        modified_image = floating_marker(image, centroids_dict=centroids_dict)
    else:
        modified_image = image

    st.image(
        modified_image,
        use_column_width='always',        
        )

try:
    DATA_DIRPATH = st.session_state.get('APP', {}).get('CONFIG', {}).get('DATA_DIRPATH', None)
    current_flagged_taxons = st.session_state.get('APP', {}).get('current_flagged_taxons', [])
    
    CURRENT_FILENAME = 'seams_current_cache_data.yaml'
    CURRENT_FILEPATH = os.path.join(DATA_DIRPATH, CURRENT_FILENAME)        

    if CURRENT_FILENAME not in os.listdir(DATA_DIRPATH):
        st.warning('**Fresh current state**. Please Initializing survey data from `MENU`>`Stations initialization`**') 
        st.stop()
    else:
        do_substrates = False
        dotpoint_type = 'taxon'
        dotpoints_selected_dict = {}
    
        

        CURRENT = load_yaml(CURRENT_FILEPATH)
        st.session_state['CURRENT'] = CURRENT
        st.session_state['CURRENT_FILEPATH'] = CURRENT_FILEPATH
        if '_frame_dict' not in st.session_state['CURRENT']:
            st.session_state['CURRENT']['_frame_dict'] = {}

        if 'DOTPOINTS_TAXON_DONE' not in st.session_state['CURRENT']:
            st.session_state['CURRENT']['DOTPOINTS_TAXON_DONE'] = {}

        if 'DOTPOINTS_SUBSTRATES_DONE' not in st.session_state['CURRENT']:
            st.session_state['CURRENT']['DOTPOINTS_SUBSTRATES_DONE'] = {}

        if 'FRAME_TAXONS' not in st.session_state['CURRENT']:
            st.session_state['CURRENT']['FRAME_TAXONS'] = {}
        
        suffix = st.session_state.get('suffix', '***')

        # --------------------
        SURVEY_NAME = CURRENT.get('SURVEY_NAME', None)
        SURVEY_FILEPATH = CURRENT.get('SURVEY_FILEPATH', None)
        STATION_NAME = CURRENT.get('STATION_NAME', None)
        STATION_FILEPATH = CURRENT.get('STATION_FILEPATH', None)
        STATION_DATA = CURRENT.get('STATION_DATA', {})
        VIDEO_NAME = CURRENT.get('VIDEO_NAME', None)
        SURVEY_FILEPATH = CURRENT.get('SURVEY_FILEPATH', None)        

        # --------------------------------------------------------------------    
        frame_info = build_header()
        
                
        if STATION_DATA is not None and len(STATION_DATA) > 0:
            RANDOM_FRAMES = STATION_DATA.get('BENTHOS_INTERPRETATION').get('RANDOM_FRAMES', {})

            with st.spinner('Loading survey data...'):
                SURVEY_DATASTORE = load_datastore(survey_filepath=SURVEY_FILEPATH)
                SURVEY_DATA = SURVEY_DATASTORE.storage_strategy.data.get('APP', {})

            
            if VIDEO_NAME is None:
                st.warning('Station with incompatible video selected or survey not initialized properly. Ensure the selected station and available video has the suffix **(***)**. Go to **Menu>Survey initialization** to initialize the survey.')
                st.stop()            
            # --------------------
            show_dotpoints_overlay = st.sidebar.checkbox(
                    label='Show dotpoints overlay',
                    value=True,
                    help='Show the dotpoints overlay on the image',
                    key='show_dotpoints_overlay',
                    )
            
            frame_selected_dict, image = show_frame_select_menu(
                SURVEY_NAME=SURVEY_NAME, 
                STATION_NAME=STATION_NAME, 
                VIDEO_NAME=VIDEO_NAME, 
                RANDOM_FRAMES=RANDOM_FRAMES)
            
            FRAME_NAME = frame_selected_dict.get('FRAME_NAME', None)
            FRAME_INDEX = frame_selected_dict.get('FRAME_INDEX', None)
            frame_info.info(f'**Frame** :blue[{FRAME_INDEX} | {FRAME_NAME}]')
               
            # create bounding box polygon
            bbox = create_bounding_box(image=image)

            #TODO: CHECK ME: st.session_state.get('dotpoints_done', {})
            # IS IF DOT POINTS HAVE STARTED
            DOTPOINTS_ADVANCED_OPTIONS = show_advanced_options()
            recalculate_dotpoints = DOTPOINTS_ADVANCED_OPTIONS['recalculate_dotpoints']
                    
            if recalculate_dotpoints:
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
            # ENHANCEMENT: RE-ENABLE n-ROWS and auto select 10 random frames
            colnames = [str(i) for i in centroids_dict.keys()]

            show_modified_image(
                image, 
                centroids_dict=centroids_dict, 
                show_dotpoints_overlay=show_dotpoints_overlay)
            # --------------------------------------------------------------------


            tabFrameInterpretation, tabResults = st.tabs(['**Frame interpretation**', '**Results**'])

            with tabFrameInterpretation:

                with st.expander(label='**Substrates**', expanded=True):
                        
                    data_config_dict_substrates = {
                        'options': [s[0] for s in substrates],
                        'dotpoint_type': 'Substrates',
                        }

                    edited_df_substrates = seafloor_interpretation_data_editor(
                        data_config_dict=data_config_dict_substrates,
                        colnames=colnames,
                        num_rows='fixed',
                        )
                    subtrate_results = translate_dictionary(edited_df_substrates.to_dict())

                    st.session_state['CURRENT']['FRAME_SUBSTRATES'] = subtrate_results
                    

                with st.expander(label='**Taxons**', expanded=True):
                    # Visualize the data editor widget.
                    
                    tcol1, tcol2, tcol3, tcol4, tcol5 = st.columns([1,1,1,1,1])

                    with tcol1:                            
                        _taxa_to_add = st.selectbox(
                            label='**Taxa**',
                            options=extended_taxons_list(),
                            help='Select the **taxa** present for the selected `dotpoints` in the frame.',
                            placeholder='Select taxa',
                            key='taxa_selectbox',
                            index=None,
                            )
                        
                        
                        
                    with tcol2:
                        show_SMHI_SFLAGS_STRID = st.checkbox(
                            label='Add SMHI SFLAGS or STRID',
                            value=False,
                            help='Swedish Meteorological and Hydrological Institute **SMHI**-based species flags (SFLAGS) and Stratum ID (STRID) for the selected taxa',
                        )

                        if show_SMHI_SFLAGS_STRID and _taxa_to_add is not None and len(_taxa_to_add) > 0:
                            
                            with tcol3:                        
                                SFLAG_options = [s for s in SPECIES_FLAGS['SFLAG']]
                                SFLAG = st.selectbox(
                                    label = 'SFLAG(s)', 
                                    options=['---'] + SFLAG_options if SFLAG_options is not None  and len(SFLAG_options)>0 else [],
                                    help='Select the **taxon flags** present in the selected taxa',)
                                
                                SFLAG_string = f'SFLAG {SFLAG}' if SFLAG != '---' else ''
                                if SFLAG != '---':
                                    st.info(SPECIES_FLAGS['SFLAG'][SFLAG])
                        
                            with tcol4:
                                STRID_options = sorted([s for s in STRATUM_ID['CODE']])
                                STRID = st.selectbox(
                                    label = 'STRID - Stratum ID', 
                                    options=['---'] + STRID_options if STRID_options is not None  and len(STRID_options)>0 else [],
                                    help='Select the **taxon rid** present in the selected taxa',)

                                if STRID != '---':
                                    st.info(STRATUM_ID['CODE'][STRID])
                            # ------------------

                                STRID_string = STRID if STRID != '---' else ''

                                flag_taxa_string = f'{_taxa_to_add} {SFLAG_string} {STRID_string}'
                                _taxa_to_add = flag_taxa_string.strip()
                    # --------------
                        
                    if _taxa_to_add is not None and len(_taxa_to_add)>0 and _taxa_to_add:
                        FRAME_TAXA = {_taxa_to_add: {i : False for i in colnames}}
                    else:
                        FRAME_TAXA = {}


                    df_taxa=pd.DataFrame.from_dict(FRAME_TAXA, orient='index', columns=colnames)
                
                    # Create a Streamlit data editor widget for the DataFrame.
                    edited_df_taxa = st.data_editor(
                        df_taxa,
                        hide_index=False,
                        num_rows='fixed',
                        use_container_width=True,
                        column_config={
                            f'{i}': st.column_config.CheckboxColumn(
                                i,
                                width='auto',
                                required=True,
                                default=False,
                                )
                                for i in colnames},
                        key=f'data_editor_taxa',                        
                        )                
                    
                    taxa_results = translate_dictionary(edited_df_taxa.to_dict())

                    confirm_taxa = st.button(
                        label=f'ADD: **{_taxa_to_add}**', 
                        help=f'Confirm the **taxa** to add to the available taxa list', 
                        disabled=True if _taxa_to_add is None or len(_taxa_to_add) == 0 else False,)
                    
                    if confirm_taxa:
                        st.session_state['CURRENT']['FRAME_TAXONS'].update(taxa_results)

                    
                    df_taxons=pd.DataFrame.from_dict(st.session_state['CURRENT']['FRAME_TAXONS'], orient='index', columns=colnames)
                    
                    frame_taxons_df = st.data_editor(
                        df_taxons,
                        hide_index=False,
                        num_rows='dynamic',
                        use_container_width=True,
                        column_config={
                            f'{i}': st.column_config.CheckboxColumn(
                                i,
                                width='auto',
                                required=True,
                                default=False,
                                )
                                for i in colnames},
                        key=f'data_editor_taxons',                        
                        )
                                        
                    taxons_results = translate_dictionary(frame_taxons_df.to_dict())
                    st.session_state['CURRENT']['FRAME_TAXONS'].update(taxons_results)
                    update_station_data(st.session_state['CURRENT'], st.session_state['CURRENT_FILEPATH'])

                        

            with tabResults:
                # --------------------
                st.write(st.session_state['CURRENT'])
            
            
                
            """"

            with icol3:
                dotpoints_indexes = flatten_list(grid)
                if 'disable_extra_dotpoints_list' not in st.session_state['CURRENT']:
                    randomly_selected_dotpoints_list = random.sample(dotpoints_indexes, 10)
                    disable_extra_dotpoints_list = [i for i in dotpoints_indexes if i not in randomly_selected_dotpoints_list]
                    st.session_state['CURRENT']['disable_extra_dotpoints_list'] = disable_extra_dotpoints_list
                else:
                    disable_extra_dotpoints_list = st.session_state['CURRENT']['disable_extra_dotpoints_list']

                # ------------------
                taxsub1, taxsub2 = st.columns([1,2])
                with taxsub1:
                    st.markdown('**Taxons**')
                with taxsub2:
                    do_substrates = st.toggle(label='**Substrates**', key='do_substrates', value=False)
                
                reenable_dotpoints_taxon = False
                if not reenable_dotpoints_taxon:
                    DOTPOINTS_TAXON_DONE = [str(d) for d in st.session_state['CURRENT']['DOTPOINTS_TAXON_DONE'].keys()]
                else:
                    DOTPOINTS_TAXON_DONE = []

                reenable_dotpoints_substrate = False
                if not reenable_dotpoints_substrate:
                    DOTPOINTS_SUBSTRATES_DONE = [str(d) for d in st.session_state['CURRENT']['DOTPOINTS_SUBSTRATES_DONE'].keys()]
                else:
                    DOTPOINTS_SUBSTRATES_DONE = []  

                
                # ------------------
                if do_substrates is False:
                    dotpoint_type = 'taxon'
                    disable_dotpoints = disable_extra_dotpoints_list + DOTPOINTS_TAXON_DONE                
                else:
                    dotpoint_type = 'substrate'
                    disable_dotpoints = disable_extra_dotpoints_list + DOTPOINTS_SUBSTRATES_DONE
                # ------------------
                dotpoints_selected_dict[dotpoint_type] = display_grid(
                        grid=grid, disable_dotpoints=disable_dotpoints, dotpoint_type=dotpoint_type)
                
                if dotpoint_type == 'taxon':
                    st.session_state['CURRENT']['_frame_dict'][dotpoint_type] = taxons_interpretation(SPECIES_FLAGS=SPECIES_FLAGS, STRATUM_ID=STRATUM_ID)
                elif dotpoint_type == 'substrate':
                    st.session_state['CURRENT']['_frame_dict'][dotpoint_type] = substrates_interpretation(substrates=substrates)

            # --------------------
            st.write(st.session_state['CURRENT'].get('_frame_dict', {}))

            # HERE FRAME INTERPRETATION
            for dotpoint_selected in dotpoints_selected_dict[dotpoint_type]:
                if dotpoint_type not in st.session_state['CURRENT']:
                    st.session_state['CURRENT'][dotpoint_type] = {}
                else:
                    st.session_state['CURRENT'][dotpoint_type].update({dotpoint_selected: st.session_state['CURRENT']['_frame_dict'][dotpoint_type]})
            
            st.write(st.session_state['CURRENT'][dotpoint_type])
            

            # --------------------

            if 'FRAME_NAME' in st.session_state:
                FRAME_NAME = st.session_state['FRAME_NAME']
                st.session_state['CURRENT']['FRAME_NAME'] = FRAME_NAME
                update_station_data(st.session_state['CURRENT'], st.session_state['CURRENT_FILEPATH'])
            else:
                FRAME_NAME = None
            """

            

            #df = dict_to_dataframe(FRAME_INTERPRETATION['DOTPOINTS'])
            #if RANDOM_FRAMES is not None and len(RANDOM_FRAMES) > 0:
            #    df = dict_to_dataframe(RANDOM_FRAMES)
            #st.write(df)

            #show_tabs(                          
            #    SURVEY_FILEPATH=SURVEY_FILEPATH,                
            #    STATION_DATA=STATION_DATA,
            #    FRAME_NAME=FRAME_NAME,       
            #)
        else:
            st.warning('Survey not initialized. Go to **Menu>Survey initialization** to initialize the survey.')
            

except Exception as e:
    trace_error = traceback.print_exc()
    if trace_error is None:
        trace_error= ''
    else:        
        st.error(f'**Benthos interpretation exception:** {trace_error} {e} | **Refresh the app and try again**')
    