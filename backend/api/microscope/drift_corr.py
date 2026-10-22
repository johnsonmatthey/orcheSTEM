import cv2
import numpy as np
import scipy.ndimage as ndimgs

def drift_calc(ref_img_in, current_img, max_shift_pixel=5, window_type = 'hanning'):
    """
    Returns the distance in pixels that the object in the image has moved relative to the ref image,
    using phase correlation.
    returns (shift_x, shift_y), response

    NOTE that the shift returned is the direction the object has moved. 
    To follow the object, use this shift directly, to counteract the drift, use -1*shift.
    """
    def _hanning(img: np.ndarray) -> np.ndarray:
        m, n = img.shape
        return img * np.outer(np.hanning(m), np.hanning(n))

    def _sobel(img: np.ndarray) -> np.ndarray:
        sx = ndimgs.sobel(img, axis=0, mode="constant")
        sy = ndimgs.sobel(img, axis=1, mode="constant")
        return np.hypot(sx, sy)

    def _median(img: np.ndarray) -> np.ndarray:
        return ndimgs.median_filter(img, size=3)

    if window_type == 'hanning':
        window_func = _hanning
    elif window_type == 'sobel':
        window_func = _sobel
    else:
        window_func = _median
    # Window the images to reduce edge effects
    ref_img_in = window_func(ref_img_in)
    current_img = window_func(current_img)

    # Use phase correlation to find the shift
    ref_img = cv2.normalize(ref_img_in, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    current_img = cv2.normalize(current_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
  
    shift, response = cv2.phaseCorrelate(
        np.float32(ref_img), 
        np.float32(current_img)
    )

    # THIS is the direction the object has moved. 
    # To follow the object, *1, to counteract the drift, *-1.
    shift = np.array(shift)  #np.round(shift) * -1 # To do reverse shift!
    shift = np.sign(shift) * np.minimum(np.abs(shift), max_shift_pixel)
    print("phase cross:" ,shift, response)
    return shift, response

