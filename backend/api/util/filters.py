import cv2
import numpy as np

def median(image:np.ndarray, ks:float)->np.ndarray:
    """
    blurs the image using a median filter from opencv

    Args:
        image (np.ndarray): image array
        ks (float): kernel size 

    Returns:
        np.ndarray: filtered image
    """
    ks = int(np.ceil(ks) // 2 * 2 + 1) # ensures that the kernel is rounded to nearest odd integer
    return(cv2.medianBlur(image,ks))
