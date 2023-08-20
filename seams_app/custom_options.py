import streamlit as st

def SGU_custom_options()->dict:
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
    shells = st.selectbox(label='Limecola baltica shell', options={'no':0, 'förekommande':1, 'måttligt':2,'rikligt':3})
    krypspar = st.selectbox(label='Krypspår', options={'no':0, 'förekommande':1, 'måttligt > 10%':2,'rikligt > 50%':3})
    sandwave = st.number_input(label='Sandwave (cm)',min_value=-1.0, max_value=500.0, step=1.0, value=-1.0)
    frame_flags = st.multiselect(label = 'flags', options=['Dålig bildkvalitet', 'Dålig sikt/vattenkvalitet'])
    
    fieldNotes = st.text_area(label='Interpretation Notes', help='Use this field to add notes about the frame. This field is not mandatory.')

    overall_in_frame = {
        'shells': shells,
        'krypspår': krypspar,
        'sandwave': sandwave,
        'frame_flags': frame_flags,
        'fieldNotes': fieldNotes
        }
    return overall_in_frame