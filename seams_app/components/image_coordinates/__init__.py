import streamlit.components.v1 as components

import base64
from io import BytesIO
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image


_component_func = components.declare_component(
    "image_coordinates", path="./seams_app/components/image_coordinates/frontend"
)


def image_coordinates(source: str | Path | np.ndarray | object,
    height: int | None = None,
    width: int | None = None,
    key: str | None = None,
    ):

    """
    Take an image source and return the coordinates of the image clicked

    Parameters
    ----------
    source : str | Path | object
        The image source
    height : int | None
        The height of the image. If None, the height will be the original height
    width : int | None
        The width of the image. If None, the width will be the original width

    modified from source: https://raw.githubusercontent.com/blackary/streamlit-image-coordinates/main/src/streamlit_image_coordinates/frontend/main.js
    """

    if isinstance(source, Path) or isinstance(source, str):
        if not str(source).startswith("http"):
            content = Path(source).read_bytes()
            src = "data:image/png;base64," + base64.b64encode(content).decode("utf-8")
        else:
            src = str(source)
    elif hasattr(source, "save"):
        buffered = BytesIO()
        source.save(buffered, format="PNG")  # type: ignore
        src = "data:image/png;base64,"
        src += base64.b64encode(buffered.getvalue()).decode("utf-8")  # type: ignore
    elif isinstance(source, np.ndarray):
        image = Image.fromarray(source)
        buffered = BytesIO()
        image.save(buffered, format="PNG")  # type: ignore
        src = "data:image/png;base64,"
        src += base64.b64encode(buffered.getvalue()).decode("utf-8")  # type: ignore
    else:
        raise ValueError(
            "Must pass a string, Path, numpy array or object with a save method"
        )

    component_value = _component_func(
        src=src,
        height=height,
        width=width,
        key=key,
    )


    return component_value


