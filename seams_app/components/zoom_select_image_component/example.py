import os
from os import path
import streamlit as st
from zoom_select_image_component import zoom_select_image_component

# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run zoom_select_image_component/example.py`

st.subheader("Image select")
st.write(path.dirname(__file__))
rectangles = zoom_select_image_component(
  path.join(path.dirname(__file__), 'gosi_station_01_SEAMS__video_station-01_frame__000128_sec.png'),
  path.join(path.dirname(__file__) + '/sam_vit_h_4b8939.pth'),
)
