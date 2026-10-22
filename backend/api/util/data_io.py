import os
import pickle
import numpy as np
import shutil
import time
import io
import base64
import cv2
from .preprocess import bytescale
import json
from pathlib import Path 
from skimage.io import imsave, imread
# from rsciio import digitalmicrograph
from typing import Literal
from typing import Literal, Any, Union


def clear_local_files(path:str, max_time:int = 86400):
    now = time.time()
    for f in os.listdir(path):
        if os.stat(os.path.join(path,f)).st_mtime < now - max_time: 
            shutil.rmtree(os.path.join(path,f))

# def local_store(temp_directory:str ,file_name:str ,data: np.ndarray, data_type: Literal["array", "object", "png"] = "array"):
#     Path(temp_directory).mkdir(parents=True, exist_ok=True)
#     if data_type == 'array':
#         np.save(os.path.join(temp_directory,file_name+'.npy'),data)
#     if data_type == 'object': # saving the data if its any other type of metric
#         with open(os.path.join(temp_directory,file_name+'.pkl'), 'wb') as f:
#             pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
#     if data_type == 'png':
#         imsave(os.path.join(temp_directory,file_name+'.png'),data)

# def local_retrieve(temp_directory:str ,file_name:str ,data_type:str ='array'):
#     if data_type == 'array':
#         return np.load(os.path.join(temp_directory,file_name+'.npy'))#,mmap_mode='r')
#     if data_type == 'object':
#         with open(os.path.join(temp_directory,file_name+'.pkl'), 'rb') as f:
#             return pickle.load(f)
#     if data_type == 'png':
#         return read_image(os.path.join(temp_directory,file_name+'.png'))[0] # just the png image, no metadata, that is used for general image reader
    
def local_store(
    temp_directory: str, 
    file_name: str, 
    data: Union[np.ndarray, dict, list, Any], 
    data_type: Literal["array", "object", "png", "json"] = "array"
):
    Path(temp_directory).mkdir(parents=True, exist_ok=True)
    file_path = os.path.join(temp_directory, file_name)

    if data_type == 'array':
        np.save(file_path + '.npy', data)
    
    elif data_type == 'object':
        with open(file_path + '.pkl', 'wb') as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
    
    elif data_type == 'png':
        imsave(file_path + '.png', data)
    
    elif data_type == "json":
        with open(file_path + '.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

def local_retrieve(
    temp_directory: str, 
    file_name: str, 
    data_type:  Literal["array", "object", "png", "json"] = "array"
):
    file_path = os.path.join(temp_directory, file_name)

    if data_type == 'array':
        return np.load(file_path + '.npy')
    
    elif data_type == 'object':
        with open(file_path + '.pkl', 'rb') as f:
            return pickle.load(f)
    
    elif data_type == 'png':
        return read_image(file_path + '.png')[0]
    
    elif data_type == 'json':
        with open(file_path + '.json', 'r', encoding='utf-8') as f:
            return json.load(f)
        

def string_to_text_file(file_name:str,string:str):
    with io.open(file_name, "w", encoding="utf-8") as f:
        f.write(string)

def text_file_to_string(file_name:str):
    with open(file_name, 'r', encoding="utf8") as myfile:
        string = myfile.read().replace('\n', '')
    return string

def find_most_common(my_list:list):
    """
    find the most common element in a list

    Args:
        my_list (list): list
    """
    return max(set(my_list), key=my_list.count)

def array_to_data_url_cv2(img: np.ndarray, compression=90, use_webp=True):
    if img.ndim > 2 and img.shape[2] == 3:  # Check if image is RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    # Choose format: WebP for better compression, JPEG as fallback
    if use_webp:
        encode_params = [int(cv2.IMWRITE_WEBP_QUALITY), compression]
        _, img_encoded = cv2.imencode('.webp', img, encode_params)
        prefix = 'data:image/webp;base64,'
    else:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), compression]
        _, img_encoded = cv2.imencode('.jpg', img, encode_params)
        prefix = 'data:image/jpeg;base64,'
    
    # Encode the image to base64
    image_string = prefix + base64.b64encode(img_encoded).decode("utf-8")
    
    return image_string

