import numpy as np
from PIL import Image
from cv2 import drawMarker, putText, LINE_AA, MARKER_CROSS, FONT_HERSHEY_SIMPLEX
from shapely import Polygon, Point
import random
from dataclasses import dataclass, field
from itertools import count
from typing import List



def floating_marker(image, centroids_dict: dict[int, Point]):
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
    """Adds a random noise 
    
    Args:
        centroid (Point): _description_
        noise_percent (float, optional): _description_. Defaults to None.
    """

    min_x, min_y, _, _ = polygon.bounds
    centroid = polygon.centroid

    if noise_percent is not None and (noise_percent > 0 and noise_percent <= 1.0):
        # calculate the noise as percentage of the distance in x and y from the centroid
        noise_x = noise_percent * (centroid.x - min_x)
        noise_y = noise_percent * (centroid.y - min_y)
        # Add random salt and pepper noise to the centroid
        centroid = Point(centroid.x + random.uniform(-noise_x, noise_x), centroid.y + random.uniform(-noise_y, noise_y))
    #TODO: Room for improvement to raise and error `if enable_random` and no noise was added.
    
    return centroid


def markers_grid(
    bbox:Polygon, 
    n_rows:int = 3, 
    enable_random:bool = False, 
    noise_percent: float = 0.1, 
 
     )->list:
    """Divides a bounding box polygon into a grid with `n_rows`. Each row is divided into columns
    and the centroids of each new column are calculated.

    Args:
        bbox (Polygon): Bounding box, shapely polygon
        n_rows (int, optional): Number of Rows to divide the bounding box. Defaults to 3.
        enable_random (bool, optional): If `True` random noise is added to the location of the centroids. Defaults to False.
        percentage_noise (float, optional): Amount of `salt and pepper` random noise to be generated in percentage [0.1, 1.0]. Defaults to 0.8.
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
