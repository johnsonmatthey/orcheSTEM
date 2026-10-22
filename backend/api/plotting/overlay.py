import numpy as np
from util.preprocess import bytescale
from .color import hex2rgb

def label2rgb(image, label_mask, label_list, color_rgbs):
    """
    Modify an image to fill in specified areas defined by label_mask with RGB colors provided in color_rgbs.
    
    Parameters:
    image (array): The original image.
    label_mask (array): The mask where each value corresponds to a label which determines the color to apply.
    label_list (list): A list of labels which correspond to different segments of the mask.
    color_rgbs (list): List of RGB tuples/colors corresponding to each label.
    
    Returns:
    array: The modified image with specified areas filled with the given RGB colors.
    """
    # Convert the grayscale image into an RGB image if needed
    if image.ndim < 3:
        image_rgb = np.zeros((image.shape[0], image.shape[1], 3), dtype='float32')
        image_rgb[:, :, 0] = image / 255
        image_rgb[:, :, 1] = image / 255
        image_rgb[:, :, 2] = image / 255
    else:
        image_rgb = image.astype('float32') / 255  # Normalize for RGB calculations
    
    # Create the overlay for each label
    for i, label in enumerate(label_list):
        idx = label - 1  # Adjust index for zero-based Python indexing
        current_rgb = np.array(color_rgbs[idx]) / 255  # Normalize RGB values
        
        # Create a mask where the label mask matches the current label
        mask = (label_mask == label)
        
        # For each channel in the RGB image, apply the color where mask is True
        for channel in range(3):
            image_rgb[mask, channel] = current_rgb[channel]
    
    return image_rgb

def create_RGB_overlay(image,label_mask,label_list,color_labels,color_alphas):
    color_rgbs = [np.array(hex2rgb(x),dtype='uint8') for x in color_labels]
    ova = label2rgb(
        image,
        label_mask,
        np.array(label_list,dtype='uint8'),
        np.array(color_rgbs,dtype='uint8'),
    )
    return bytescale(ova)
