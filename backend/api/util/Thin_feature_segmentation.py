###~~~ Assumes a numpy array image input ~~~###

### Image Contrast Enhancement ###
#~~Smoothing~~#
#Gaussian or median or None 

#~~Background subtraction~~#
#Large gaussian or rolling-ball or None

#~~Boost local contrast~~#
#contrast limited adaptive histogram equalization or None


### Image Segmentaion ###
#~~Morphological~~#
# adaptive threshold or global threshold or hystersis threshold
# open/close & remove lone pixels

#~~Watershed~~#
# flooding or topolgical or spanning forests

#~~Edge detection~~#
#Canny?

### Post process ### 
#~~Gap closing/small object removal~~#

#~~Downselect by user definitions: width/heigh ratio, size, etc~~#

#~~Hough transform~~#
# skelatonize a binary image from morph or water 
# find lines return boxes around them

import numpy as np
from PIL import Image

from skimage import exposure, filters, feature, morphology, measure, segmentation, transform, util


def to_gray_float01(image):
    """
    Convert input (numpy array or PIL image) to grayscale float32 in [0, 1].
    """
    if isinstance(image, Image.Image):
        image = np.array(image)

    image = np.asarray(image)

    if image.ndim == 3:
        if image.shape[-1] == 4:
            image = image[..., :3]
        # Simple luminance conversion without skimage.color
        image = image.astype(np.float32)
        image = 0.2989 * image[..., 0] + 0.5870 * image[..., 1] + 0.1140 * image[..., 2]
    else:
        image = image.astype(np.float32)

    imin = np.min(image)
    imax = np.max(image)
    if imax > imin:
        image = (image - imin) / (imax - imin)
    else:
        image = np.zeros_like(image, dtype=np.float32)

    return image.astype(np.float32)


def apply_smoothing(img, method="none", sigma=1.0):
    """
    method: 'none', 'gaussian', 'median'
    """
    if method == "gaussian":
        return filters.gaussian(img, sigma=sigma, preserve_range=True).astype(np.float32)
    elif method == "median":
        fp = morphology.disk(max(1, int(np.ceil(sigma))))
        return filters.median(util.img_as_float32(img), footprint=fp).astype(np.float32)
    return img.astype(np.float32)


def subtract_background(img, method="none", background_sigma=20.0):
    """
    method: 'none', 'large_gaussian', 'rolling_ball'
    rolling_ball is approximated with morphological opening using a disk.
    """
    if method == "large_gaussian":
        gaussian_sigma = background_sigma
        bg = filters.gaussian(img, sigma=gaussian_sigma, preserve_range=True)
        out = img - bg
        out = exposure.rescale_intensity(out, in_range="image", out_range=(0, 1))
        return out.astype(np.float32)

    elif method == "rolling_ball":
        # Approximation of rolling-ball background subtraction
        rolling_ball_radius = background_sigma
        selem = morphology.disk(max(1, int(rolling_ball_radius)))
        bg = morphology.opening(img, footprint=selem)
        out = img - bg
        out = exposure.rescale_intensity(out, in_range="image", out_range=(0, 1))
        return out.astype(np.float32)

    return img.astype(np.float32)


def boost_local_contrast(img, method="none", clip_limit=0.01, kernel_size=None):
    """
    method: 'none', 'clahe'
    """
    if method == "clahe":
        return exposure.equalize_adapthist(img, clip_limit=clip_limit, kernel_size=kernel_size).astype(np.float32)
    return img.astype(np.float32)


def enhance_image(
    image,
    smoothing="none",
    smoothing_sigma=1.0,
    background="none",
    background_sigma=20.0,
    local_contrast="none",
    clahe_clip_limit=0.01,
    clahe_kernel_size=None,
):
    img = to_gray_float01(image)
    img = apply_smoothing(img, method=smoothing, sigma=smoothing_sigma)
    img = subtract_background(img, method=background, background_sigma=background_sigma)
    img = boost_local_contrast(img, method=local_contrast, clip_limit=clahe_clip_limit, kernel_size=clahe_kernel_size)
    return img


