    
def plotly_shape_to_skimage(shape):
    """Converts a Plotly rect shape to skimage-style bbox [r0, c0, r1, c1]"""
    # Plotly: x=col, y=row
    return [
        int(min(shape['y0'], shape['y1'])), # min_row
        int(min(shape['x0'], shape['x1'])), # min_col
        int(max(shape['y0'], shape['y1'])), # max_row
        int(max(shape['x0'], shape['x1']))  # max_col
    ]

def skimage_to_plotly_shape(bbox, box_id):
    """Converts skimage bbox [r0, c0, r1, c1] to Plotly shape"""
    return {
        'type': 'rect',
        'x0': bbox[1], 'y0': bbox[0],
        'x1': bbox[3], 'y1': bbox[2],
        'line': {'color': 'cyan', 'width': 2},
        'editable': True
    }
    
def is_inside(centroid, roi_bbox):
    """
    centroid: [row, col]
    roi_bbox: [min_row, min_col, max_row, max_col]
    """
    r, c = centroid
    rmin, cmin, rmax, cmax = roi_bbox
    return rmin <= r <= rmax and cmin <= c <= cmax