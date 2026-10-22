def _add_crosses(a):
    """
    Adds 3 pixel buffer cross to quad chip data.

    Parameters
    ----------
    a : numpy.ndarray
        Stack of raw frames or reshaped dask array object, prior to dimension reshaping, to insert
        3 pixel buffer cross into.

    Returns
    -------
    b : numpy.ndarray
        Stack of frames or reshaped 4DSTEM object including 3 pixel buffer cross in the diffraction plane.
    """
    original_shape = a.shape

    if len(original_shape) == 4:
        a = a.reshape(
            original_shape[0] * original_shape[1], original_shape[2], original_shape[3]
        )

    a_half = int(original_shape[-1] / 2), int(original_shape[-2] / 2)
    # Define 3 pixel wide cross of zeros to pad raw data
    if len(original_shape) == 4:
        z_array = np.zeros(
            (original_shape[0] * original_shape[1], original_shape[-2], 3),
            dtype=a.dtype,
        )
        z_array2 = np.zeros(
            (original_shape[0] * original_shape[1], 3, original_shape[-1] + 3),
            dtype=a.dtype,
        )
    else:
        z_array = np.zeros((original_shape[0], original_shape[-2], 3), dtype=a.dtype)
        z_array2 = np.zeros(
            (original_shape[0], 3, original_shape[-1] + 3), dtype=a.dtype
        )

    # Insert blank cross into raw data
    b = np.concatenate((a[:, :, : a_half[1]], z_array, a[:, :, a_half[1] :]), axis=-1)

    b = np.concatenate((b[:, : a_half[0], :], z_array2, b[:, a_half[0] :, :]), axis=-2)

    if len(original_shape) == 4:
        b = b.reshape(
            original_shape[0],
            original_shape[1],
            original_shape[2] + 3,
            original_shape[3] + 3,
        )

    return b

import os
import numpy as np
# file = r"/dls/e02/data/2026/mg44446-2/Merlin/W_thin_test1/20260724_144047/20260724_144041_data.mib"
folder = r"/dls/e02/data/2026/mg44446-2/Merlin/W_thin_test1/20260724_144047/"


def Grab_first_mib_frame(file_path):
    if os.path.exists(file_path):
        for (root,dirs,files) in os.walk(folder,topdown=True): 
            for f in files:
                if f.endswith('.mib'):
                    file = os.path.join(root,f)
    else:
        print('No Merlin file folder found.')
        return np.zeros(512,512)
    with open(file, "rb") as mib:
        header = mib.read(100)
        print(str(header).split(',')[:10])
        add_cross = True
        header_size = int(str(header).split(',')[2])
        det_y = int(str(header).split(',')[4]) #512 
        det_x = int(str(header).split(',')[5]) #512 
        
        print(f"header length is {str(header).split(',')[2]}, and the data type is {str(header).split(',')[6]}.")
        print(f"Frame size is {str(header).split(',')[4]} by {str(header).split(',')[5]}.")
        dtype = np.uint8 # PIXEL_DEPTH_NPY_TYPE["U08"]

        stride = (header_size + det_y*det_x*np.dtype(dtype).itemsize)

        # ensure the dtype is big endian (from Merlin manual)
        dtype_be = np.dtype(dtype).newbyteorder(">")

        # return pointer to the start
        ptr = 0
        mib.seek(ptr)
        # read the frame (header+data), this moves the file pointer by stride
        frame = mib.read(stride)

        # construct only the frame
        arr = np.frombuffer(frame[header_size:], dtype=dtype_be)

        # convert from big-endian to little-endian
        arr_le = arr.byteswap()
        arr_le = arr_le.view(arr_le.dtype.newbyteorder())

        # reshape to 2D for flipping
        resh = arr_le.reshape(det_y, det_x)

        # flip it to match those from pyxem (but why?)
        resh = np.flipud(resh)

        # reshape to the chunk frame size
        resh = resh.reshape(1, det_y, det_x)

        # add cross if needed
        if add_cross:
            resh = _add_crosses(resh)
        
        return resh[0,:,:]


# import matplotlib.patches as patches
# import matplotlib.pyplot as plt

# h,w = np.shape(reshc[0,:,:])
# Ramp = np.linspace(-1,1,h)
# im_rampx, im_rampy = np.meshgrid(Ramp, Ramp)
# COM = (round(h/2)+np.sum(np.multiply(im_rampy,reshc[0,:,:]/np.sum(reshc[0,:,:])))*h/2, round(h/2)+np.sum(np.multiply(im_rampx,reshc[0,:,:]/np.sum(reshc[0,:,:])))*h/2)


# fig, ax = plt.subplots()
# ax.imshow(reshc[0,:,:])

# # Create the circle patch
# circle = patches.Circle(
#     COM[::-1],
#     radius=10,
#     edgecolor="red",
#     facecolor="none",
#     linewidth=2,
# )

# # Add the patch to the axis
# ax.add_patch(circle)

# # Ensure circle looks perfectly round, not skewed
# ax.set_aspect("equal")

# plt.show()       
