import numpy as np
import cv2

def threshold_multi_range(image: np.ndarray, thresh_range:list)->np.ndarray:
    """
    thresholds the image between a range chosen by the user

    Args:
        image (np.ndarray): image array 
        thresh_range (list): threshold ranges   

    Returns:
        np.ndarray: integer mask of the threshold range region
    """
    mask1 = (image >= thresh_range[0]).astype('uint8')
    mask2 = (image <= thresh_range[1]).astype('uint8')
    mask = ((mask1 + mask2) == 2).astype('uint8')
    return mask