def threshold_mask(
    img,
    method="global",
    polarity="bright",
    global_threshold=None,
    threshold_value=35,
    threshold_sigma=0.0,
):
    """
    method: 'adaptive', 'global', 'hysteresis'
    polarity: 'bright' or 'dark'
    """
    if polarity not in ("bright", "dark"):
        raise ValueError("polarity must be 'bright' or 'dark'")

    work = img if polarity == "bright" else (1.0 - img)

    if method == "adaptive":
        neighbourhood_size = int(threshold_value)
        if neighbourhood_size % 2 == 0:
            neighbourhood_size += 1
        thr = filters.threshold_local(work, block_size=neighbourhood_size, offset=threshold_sigma)
        mask = work > thr

    elif method == "global":
        if global_threshold is None:
            global_threshold = filters.threshold_otsu(work)
        mask = work > float(global_threshold)

    elif method == "hysteresis":
        if threshold_sigma==0:
            # fallback based on image percentiles
            hysteresis_low = np.percentile(work, 60)
            hysteresis_high = np.percentile(work, 80)
        else:
            hysteresis_low = np.percentile(work, threshold_value-threshold_sigma)
            hysteresis_high = np.percentile(work, threshold_value+threshold_sigma)
        mask = filters.apply_hysteresis_threshold(work, hysteresis_low, hysteresis_high)

    else:
        raise ValueError("method must be 'adaptive', 'global', or 'hysteresis'")

    return mask.astype(bool)


def morphological_cleanup(
    mask,
    open_radius=1,
    close_radius=1,
    min_object_size=20,
    min_hole_size=20,
):
    out = mask.astype(bool)

    if open_radius and open_radius > 0:
        out = morphology.opening(out, footprint=morphology.disk(int(open_radius)))
    if close_radius and close_radius > 0:
        out = morphology.closing(out, footprint=morphology.disk(int(close_radius)))

    if min_object_size and min_object_size > 0:
        out = morphology.remove_small_objects(out, min_size=int(min_object_size))

    if min_hole_size and min_hole_size > 0:
        out = morphology.remove_small_holes(out, area_threshold=int(min_hole_size))

    return out.astype(bool)


def edge_segmentation(img, sigma=1.5, low_threshold=None, high_threshold=None):
    """
    Canny edge map.
    """
    return feature.canny(
        img,
        sigma=sigma,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    ).astype(bool)


def watershed_segment(
    img,
    seed_mask,
    mode="flooding",
    polarity="bright",
    min_distance=10,
    rw_beta=90, # Penalization coefficient for the random walker motion (the greater beta, the more difficult the diffusion).
):
    """
    mode:
      - 'flooding'      : marker-controlled watershed using connected components as markers
      - 'topological'   : watershed using local extrema markers
      - 'spanning_forests' : random walker (spanning forest style)
    Returns a binary foreground mask.
    """
    work = img if polarity == "bright" else (1.0 - img)

    if mode == "spanning_forests":
        # 1 = background, 2 = foreground
        markers = np.ones_like(work, dtype=np.int32)
        markers[seed_mask] = 2
        # keep a thin band of background; outside seed mask remains background
        labels = segmentation.random_walker(work, markers, beta=rw_beta, mode="bf")
        return (labels == 2)

    # Watershed on gradient
    gradient = filters.sobel(work)

    if mode == "flooding":
        # Connected components as markers
        markers = measure.label(seed_mask)
        if markers.max() == 0:
            return seed_mask.astype(bool)
        labels = segmentation.watershed(gradient, markers=markers, mask=seed_mask)
        return labels > 0

    if mode == "topological":
        # Markers from local maxima on the work image
        coords = feature.peak_local_max(
            work,
            min_distance=max(1, int(min_distance)),
            threshold_abs=np.percentile(work[seed_mask], 50) if np.any(seed_mask) else None,
            exclude_border=False,
            labels=seed_mask.astype(np.uint8),
        )

        markers = np.zeros_like(work, dtype=np.int32)
        for i, (r, c) in enumerate(coords, start=1):
            markers[r, c] = i

        if markers.max() == 0:
            # fallback
            markers = measure.label(seed_mask)

        labels = segmentation.watershed(gradient, markers=markers, mask=seed_mask)
        return labels > 0

    raise ValueError("mode must be 'flooding', 'topological', or 'spanning_forests'")


