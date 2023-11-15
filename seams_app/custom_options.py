import streamlit as st

def SGU_custom_options(FRAME_INTERPRETATION:dict)->dict:
    """
    Provides a Streamlit-based UI for the user to select and input custom options for a survey frame.

    Options Included:
    -----------------
    1. `Limecola baltica shell`: A select box to choose the amount of Limecola baltica shell presence.
        - Options: 'no', 'förekommande', 'måttligt', 'rikligt'.
        - Corresponding Values: 0, 1, 2, 3.
    2. `Krypspår`: A select box to choose the prevalence of tracks (Krypspår).
        - Options: 'no', 'förekommande', 'måttligt > 10%', 'rikligt > 50%'.
        - Corresponding Values: 0, 1, 2, 3.
    3. `Sandwave (cm)`: A numeric input field to enter the height of the sandwaves in centimeters.
        - Range: -1.0 to 500.0 cm.
    4. `flags`: A multi-select box to choose any flags that might apply to the frame.
        - Options: 'Dålig bildkvalitet', 'Dålig sikt/vattenkvalitet'.
    5. `Interpretation Notes`: A text area for the user to input any additional notes or comments about the frame.

    Returns:
    -------
    dict:
        A dictionary containing the user's selections and inputs for each option.

    Notes:
    -----
    - The function is designed for integration within a Streamlit application.
    - The dictionary keys are in English for programmatic consistency, while the user-facing labels are in Swedish.
    """
    frame_flags = None

    col1, col2 = st.columns([1,1])
    with col1:
        shells_options = {'no':0, 'förekommande':1, 'måttligt':2,'rikligt':3}
        key_shells = FRAME_INTERPRETATION.get('CUSTOM_OPTIONS', {}).get('shells', 'no')
        shells = st.selectbox(
            label='Limecola baltica shell', 
            options=shells_options,            
            index=shells_options.get(key_shells, 0)            
             )
        
        krypspar_options={'no':0, 'förekommande':1, 'måttligt > 10%':2,'rikligt > 50%':3}
        key_krypspar =  FRAME_INTERPRETATION.get('CUSTOM_OPTIONS', {}).get('krypspar', 'no')
        krypspar = st.selectbox(
            label='Krypspår', 
            options={'no':0, 'förekommande':1, 'måttligt > 10%':2,'rikligt > 50%':3},
            index=krypspar_options.get(key_krypspar, 0)
            )
        
        sandwave = st.number_input(
            label='Sandwave (cm)', 
            min_value=-1.0, 
            max_value=500.0, 
            step=1.0, 
            value=FRAME_INTERPRETATION.get('CUSTOM_OPTIONS', {}).get('sandwave', -1.0)
            )
    with col2:
        if 'CUSTOM_OPTIONS' in FRAME_INTERPRETATION:

            frame_flags_options = {'Bra bildkvalitet': 0, 'Dålig bildkvalitet': 1, 'Dålig sikt/vattenkvalitet':2}
            key_flag = FRAME_INTERPRETATION.get('CUSTOM_OPTIONS', {}).get('frame_flags', 'Bra bildkvalitet')
            
            frame_flags = st.selectbox(
                label = 'flags', 
                options=frame_flags_options,
                placeholder='Select quality flags',
                index=frame_flags_options.get(key_flag, 0),
                )
                    
                
        fieldNotes = st.text_area(
            label='Interpretation Notes', 
            help='Use this field to add notes about the frame. This field is not mandatory.',
            value=FRAME_INTERPRETATION.get('CUSTOM_OPTIONS', {}).get('fieldNotes', '')            
            )

    overall_in_frame = {
        'shells': shells,
        'krypspår': krypspar,
        'sandwave': sandwave,
        'frame_flags': frame_flags,
        'fieldNotes': fieldNotes.strip()
        }
    return overall_in_frame