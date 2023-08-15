import numpy as np
from cv2 import imwrite,  putText, FONT_HERSHEY_SIMPLEX, rectangle
from dataclasses import dataclass, field
import pickle


@dataclass
class DotPoint:
    """
        Represents a point with various attributes.

        Class Attributes:
        - instance_count (int): Tracks the number of DotPoint instances created.
        - instances (dict): Stores created DotPoint instances with their ID as the key.

        Instance Attributes:
        - ID (int): The instance number for the DotPoint ranging between 1 and 10 (inclusive).
        - DOTPOINT_ID (int): A unique reference ID given to the class.
        - frame_x_coord (int): The x-coordinate in the frame.
        - frame_y_coord (int): The y-coordinate in the frame.
        - TAXONS (set): A set of taxons associated with the point.
        - SUBSTRATE (str): The substrate type associated with the point.
        - boundary_width (int): The width of the boundary box centered around the point.
        - boundary_height (int): The height of the boundary box centered around the point.

        Methods:
        - reset_counter: Resets the instance_count and clears the instances dictionary.
        - export_attributes: Returns the attributes of the instance as a dictionary.
        - reset_by_dotpoint_id: Resets the attributes of an instance given its DOTPOINT_ID.
        - draw_boundary_on_image: Draws a rectangle boundary centered at the point on an image.
        - clip_image: Clips the image based on the boundary box of the point.
        - boundary_as_polygon: Exports the boundary box as a list of coordinates forming a polygon.
        - save_clipped_image: Saves the clipped image as PNG or JPEG based on the boundary box.

        Notes:
        - boundary box for defaults to 224x224 pixels as in the CoralNet Point Intercept Method.
        - source: https://coralnet.ucsd.edu/blog/a-new-deep-learning-engine-for-coralnet/

        Examples:
        ```python
        # Test the dataclass and reset method
        point1 = DotPoint(1, 10, 20, {"taxon1", "taxon2"}, "rock")
        point2 = DotPoint(2, 30, 40)
        point3 = DotPoint(3, 50, 60, {"taxon3"})

        img = cv2.imread('path_to_your_image.jpg')
        point1.draw_boundary_on_image(img)
        clipped_img = point1.clip_image(img)
        polygon = point1.boundary_as_polygon()
        point1.save_clipped_image(img, "clipped_point1")
        ```
    """
    DOTPOINT_ID: int
    frame_x_coord: int
    frame_y_coord: int
    TAXONS: set = field(default_factory=set)
    SUBSTRATE: str = ""
    ID: int = field(init=False)
    
    instance_count = 0
    instances = {}
    dotpoint_id_instances = {}

    # boundary box for defaults to 224x224 pixels as in the CoralNet Point Intercept Method.
    # source: https://coralnet.ucsd.edu/blog/a-new-deep-learning-engine-for-coralnet/
    boundary_width: int = 224
    boundary_height: int = 224

    def __post_init__(self):
        """
        Post-initialization method for dataclasses. Initializes the ID.
        """
        DotPoint.instance_count += 1
        if DotPoint.instance_count > 10:
            raise ValueError("Only 10 instances of DotPoint can be created.")
            
        self.ID = DotPoint.instance_count
        DotPoint.instances[self.ID] = self
        DotPoint.dotpoint_id_instances[self.DOTPOINT_ID] = self

    @classmethod
    def reset_counter(cls):
        """
        Resets the instance_count to 0 and clears the instances dictionary.
        """
        cls.instance_count = 0
        cls.instances = {}
        cls.dotpoint_id_instances = {}

    def export_attributes(self):
        """
        Returns the attributes of the instance in a dictionary format.
        
        Returns:
        - dict: A dictionary containing the attributes of the instance.
        """
        return {
            self.ID: {
                "ID": self.ID,
                "DOTPOINT_ID": self.DOTPOINT_ID,
                "frame_x_coord": self.frame_x_coord,
                "frame_y_coord": self.frame_y_coord,
                "TAXONS": self.TAXONS,
                "SUBSTRATE": self.SUBSTRATE
            }
        }

    @classmethod
    def reset_by_dotpoint_id(cls, dotpoint_id):
        """
        Resets the attributes of an instance given its DOTPOINT_ID.
        
        Args:
        - dotpoint_id (int): The DOTPOINT_ID of the instance to reset.
        
        Returns:
        - None
        """
        instance = cls.dotpoint_id_instances.get(dotpoint_id)
        if not instance:
            raise ValueError(f"No instance found with DOTPOINT_ID {dotpoint_id}")
        
        instance.frame_x_coord = 0
        instance.frame_y_coord = 0
        instance.TAXONS.clear()
        instance.SUBSTRATE = ""

    def draw_boundary_on_image(self, img: np.ndarray, color=(255,0,0)) -> np.ndarray:
        # For violet: color=(255, 0, 255)
        x, y = self.frame_x_coord, self.frame_y_coord
        width, height = self.boundary_width, self.boundary_height

        start_x = x - width // 2
        start_y = y - height // 2
        end_x = start_x + width
        end_y = start_y + height
        
        rectangle(img, (start_x, start_y), (end_x, end_y), color, 2)
        putText(img, str(self.DOTPOINT_ID), (start_x, start_y - 10), FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        return img

    def clip_image(self, img: np.ndarray) -> np.ndarray:
        x, y = self.frame_x_coord, self.frame_y_coord
        width, height = self.boundary_width, self.boundary_height

        start_x = x - width // 2
        start_y = y - height // 2
        end_x = start_x + width
        end_y = start_y + height

        clipped_img = img[start_y:end_y, start_x:end_x]
        return clipped_img

    def boundary_as_polygon(self) -> list:
        x, y = self.frame_x_coord, self.frame_y_coord
        width, height = self.boundary_width, self.boundary_height

        start_x = x - width // 2
        start_y = y - height // 2
        end_x = start_x + width
        end_y = start_y + height

        return [(start_x, start_y), (end_x, start_y), (end_x, end_y), (start_x, end_y)]

    def save_clipped_image(self, img: np.ndarray, file_name: str, file_type: str = "png"):
        if file_type not in ["png", "jpeg"]:
            raise ValueError("Supported file types are 'png' and 'jpeg'")

        clipped_img = self.clip_image(img)
        if file_type == "png":
            imwrite(f"{file_name}.png", clipped_img)
        else:
            imwrite(f"{file_name}.jpeg", clipped_img)

    def serialize_to_variable(self) -> bytes:
        """
        Serializes the object attributes to a bytes object.
        
        Returns:
        - bytes: A bytes object containing the serialized attributes of the instance.
        """
        return pickle.dumps(self.export_attributes())

    @staticmethod
    def deserialize_from_variable(serialized_data: bytes) -> dict:
        """
        Deserializes the object attributes from a bytes object.
        
        Args:
        - serialized_data (bytes): A bytes object containing the serialized attributes.
        
        Returns:
        - dict: A dictionary containing the deserialized attributes of the instance.
        """
        return pickle.loads(serialized_data)
    
    def serialize_to_pickle(self, file_name: str):
        """
        Serializes the object attributes to a pickle file.
        
        Args:
        - file_name (str): The name of the pickle file where the serialized data will be stored.
        
        Returns:
        - None
        """
        with open(file_name, 'wb') as f:
            pickle.dump(self.export_attributes(), f)

    @staticmethod
    def deserialize_from_pickle(file_name: str) -> dict:
        """
        Deserializes the object attributes from a pickle file.
        
        Args:
        - file_name (str): The name of the pickle file from where the serialized data will be read.
        
        Returns:
        - dict: A dictionary containing the deserialized attributes of the instance.
        """
        with open(file_name, 'rb') as f:
            data = pickle.load(f)
        return data

