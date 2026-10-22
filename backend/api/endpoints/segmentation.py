from fastapi import APIRouter
from data_models import schemas
from util import threshold, data_io, filters, Thin_feature_segmentation
from plotting import overlay
import numpy as np
from ml_util import unet_request_util as unet_util
import os

router = APIRouter()

def stored_mask_and_overlay(folder_path, mask, img):
    data_io.local_store(folder_path, 'threshold', mask, data_type='png')
    data_io.local_store(folder_path, 'threshold', mask, data_type='array')
    combined = overlay.create_RGB_overlay(img, mask > 0, [1], ["#FF0000"], [0.5])
    data_io.local_store(folder_path, 'threshold-overlay', combined, data_type='object')


@router.post("/segment-classical")
async def apply_classical(req: schemas.SegClassicalRequest):
    img = data_io.local_retrieve(req.folder_path, 'survey', data_type='png')
    img = filters.median(img, req.median_val)
    mask = img > 50 # Placeholder for actual classical method

    stored_mask_and_overlay(req.folder_path, mask, img)
    return {"status": "success"}

@router.post("/segment-ml")
async def apply_ml(req: schemas.MLRequest):
    img = data_io.local_retrieve(req.folder_path, 'survey', data_type='png')
    img_np = np.array(img)
    mask = unet_util.get_unet_mask(img_np, server_address = (req.model_ip, req.model_port))
    print("sent image to UNet server and received mask")
    stored_mask_and_overlay(req.folder_path, mask, img)
    return {"status": "success"}

@router.post("/segment-thresholding")
async def apply_thresholding(req: schemas.ThresholdRequest):
    img = data_io.local_retrieve(req.folder_path, 'survey', data_type='png')
    img = filters.median(img, req.median_val)
    mask = threshold.threshold_multi_range(img, req.range)


    stored_mask_and_overlay(req.folder_path, mask, img)
    return {"status": "success"}

@router.post("/segment-thin-feature")
async def apply_thresholding(req: schemas.ThinRequest):
    img = data_io.local_retrieve(req.folder_path, 'survey', data_type='png')
    processed = Thin_feature_segmentation.process_thin_features(
        img, 
        smoothing=req.dropdown_smoothing,              # 'gaussian', 'median', 'none'
        smoothing_sigma=req.input_smoothing,
        background=req.dropdown_background,         # 'large_gaussian', 'rolling_ball', 'none'
        background_gaussian_sigma=req.input_background,
        local_contrast="clahe",            # 'clahe', 'none'
        clahe_clip_limit=0.01,
        clahe_kernel_size=None,
        # segmentation
        seg_method=req.dropdown_segmentation,             # 'adaptive', 'global', 'hysteresis'
        polarity=req.polarity_selector,                 # 'bright' or 'dark'
        threshold_value=req.input_threshold_value,
        threshold_sigma=req.input_threshold_sigma,
        # watershed
        watershed_mode=req.dropdown_watershed,         # 'flooding', 'topological', 'spanning_forests', 'none'
        watershed_min_distance=req.input_watershed_distance,
        watershed_rw_beta=90,
        use_canny=False,
        canny_sigma=1.5,
        canny_low=None,
        canny_high=None,
        # cleanup
        open_radius=req.input_min_open,
        close_radius=req.input_min_close,
        min_object_size=req.input_min_object,
        min_hole_size=req.input_min_hole,
        # postprocess
        max_object_size=None,
        width_height_ratio_range=None,
        area_range=None,
        )

    mask = processed['cleaned_mask'].astype(bool)
    stored_mask_and_overlay(req.folder_path, mask, img)
    return {"status": "success"}


