def read_image(path:str):
    # if ".dm3" in path or ".dm4" in path:
    #     dm_obj = digitalmicrograph.file_reader(path)
    #     image = dm_obj[0]['data']
    #     pixel_size = dm_obj[0]['axes'][0]['scale']
    #     pixel_units = dm_obj[0]['axes'][0]['units']
    #     image = bytescale(image)
    #     # to do : options to add a scalebar here might be nice?? 
    #     print("this is my image")
    #     print(image)
        
    #     print("these are my image dimensions")
    #     print(image.shape)
    #     print("this is my pixel units")
    #     print(pixel_units)
    #     print("this is my pixel size")
    #     print(pixel_size)
    #     if pixel_units == 'µm':
    #         pixel_units = 'um'
    #     if pixel_units == 'Å':
    #         pixel_units = 'nm'
    #         pixel_size = 1/10 * pixel_size
            
    #     # image = imshow.add_scalebar(image, pixel_size=pixel_size, pixel_units=pixel_units)
    #     return bytescale(image), pixel_size, pixel_units
    image = bytescale(cv2.imread(path,cv2.IMREAD_GRAYSCALE))
    pixel_size = 1
    pixel_units = 'pixels'
    return image, pixel_size, pixel_units

def dict_to_json(file_name, dictionary):
    json_object = json.dumps(dictionary, indent = 4) 
    with open(f'{file_name}.json', 'w') as outfile:
        outfile.write(json_object)

def fig_to_image_string(fig):
    """converts a plotly image to an image string

    Args:
        fig (_type_): plotly figure object
    """
    img_bytes = fig.to_image(format="png")
    encoding = base64.b64encode(img_bytes).decode()
    img_b64 = "data:image/png;base64," + encoding
    return img_b64


def fig2data(fig):
    """
    credit: http://www.icare.univ-lille1.fr/tutorials/convert_a_matplotlib_figure
    @brief Convert a Matplotlib figure to a 4D numpy array with RGBA channels and return it
    @param fig a matplotlib figure
    @return a numpy 3D array of RGBA values
    """
    # draw the renderer
    fig.canvas.draw()
 
    # Get the RGBA buffer from the figure
    h,w = fig.canvas.get_width_height()
    buf = np.fromstring ( fig.canvas.tostring_argb(), dtype=np.uint8 )
    buf.shape = ( w, h,4 )
 
    # canvas.tostring_argb give pixmap in ARGB mode. Roll the ALPHA channel to have it in RGBA mode
    buf = np.roll ( buf, 3, axis = 2 )
    return buf

def write_image_to_virtual_file(image_array):
    """
    Write an image array to a virtual file and return the virtual file.
    
    Parameters:
    image_array (numpy.ndarray): The image array to write to the virtual file.
    
    Returns:
    BytesIO: The virtual file containing the image data.
    """
    virtual_file = io.BytesIO()
    imsave(virtual_file, image_array, plugin='pil', format_str='png')
    virtual_file.seek(0)  # Reset stream position to the beginning
    return virtual_file

def read_image_from_virtual_file(virtual_file):
    """
    Read an image array from a virtual file.
    
    Parameters:
    virtual_file (BytesIO): The virtual file containing the image data.
    
    Returns:
    numpy.ndarray: The image array read from the virtual file.
    """
    virtual_file.seek(0)  # Ensure the stream position is at the beginning
    image_array = imread(virtual_file, plugin='pil')
    return image_array


def parse_and_save_dcc_upload_contents(content, filename, upload_dir):
    """
    Docstring for parse_and_save_dcc_upload_contents
    
    :param content: content from dcc upload
    :param filename: list of filenames returned by dcc upload
    :param upload_dir: location where the data needs to be saved
    
    Example usage: 
    
    @callback(
        Input('upload-report-data', 'contents'),
        State('upload-report-data', 'filename'),
        State('upload-report-data', 'style'), # styling chosen just so that we can control an enable/disable button
    )
    def save_contents(list_of_contents, list_of_filenames, current_style):
        for content, filename in zip(list_of_contents, list_of_filenames):
            if content is not None:
                saved_path = parse_and_save_dcc_upload_contents(content, filename, upload_dir)
                if saved_path:
                    file_paths.append(saved_path)
    ... rest of your code goes here     
    """
    _, content_string = content.split(',')
    decoded = base64.b64decode(content_string)
    
    # Create the full path
    file_path = os.path.join(upload_dir, filename)
    
    try:
        # Write the file
        with open(file_path, "wb") as f:
            f.write(decoded)
        return file_path
    except Exception as e:
        print(e)
        return None