import plotly.graph_objects as go
import numpy as np
import cv2

def create_sub_sampled_figure(
    image, 
    relayout_data, 
    current_zoom_state,  
    target_display_dim
):
    # 1. Handle Dimensions
    # Ensure we are working with H, W, C
    if image.ndim == 2:
        H, W = image.shape
        is_grayscale = True
    else:
        H, W, C = image.shape
        is_grayscale = False

    zoom_info = current_zoom_state.copy() if current_zoom_state else {}

    # 2. Handle Relayout / Zoom Logic
    if relayout_data:
        if relayout_data.get('xaxis.autorange') or relayout_data.get('yaxis.autorange'):
            zoom_info.clear()
        else:
            # Robustly check for ranges in relayoutData
            xr = relayout_data.get('xaxis.range')
            yr = relayout_data.get('yaxis.range')
            
            # Handle array vs index access style from Plotly
            x0 = xr[0] if xr else relayout_data.get('xaxis.range[0]')
            x1 = xr[1] if xr else relayout_data.get('xaxis.range[1]')
            y0 = yr[0] if yr else relayout_data.get('yaxis.range[0]')
            y1 = yr[1] if yr else relayout_data.get('yaxis.range[1]')

            if x0 is not None and x1 is not None:
                zoom_info['x0'], zoom_info['x1'] = x0, x1
            if y0 is not None and y1 is not None:
                zoom_info['y0'], zoom_info['y1'] = y0, y1

    # 3. Calculate Subsampling
    is_zoomed = all(k in zoom_info for k in ('x0', 'x1', 'y0', 'y1'))

    if is_zoomed:
        # Clamp zoom values to image boundaries
        # Note: Y-axis logic is tricky. Usually Plotly sends Y0 (bottom) and Y1 (top).
        # For images, we need row indices.
        raw_x0, raw_x1 = sorted([max(0, min(W, zoom_info['x0'])), max(0, min(W, zoom_info['x1']))])
        raw_y0, raw_y1 = sorted([max(0, min(H, zoom_info['y0'])), max(0, min(H, zoom_info['y1']))])

        # Convert to integer indices
        j0, j1 = int(np.floor(raw_x0)), int(np.ceil(raw_x1))
        i0, i1 = int(np.floor(raw_y0)), int(np.ceil(raw_y1))

        if j1 > j0 and i1 > i0:
            cropped_img = image[i0:i1, j0:j1]
            
            # Calculate downsample factor
            max_s_crop = max(j1-j0, i1-i0)
            downsample_factor = max(1, (max_s_crop + target_display_dim - 1) // target_display_dim)
            
            # Slice the data
            display_img_data = cropped_img[::downsample_factor, ::downsample_factor]
            
            # Reconstruct coordinates relative to original image
            # We create arrays like you had before, it's safer for alignment
            x_axis_coords = np.arange(j0, j1, downsample_factor)
            y_axis_coords = np.arange(i0, i1, downsample_factor)
            
            # Preserve the ZOOM state exactly as requested
            fig_x_range = [zoom_info['x0'], zoom_info['x1']]
            fig_y_range = [zoom_info['y0'], zoom_info['y1']]
        else:
            is_zoomed = False
            zoom_info.clear()

    if not is_zoomed:
        max_s_full = max(H, W)
        downsample_factor = max(1, (max_s_full + target_display_dim - 1) // target_display_dim)
        
        display_img_data = image[::downsample_factor, ::downsample_factor]
        
        x_axis_coords = np.arange(0, W, downsample_factor)
        y_axis_coords = np.arange(0, H, downsample_factor)
        
        # Standard Image View: X [0, W], Y [H, 0] (Reversed for images!)
        fig_x_range = [0, W]
        fig_y_range = [H, 0] 
        zoom_info.clear()

    # 4. Grayscale Fix
    # go.Image REQUIREs 3 channels (RGB). If we have 2D, we assume it's grayscale 
    # and stack it to make it look like RGB to Plotly.
    if display_img_data.ndim == 2:
        display_img_data = np.stack((display_img_data,)*3, axis=-1)

    # 5. Safety check for empty data
    if display_img_data.size == 0:
         display_img_data = np.zeros((1, 1, 3), dtype=np.uint8)

    # 6. Create Figure using go.Image (Faster than px.imshow)
    fig = go.Figure()
    
    fig.add_trace(go.Image(
        z=display_img_data,
        x0=x_axis_coords[0],
        dx=downsample_factor,
        y0=y_axis_coords[0],
        dy=downsample_factor,
        colormodel='rgb' # Always RGB now that we handled the grayscale conversion manually
    ))

    # 7. Update Layout to handle Orientation and Margins
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(
            range=fig_x_range,
            visible=False,
            autorange=False 
        ),
        yaxis=dict(
            range=fig_y_range, # This range [H, 0] controls the flip!
            visible=False,
            autorange=False,
            scaleanchor='x' # Keeps pixels square
        )
    )

    return fig, zoom_info


def plotpx(
    image, 
    relayout_data = None,
    current_zoom_state = None,
    target_display_dim = 500, # Default to 500 for speed
):
    # Ensure image is uint8 for speed
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)

    # Wrapper
    fig, zoom_state_to_persist = create_sub_sampled_figure(
        image = image,
        relayout_data = relayout_data,
        current_zoom_state = current_zoom_state,
        target_display_dim = target_display_dim
    )
    return fig, zoom_state_to_persist