def postprocess_mask(
    mask,
    max_object_size=None,
    width_height_ratio_range=None,
    area_range=None,
):
    """
    Post-process and optionally downselect by shape.

    width_height_ratio_range: (min_ratio, max_ratio) based on bbox width / height
    area_range: (min_area, max_area)
    """
    out = mask.astype(bool)

    if max_object_size is not None:
        # Keep only components below a maximum size
        labeled = measure.label(out)
        keep = np.zeros_like(out, dtype=bool)
        for region in measure.regionprops(labeled):
            if region.area <= max_object_size:
                keep[labeled == region.label] = True
        out = keep

    if width_height_ratio_range is not None or area_range is not None:
        labeled = measure.label(out)
        keep = np.zeros_like(out, dtype=bool)

        for region in measure.regionprops(labeled):
            minr, minc, maxr, maxc = region.bbox
            h = maxr - minr
            w = maxc - minc
            ratio = (w / h) if h > 0 else np.inf

            ok = True
            if width_height_ratio_range is not None:
                rmin, rmax = width_height_ratio_range
                ok &= (ratio >= rmin) and (ratio <= rmax)

            if area_range is not None:
                amin, amax = area_range
                ok &= (region.area >= amin) and (region.area <= amax)

            if ok:
                keep[labeled == region.label] = True

        out = keep

    return out.astype(bool)


def skeleton_and_hough_boxes(
    mask,
    line_length=20,
    line_gap=5,
    box_padding=4,
):
    """
    Skeletonize a binary mask, detect line segments with probabilistic Hough transform,
    and return boxes around them.

    Returns:
      skeleton: 1-pixel wide binary image
      lines: list of ((x0, y0), (x1, y1))
      boxes: list of (min_row, min_col, max_row, max_col)
    """
    skeleton = morphology.skeletonize(mask > 0)

    # skimage returns line endpoints as (x0, y0), (x1, y1)
    lines = transform.probabilistic_hough_line(
        skeleton.astype(np.uint8),
        threshold=10,
        line_length=int(line_length),
        line_gap=int(line_gap),
    )

    boxes = []
    h, w = skeleton.shape

    for (x0, y0), (x1, y1) in lines:
        minc = max(0, min(x0, x1) - box_padding)
        maxc = min(w, max(x0, x1) + box_padding + 1)
        minr = max(0, min(y0, y1) - box_padding)
        maxr = min(h, max(y0, y1) + box_padding + 1)
        boxes.append((minr, minc, maxr, maxc))

    return skeleton, lines, boxes


