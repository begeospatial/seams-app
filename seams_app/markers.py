import numpy as np
from PIL import Image
from cv2 import drawMarker, putText, LINE_AA, MARKER_CROSS, FONT_HERSHEY_SIMPLEX
from shapely import Polygon, Point
import random
from dataclasses import dataclass, field
from itertools import count
from typing import List
from streamlit import cache_data



def floating_marker(image, centroids_dict: dict[int, Point]):
    """
    Overlays cross markers at specified centroid positions on the given image.

    Parameters:
    -----------
    image : Image
        An image in which to overlay the markers.
        
    centroids_dict : dict[int, Point]
        A dictionary where keys represent unique identifiers (IDs) for each centroid 
        and values are Point objects specifying the x and y coordinates of each centroid.

    Returns:
    --------
    Image:
        The modified image with overlaid markers.

    Notes:
    -----
    - This function uses OpenCV functions like drawMarker and putText to achieve its 
      functionality. Therefore, it requires the OpenCV library to be imported and available.
    - The function works with images provided as PIL Image objects and returns a 
      modified image in the same format.
    - The markers are colored green, but this can be changed by adjusting the 
      `marker_color` variable.
    """
    # Convert the image to a NumPy array

    image = np.array(image)   
    marker_color = (0,255,0)

    for id, centroid in centroids_dict.items():
        
        x = int(centroid.x)
        y = int(centroid.y)
        drawMarker(image, (x, y), marker_color, markerType= MARKER_CROSS, 
    markerSize=100, thickness=2, line_type= LINE_AA)

        font = FONT_HERSHEY_SIMPLEX  # normal size sans-serif font
        text_origin = (x-50, y + 50)
        fontScale = 1
        fontThickness = 2

        putText(
            image, 
            str(id), 
            text_origin, 
            font, 
            fontScale, 
            marker_color, 
            fontThickness, 
            LINE_AA )

    # convert the image back to an image object and return it
    return Image.fromarray(image)


def create_bounding_box(image: Image.Image) -> Polygon:
    """Creates a shapely polygon of the bounding box of an image

    Args:
        image (Image.Image): Pil image object

    Returns:
        Polygon : shapely bounding box
    """

    width, height = image.size
    return Polygon([(0, 0), (width, 0), (width, height), (0, height)])


def add_random_noise_to_polygon_centroid(polygon:Polygon, noise_percent: float)->Point:
    """
    Introduces random noise to the centroid of a polygon, moving its position slightly.

    Args:
        polygon (Polygon): The shapely polygon for which the centroid's position needs to be perturbed.
        noise_percent (float): A percentage value between 0 and 1 indicating the degree of noise to introduce. A higher value will result in a larger perturbation of the centroid's position.

    Returns:
        Point: A new shapely Point object representing the perturbed centroid of the provided polygon.
    
    Note:
        The noise introduced is proportional to the distance between the centroid and the minimum x and y values of the polygon's bounding box. The perturbation is random, so multiple calls to the function for the same polygon and noise_percent will likely return different results.
    """

    min_x, min_y, _, _ = polygon.bounds
    centroid = polygon.centroid

    if noise_percent is not None and (noise_percent > 0 and noise_percent <= 1.0):
        # calculate the noise as percentage of the distance in x and y from the centroid
        noise_x = noise_percent * (centroid.x - min_x)
        noise_y = noise_percent * (centroid.y - min_y)
        # Add random salt and pepper noise to the centroid
        centroid = Point(centroid.x + random.uniform(-noise_x, noise_x), centroid.y + random.uniform(-noise_y, noise_y))
    
    
    return centroid


