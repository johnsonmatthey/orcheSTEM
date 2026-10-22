import numpy as np 
from skimage.feature import peak_local_max
from mahotas import cwatershed
import scipy.ndimage as ndi
from edt import edt
from skimage.segmentation import find_boundaries

def remove_close_peaks(coord,coords,s):
    """
    for the current given coordinate the the point cloud, find the close coordinates and remove them
    """
    dists = np.sqrt(np.sum(((coord - coords)**2),axis=1)).reshape(-1,1)
    dclose= np.where(dists<(s))[0] # distances that are close to s
    coords = np.delete(coords,dclose,axis=0)
    coords = np.vstack((coord,coords))
    return coords

def remove_all_close_local_maxi_coords(local_maxi_coords,s):
    for i in range(0,len(local_maxi_coords)):
        try: 
            local_maxi_coords = remove_close_peaks(local_maxi_coords[i],local_maxi_coords,s)
        except IndexError:
            pass
    return local_maxi_coords

def watershed(mask,s):
    """
    perform watershed of a mask given a separation value of s
    """
    if s == 0 :
        return mask
    
    selem = np.ones((s,s))
    
    if mask.ndim == 3:
        selem = np.ones((s,s,s))

    dst = edt(mask)
    local_maxi_coords = peak_local_max(dst, footprint=selem, labels=mask, exclude_border=False) 
    local_maxi_coords = remove_all_close_local_maxi_coords(local_maxi_coords,s)
    local_maxi = np.zeros_like(mask)
    local_maxi[tuple(local_maxi_coords.T)] = 1
    local_maxi = ndi.label(local_maxi)[0]
    labels = cwatershed(dst.max() - dst,local_maxi)
    boundaries = find_boundaries(labels) == 0
    return (mask*boundaries).astype('uint8')