def process_thin_features(
    image,
    # enhancement
    smoothing="gaussian",              # 'gaussian', 'median', 'none'
    smoothing_sigma=1.0,
    background="rolling_ball",         # 'large_gaussian', 'rolling_ball', 'none'
    background_gaussian_sigma=20.0,
    local_contrast="clahe",            # 'clahe', 'none'
    clahe_clip_limit=0.01,
    clahe_kernel_size=None,
    # segmentation
    seg_method="adaptive",             # 'adaptive', 'global', 'hysteresis'
    polarity="bright",                 # 'bright' or 'dark'
    global_threshold=None,
    threshold_value=35,
    threshold_sigma=0,
    # watershed
    watershed_mode="flooding",         # 'flooding', 'topological', 'spanning_forests', 'none'
    watershed_min_distance=10,
    watershed_rw_beta=90,
    use_canny=False,
    canny_sigma=1.5,
    canny_low=None,
    canny_high=None,
    # cleanup
    open_radius=1,
    close_radius=2,
    min_object_size=20,
    min_hole_size=20,
    # postprocess
    max_object_size=None,
    width_height_ratio_range=None,
    area_range=None,
    # hough
    do_hough=True,
    hough_line_length=20,
    hough_line_gap=5,
    box_padding=4,
):
    """
    Full pipeline for thin feature isolation.

    Returns a dict with:
      - enhanced
      - base_mask
      - edge_mask
      - watershed_mask
      - cleaned_mask
      - skeleton
      - lines
      - boxes
    """
    enhanced = enhance_image(
        image,
        smoothing=smoothing,
        smoothing_sigma=smoothing_sigma,
        background=background,
        background_sigma=background_gaussian_sigma,
        local_contrast=local_contrast,
        clahe_clip_limit=clahe_clip_limit,
        clahe_kernel_size=clahe_kernel_size,
    )

    base_mask = threshold_mask(
        enhanced,
        method=seg_method,
        polarity=polarity,
        global_threshold=global_threshold,
        threshold_value=threshold_value,
        threshold_sigma=threshold_sigma,
    )

    edge_mask = None
    if use_canny:
        edge_mask = edge_segmentation(
            enhanced,
            sigma=canny_sigma,
            low_threshold=canny_low,
            high_threshold=canny_high,
        )
        # Combine threshold + edges to help thin structures
        base_mask = np.logical_or(base_mask, edge_mask)

    if watershed_mode != 'none': use_watershed = True 
    else: use_watershed = False
    watershed_mask = None
    if use_watershed:
        watershed_mask = watershed_segment(
            enhanced,
            seed_mask=base_mask,
            mode=watershed_mode,
            polarity=polarity,
            min_distance=watershed_min_distance,
            rw_beta=watershed_rw_beta,
        )
        base_mask = np.logical_or(base_mask, watershed_mask)

    cleaned_mask = morphological_cleanup(
        base_mask,
        open_radius=open_radius,
        close_radius=close_radius,
        min_object_size=min_object_size,
        min_hole_size=min_hole_size,
    )

    cleaned_mask = postprocess_mask(
        cleaned_mask,
        max_object_size=max_object_size,
        width_height_ratio_range=width_height_ratio_range,
        area_range=area_range,
    )

    ###~~~ Cleaned mask is the one needed for segmentation ~~~###
    # line direction analysis below is for dislocation idenfication needed for automated decision making

    skeleton = None
    lines = []
    boxes = []
    if do_hough:
        skeleton, lines, boxes = skeleton_and_hough_boxes(
            cleaned_mask,
            line_length=hough_line_length,
            line_gap=hough_line_gap,
            box_padding=box_padding,
        )

    return {
        "enhanced": enhanced,
        "base_mask": base_mask,
        "edge_mask": edge_mask,
        "watershed_mask": watershed_mask,
        "cleaned_mask": cleaned_mask, # This is the key mask needed as output
        "skeleton": skeleton,
        "lines": lines,
        "boxes": boxes,
    }

import matplotlib.pyplot as plt


def _dict_to_multiline_text(d, max_items=8):
    """
    Convert a dictionary into a compact multiline label string.
    """
    items = list(d.items())

    lines = []
    for i, (k, v) in enumerate(items):
        if i >= max_items:
            lines.append("...")
            break
        lines.append(f"{k}={v}")

    return "\n".join(lines)