def markers_grid(
    bbox:Polygon, 
    n_rows:int = 3, 
    enable_random:bool = False, 
    noise_percent: float = 0.1, 
 
     )->list:
    
    """
    Divides a bounding box polygon into a grid with a specified number of rows. Each row is divided into either 3 or 4 columns, 
    depending on whether the row index is even or odd, respectively. The centroids of these columns are then calculated.

    Args:
        bbox (Polygon): 
            The bounding box as a shapely Polygon object that will be divided into rows and columns.
        
        n_rows (int, optional): 
            Number of rows to divide the bounding box into. Defaults to 3.
        
        enable_random (bool, optional): 
            If set to True, adds random noise to the location of the centroids. This can be useful if one wishes to slightly 
            perturb the centroids' locations for a more randomized or natural appearance. Defaults to False.
        
        noise_percent (float, optional): 
            Amount of random noise to be added to the centroid's position, expressed as a percentage. 
            Only applies if enable_random is True. A higher value will result in a larger perturbation of the centroids' 
            positions. The value should be in the range [0.1, 1.0]. Defaults to 0.1.

    Returns:
        list: 
            A list of shapely Point objects representing the centroids of the columns.

    Notes:
        The function operates by first dividing the bounding box into rows. Each row is then divided into columns: even-indexed 
        rows are divided into 3 columns, and odd-indexed rows are divided into 4 columns. The centroids of these columns are 
        then computed and optionally perturbed with random noise, if enable_random is set to True.
    """

    # Calculate the width and height of the polygon
    min_x, min_y, max_x, max_y = bbox.bounds
    row_width = max_x - min_x 
    height = max_y - min_y

    # Divide the polygon into rows
    row_height = height / n_rows
    rows = []

    for i in range(n_rows):
        y0 = min_y + i * row_height
        y1 = y0 + row_height
        rows.append(Polygon([(min_x, y0), (max_x, y0), (max_x, y1), (min_x, y1)]))

    # Divide each row into columns and calculate the centroids
    centroids = []
    
    for i, row in enumerate(rows):
        min_x, min_y, max_x, max_y = row.bounds

        if i % 2 == 0:
            # Even row: divide into 3
            col_width = row_width / 3
            for j in range(3):
                x0 = min_x + j * col_width
                x1 = x0 + col_width
                col = Polygon([(x0, min_y), (x1, min_y), (x1, max_y), (x0, max_y)])
                
                if enable_random:
                    centroid = add_random_noise_to_polygon_centroid(polygon=col, noise_percent=noise_percent)
                else:
                    centroid = col.centroid

                centroids.append(centroid)
        else:
            # Odd row: divide into 4
            col_width = row_width / 4
            for j in range(4):
                x0 = min_x + j * col_width
                x1 = x0 + col_width
                col = Polygon([(x0, min_y), (x1, min_y), (x1, max_y), (x0, max_y)])
                
                if enable_random:
                    centroid = add_random_noise_to_polygon_centroid(polygon=col, noise_percent=noise_percent)
                else:
                    centroid = col.centroid

                centroids.append(centroid)

    return centroids    


@dataclass(kw_only=True)
class DotPoint:
    """
    Represents a specific point on a frame, primarily used to mark a location of interest in an image or video frame.
    
    Attributes:
        frame_id (int): 
            Identifier for the frame where the DotPoint is located. This could correspond to a specific image or video frame number.
        
        x (float): 
            Horizontal coordinate of the DotPoint within the frame.
            
        y (float): 
            Vertical coordinate of the DotPoint within the frame.
            
        id (int): 
            A unique identifier for the DotPoint. This can be used to reference or track the point across multiple frames or datasets.
            
        taxons (list[str], optional): 
            A list of taxonomic classifications or species names associated with the DotPoint. Useful for marking specific organisms 
            or entities within an image. By default, this list is empty.
            
        substrates (list[str], optional): 
            A list of substrate types or categories associated with the DotPoint. Substrates refer to the underlying surface or 
            material upon which organisms live or grow. By default, this list is empty.
    """
    frame_id: int
    x: float
    y: float
    id: int 
    taxons: list[str] = field(default_factory=list)
    substrates: list[str] = field(default_factory=list)


def dotpoints_grid(filepath:str,
    n_rows = 3,
    enable_random = False,
    noise_percent = 0.0,
    frame_id: int = 1,
    ):
    """
    Creates a grid of dot points on an image and returns the modified image.

    Args:
        filepath (str): 
            Path to the image file on which dotpoints will be created.

        n_rows (int, optional): 
            Number of rows to divide the bounding box into for placing dotpoints. Defaults to 3.

        enable_random (bool, optional): 
            If set to `True`, random noise is added to the location of the centroids of the grid cells, which in turn
            perturbs the location of the dotpoints. This can be useful to avoid uniformity. Defaults to False.

        noise_percent (float, optional): 
            A float value between 0 and 1 indicating the amount of random noise (in percentage) to be added to the location 
            of the centroids of the grid cells. Only effective if `enable_random` is set to True. Defaults to 0.0.

        frame_id (int, optional): 
            Identifier for the frame or image where the dotpoints are located. This is useful when working with a sequence
            of frames or images. Defaults to 1.

    Returns:
        Image: 
            The modified image with dotpoints placed in a grid format.

    Note:
        This function requires the PIL (Pillow) library for image processing and the shapely library for geometry operations.
    """

    dotpoints = []
    image = Image.open(filepath)       
    # create bounding box polygon
    bbox = create_bounding_box(image=image)
    centroids = markers_grid(bbox, n_rows=n_rows, enable_random=enable_random, noise_percent=noise_percent)

    for i, centroid in enumerate(centroids):
        dotpoint = DotPoint(frame_id=frame_id, x=int(centroid.x), y=int(centroid.y), id=i+1)
        dotpoints.append(dotpoint)
                
    # Add the floating button to the image
    modified_image = floating_marker(image, dotpoints=dotpoints)
            
    return modified_image
