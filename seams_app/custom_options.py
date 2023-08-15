import streamlit as st

def SGU_custom_options()->dict:
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