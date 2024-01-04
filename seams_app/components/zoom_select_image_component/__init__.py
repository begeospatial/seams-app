import os
import io

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

import numpy as np
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry
from seaborn import color_palette

# Create a _RELEASE constant. We'll set this to False while we're developing
# the component, and True when we're ready to package and distribute it.
# (This is, of course, optional - there are innumerable ways to manage your
# release process.)
_RELEASE = True

# Declare a Streamlit component. `declare_component` returns a function
# that is used to create instances of the component. We're naming this
# function "_component_func", with an underscore prefix, because we don't want
# to expose it directly to users. Instead, we will create a custom wrapper
# function, below, that will serve as our component's public API.

# It's worth noting that this call to `declare_component` is the
# *only thing* you need to do to create the binding between Streamlit and
# your component frontend. Everything else we do in this file is simply a
# best practice.

if not _RELEASE:
    _component_func = components.declare_component(
        "zoom_select_image_component",
        # Pass `url` here to tell Streamlit that the component will be served
        # by the local dev server that you run via `npm run start`.
        # (This is useful while your component is in development.)
        url="http://localhost:3001",
    )
else:
    # When we're distributing a production version of the component, we'll
    # replace the `url` param with `path`, and point it to the component's
    # build directory:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("zoom_select_image_component", path=build_dir)

@st.cache_resource
def load_image_as_pil(image_path: str):
    return Image.open(image_path)

@st.cache_data
def create_url_to_image(image_path: str):
    image = load_image_as_pil(image_path)
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='png')
    url = st.runtime.get_instance().media_file_mgr.add(image_bytes.getvalue(), 'application/png', image_path)
    return url

@st.cache_resource
def load_sa_model(sa_checkpoint_path: str):
    sam = sam_model_registry["default"](checkpoint=sa_checkpoint_path)
    return SamAutomaticMaskGenerator(sam)

@st.cache_data
def crop_and_generate_annotations(sa_checkpoint, image_path, left, top, width, height):
    mask_generator = load_sa_model(sa_checkpoint)
    pil_image = load_image_as_pil(image_path)
    image_cropped = pil_image.crop((left, top, left + width, top + height))
    image_cropped_np = np.array(image_cropped)
    return image_cropped_np, mask_generator.generate(image_cropped_np)

def zoom_select_image_component(image_path: str, sa_checkpoint_path: str, rectangle_width=500, rectangle_height=500):
    """Create a new instance of "zoom_select_image_component".

    Parameters
    ----------
    image_path: str
        A path to an image on the filesystem.
    sa_checkpoint_path: str
        A path to a SegmentAnything checkpoint (see https://github.com/facebookresearch/segment-anything for
        instructions on where to obtain this file).
    rectangle_width: number
        The width of the zoom rectangle in image pixels.
    rectangle_height: number
        The height of the zoom rectangle in image pixels.


    Returns
    -------
    array
        An array of selected rectangles.
        Each rectangle is a dictionary with keys 'left', 'top', 'width', 'height' giving the position and size
        of the rectangle in pixels relative the top left corner of the image.
        For rectangles with annotation enabled, there is also a key 'annotations' containing the results
        of running the segment_anything model against the part of the image cropped by the rectangle.
    """

    image_url = create_url_to_image(image_path)
    rectangles = _component_func(image_url=image_url, rectangle_width=rectangle_width, rectangle_height=rectangle_height, default=[])

    for rectangle in rectangles:
        left = rectangle['left'] = round(rectangle['left'])
        top = rectangle['top'] = round(rectangle['top'])
        width = rectangle['width'] = round(rectangle['width'])
        height = rectangle['height'] = round(rectangle['height'])

        if not rectangle['shouldAnnotate']:
            continue

        image_cropped, annotations = crop_and_generate_annotations(sa_checkpoint_path, image_path, left, top, width, height)
        rectangle['annotations'] = annotations

        image_cropped = image_cropped/255
        masks = np.zeros_like(image_cropped)

        sorted_annotations = sorted(annotations, key=(lambda x: -x['area']))
        colors = color_palette("husl", len(sorted_annotations))

        for color, annotation in zip(colors, sorted_annotations):
            # the key 'segmentation' contains a boolean 2D array (HW) that is true on the image pixels that are
            # contained in the segmentation
            m = annotation['segmentation']
            # we combine all the segmmentations as an image in a 3D array (HWC)
            masks[m] += color

        with st.sidebar:
            blended_image = 0.4 * image_cropped + 0.6 * masks
            st.image(blended_image, clamp=True, use_column_width='always')

    return rectangles
