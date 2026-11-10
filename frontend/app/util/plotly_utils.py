import re

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
    
def plotly_path_to_polygon(shape):
    """Converts a Plotly freeform 'path' shape (lasso) into a list of [row, col] points"""
    coords = [float(n) for n in re.findall(r'[-+]?\d*\.?\d+', shape['path'])]
    return [[y, x] for x, y in zip(coords[0::2], coords[1::2])]

def point_in_polygon(point, polygon):
    """Ray-casting point-in-polygon test. point/polygon vertices: [row, col]"""
    r, c = point
    inside = False
    n = len(polygon)
    for i in range(n):
        r1, c1 = polygon[i]
        r2, c2 = polygon[(i + 1) % n]
        if (r1 > r) != (r2 > r) and c < c1 + (r - r1) * (c2 - c1) / (r2 - r1):
            inside = not inside
    return inside

def is_inside(centroid, roi):
    """
    centroid: [row, col]
    roi: bbox [min_row, min_col, max_row, max_col], or a lasso polygon (list of [row, col] points)
    """
    if roi and isinstance(roi[0], (list, tuple)):
        return point_in_polygon(centroid, roi)
    r, c = centroid
    rmin, cmin, rmax, cmax = roi
    return rmin <= r <= rmax and cmin <= c <= cmax