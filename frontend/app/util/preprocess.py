import numpy as np
import cv2

def detect_and_remove_hot_pixels(data, median_ksize=3, z_thresh=8.0, min_abs_threshold=50.0, iterations=2):
    if median_ksize % 2 == 0 or median_ksize < 3:
        raise ValueError("median_ksize must be odd and >= 3")

    cleaned = np.asarray(data).copy()
    hot_mask_total = np.zeros_like(cleaned, dtype=bool)
    threshold_last = None
    mad_last = None
    sigma_last = None

    for _ in range(iterations):
        src_float = cleaned.astype(np.float32)
        local_med = cv2.medianBlur(cleaned, median_ksize).astype(np.float32)
        residual = src_float - local_med

        med_res = np.median(residual)
        mad = np.median(np.abs(residual - med_res))
        sigma = 1.4826 * mad if mad > 0 else 0.0
        threshold = max(min_abs_threshold, z_thresh * sigma)

        hot_mask = residual > threshold
        if not np.any(hot_mask):
            threshold_last, mad_last, sigma_last = threshold, mad, sigma
            break

        cleaned[hot_mask] = local_med[hot_mask].astype(cleaned.dtype)
        hot_mask_total |= hot_mask
        threshold_last, mad_last, sigma_last = threshold, mad, sigma

    diagnostics = {
        "mad": float(mad_last if mad_last is not None else 0.0),
        "sigma": float(sigma_last if sigma_last is not None else 0.0),
        "threshold": float(threshold_last if threshold_last is not None else min_abs_threshold),
        "count": sum(hot_mask_total).sum(),
    }
    return cleaned, hot_mask_total, diagnostics

def bytescale(data, cmin=None, cmax=None, high=255, low=0, remove_hot_pixels=False):
    if remove_hot_pixels:
        data, _, diag = detect_and_remove_hot_pixels(data)
        num_hot = diag["count"]
        if num_hot>0:
            print("HOT PIXELS!")
            print(diag)

    if data.dtype == np.uint8:
        return data

    if high < low:
        raise ValueError("`high` should be larger than `low`.")

    if cmin is None:
        cmin = data.min()
        # cmin = float(np.percentile(data,0.02))
    if cmax is None:
        cmax = data.max()
        # cmax = float(np.percentile(data,0.98))

    cscale = cmax - cmin
    if cscale < 0:
        raise ValueError("`cmax` should be larger than `cmin`.")
    elif cscale == 0:
        cscale = 1

    scale = float(high - low) / cscale
    bytedata = (data * 1.0 - cmin) * scale + low + 0.4999
    bytedata = np.clip(bytedata, 0, 255)
    return bytedata.astype(np.uint8)

def reshape_storage_data_to_image(data, image_shape, data_type='uint8'):
    image = np.zeros(tuple(image_shape), dtype=data_type)
    image[:image_shape[0]] = data[:]
    return image

def crop_image(image, xlims:list, ylims:list):
    # lims are in fractional terms
    image_shape = np.array(image.shape)
    image_cropped = image[
        int(xlims[0]*image_shape[0]):int(xlims[1]*image_shape[0]),
        int(ylims[0]*image_shape[1]):int(ylims[1]*image_shape[1])
    ]
    return image_cropped

def merge_cropped_and_original_image(original_image, cropped_image, xlims:list, ylims:list): # to use in code when the two images need to be merged for display purposes
    image_shape = np.array(original_image.shape)
    merged_image = original_image.copy()
    merged_image[
        int(xlims[0]*image_shape[0]):int(xlims[1]*image_shape[0]),
        int(ylims[0]*image_shape[1]):int(ylims[1]*image_shape[1])
    ] = cropped_image
    return merged_image

def sparse_sample_image(image, fig_dims):
    image_shape = np.array(image.shape)
    max_dim = image_shape.max()
    dim_thresh = np.array(fig_dims).max()
    if max_dim <= dim_thresh:
        return image
    if max_dim > dim_thresh:
        f = int(np.round(max_dim/dim_thresh))
        X, Y = np.meshgrid(
            np.arange(0,image_shape[0]-1,f),
            np.arange(0,image_shape[1]-1,f),
        )
        image = image[X,Y]
        return np.transpose(image, (1,0))

def resample_image(image, target_height):
    if image.shape[0] > target_height:
        aspect_ratio = image.shape[1] / image.shape[0]
        target_width = int(aspect_ratio * target_height)
        resampled_image = image[::image.shape[0]//target_height, ::image.shape[1]//target_width]
        return resampled_image
    return image

def rotate_by_90(image, k):
    return(np.rot90(image, k))

def adjust_brightness_contrast_gamma(
    image:np.ndarray, 
    contrast:float,
    brightness:float, 
    gamma:float)->np.ndarray:
    """adjust the brightness, contrast and gamma in an image

    Args:
        image (np.ndarray): the image array
        contrast (float): contrast value negative to positive, some num
        brightness (float): brightness value
        gamma (float): gamma value, cannot be zero

    Returns:
        np.ndarray: the image with the adjusted exposure
    """
    image = cv2.convertScaleAbs(image, contrast, brightness)
    if gamma != 0:
        lookUpTable = np.empty((1,256), np.uint8)
        for i in range(256):
            lookUpTable[0,i] = np.clip(pow(i / 255.0, gamma) * 255.0, 0, 255)        
        return cv2.LUT(image, lookUpTable)
    return image