def visualize_pipeline_results(
    image,
    result,
    config=None,
    figsize=(18, 12),
    cmap="gray",
    overlay_boxes=True,
):
    """
    Display pipeline outputs in labeled matplotlib subplots.

    Parameters
    ----------
    image : ndarray
        Original input image.

    result : dict
        Output from process_thin_features()

    config : dict or None
        Dictionary of settings/parameters used in processing.

    figsize : tuple
        Matplotlib figure size.

    overlay_boxes : bool
        Draw Hough boxes on cleaned mask.
    """

    if config is None:
        config = {}

    fig, axes = plt.subplots(2, 4, figsize=figsize)
    axes = axes.ravel()

    # -----------------------------
    # Original
    # -----------------------------
    axes[0].imshow(image, cmap=cmap)
    axes[0].set_title("Original Image")
    axes[0].axis("off")

    # -----------------------------
    # Enhanced
    # -----------------------------
    axes[1].imshow(result["enhanced"], cmap=cmap)
    txt = _dict_to_multiline_text({
        "smoothing": config.get("smoothing"),
        "sigma": config.get("smoothing_sigma"),
        "background": config.get("background"),
        "contrast": config.get("local_contrast"),
    })
    axes[1].set_title(f"Enhanced\n{txt}", fontsize=9)
    axes[1].axis("off")

    # -----------------------------
    # Base mask
    # -----------------------------
    axes[2].imshow(result["base_mask"], cmap=cmap)
    txt = _dict_to_multiline_text({
        "seg_method": config.get("seg_method"),
        "polarity": config.get("polarity"),
        "block_size": config.get("adaptive_block_size"),
    })
    axes[2].set_title(f"Threshold Mask\n{txt}", fontsize=9)
    axes[2].axis("off")

    # -----------------------------
    # Edge mask
    # -----------------------------
    edge_mask = result.get("edge_mask")
    if edge_mask is not None:
        axes[3].imshow(edge_mask, cmap=cmap)
        txt = _dict_to_multiline_text({
            "canny_sigma": config.get("canny_sigma"),
            "low": config.get("canny_low"),
            "high": config.get("canny_high"),
        })
        axes[3].set_title(f"Canny Edges\n{txt}", fontsize=9)
    else:
        axes[3].text(0.5, 0.5, "No Edge Step", ha="center", va="center")
        axes[3].set_title("Canny Disabled")

    axes[3].axis("off")

    # -----------------------------
    # Watershed
    # -----------------------------
    watershed_mask = result.get("watershed_mask")
    if watershed_mask is not None:
        axes[4].imshow(watershed_mask, cmap=cmap)
        txt = _dict_to_multiline_text({
            "mode": config.get("watershed_mode"),
        })
        axes[4].set_title(f"Watershed\n{txt}", fontsize=9)
    else:
        axes[4].text(0.5, 0.5, "No Watershed", ha="center", va="center")
        axes[4].set_title("Watershed Disabled")

    axes[4].axis("off")

    # -----------------------------
    # Cleaned mask
    # -----------------------------
    axes[5].imshow(result["cleaned_mask"], cmap=cmap)

    txt = _dict_to_multiline_text({
        "open": config.get("open_radius"),
        "close": config.get("close_radius"),
        "min_obj": config.get("min_object_size"),
        "gap_close": config.get("gap_close_radius"),
    })

    axes[5].set_title(f"Postprocessed Mask\n{txt}", fontsize=9)
    axes[5].axis("off")

    # -----------------------------
    # Skeleton
    # -----------------------------
    skeleton = result.get("skeleton")

    if skeleton is not None:
        axes[6].imshow(skeleton, cmap=cmap)
        axes[6].set_title("Skeletonized")
    else:
        axes[6].text(0.5, 0.5, "No Skeleton", ha="center", va="center")
        axes[6].set_title("Skeleton Disabled")

    axes[6].axis("off")

    # -----------------------------
    # Hough lines / boxes
    # -----------------------------
    axes[7].imshow(result["cleaned_mask"], cmap=cmap)

    if overlay_boxes and result.get("boxes") is not None:
        for box in result["boxes"]:
            minr, minc, maxr, maxc = box

            rect = plt.Rectangle(
                (minc, minr),
                maxc - minc,
                maxr - minr,
                fill=False,
                linewidth=1.5,
            )

            axes[7].add_patch(rect)

    if result.get("lines") is not None:
        for line in result["lines"]:
            (x0, y0), (x1, y1) = line
            axes[7].plot([x0, x1], [y0, y1], linewidth=1)

    txt = _dict_to_multiline_text({
        "line_len": config.get("hough_line_length"),
        "line_gap": config.get("hough_line_gap"),
        "n_lines": len(result.get("lines", [])),
    })

    axes[7].set_title(f"Hough Lines\n{txt}", fontsize=9)
    axes[7].axis("off")

    plt.tight_layout()
    plt.show()