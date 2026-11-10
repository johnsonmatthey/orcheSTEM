
from pathlib import Path
from fastapi import APIRouter
from util import data_io, preprocess
from data_models import schemas
from skimage.io import imread
import numpy as np
router = APIRouter()
from microscope.core.controller import build_controller
from microscope.techniques.compucentric_tilting import Compucentric_calibration, Compucentric_tilt

@router.post("/scan")
def trigger_scan(req: schemas.ScanAndSaveRequest):
    # Build microscope controller based on config 
    microscope = build_controller(req.stage_method, req.lenses_method, req.imaging_method)

    scanned_img_arr = None
    scanned_img_arr_lowmag = None

    # Set scan parameters
    microscope.imaging.set_dwell_time(req.dwell_time_us * 1e-6) # in seconds
    microscope.imaging.set_flyback_time(req.flyback_time_us * 1e-6) # in seconds
    box_coords = req.box_coords if req.is_subscan else None # should be width, height, x0, y0

    savefolder = Path(req.folder_path).resolve().as_posix()
    with microscope.lenses.detector_inserted():
        with microscope.lenses.beam_unblanked():
            try:
                scanned_img_arr = microscope.imaging.get_image(
                    full_image_size=[req.survey_image_size, req.survey_image_size],
                    subscan_region=box_coords,
                    savefolder=savefolder,
                    savefile=req.filename,
                )
                # rescale to uint8 for saving as png
                #data_io.local_store(req.folder_path, req.filename, scanned_img_arr, data_type='array')
                if scanned_img_arr is not None:
                    scanned_img_arr = preprocess.bytescale(scanned_img_arr)

                if box_coords is None:
                    #save the absolute magnification+defocus used here as only should enter if doing normal survey
                    # - this is so the same view can be reproduced after stage movement
                    num_change = 4 # Temp for pyjem, TODO replace this with set mag logic and expose to frontend
                    data_io.local_store(req.folder_path, req.filename + '_settings', {
                        "magnification": microscope.lenses.get_magnification(),
                        "defocus": microscope.lenses.get_defocus(),
                        "low_mag_increments" : num_change 
                    }, data_type='json')
                    # For checking at low mag where you are etc. Testing
                    if microscope.lenses.increment_magnification(-num_change):
                        try:
                            scanned_img_arr_lowmag = microscope.imaging.get_image(
                                full_image_size=[req.survey_image_size, req.survey_image_size],
                                subscan_region=box_coords,
                                savefolder=savefolder,
                                savefile=req.filename+'_lowmag',
                            )
                            if scanned_img_arr_lowmag is not None:
                                scanned_img_arr_lowmag = preprocess.bytescale(scanned_img_arr_lowmag)
                        finally:
                            microscope.lenses.increment_magnification(num_change)
                    else:
                        print("Low-magnification survey unavailable; keeping the main survey image.")

            except Exception as e:
                print(f"Image acquisition failed: {e}. Using dummy image.")
    
    if scanned_img_arr is None:
        # dummy image if no microscope connected
        scanned_img_arr = imread("test.bmp", as_gray=True) # dummy image saved in the main folder

    # req.folder_path + "/" + "survey_image"
    # dummy_img = imread(req.folder_path + "/" + "survey_image.tif", as_gray=True) # dummy image saved in the main folder

    data_io.local_store(req.folder_path, req.filename, scanned_img_arr, data_type='png')
    if scanned_img_arr_lowmag is not None:
        data_io.local_store(req.folder_path, req.filename + '_lowmag', scanned_img_arr_lowmag, data_type='png')

    return {"status": "success", "image": f"{req.filename}.png"}


@router.post("/save-defocus")
def save_defocus(req: schemas.SaveDefocusRequest):
    microscope = build_controller(req.stage_method, req.lenses_method, req.imaging_method)
    try:
        olf_value = microscope.lenses.get_defocus()
    except Exception as e:
        print("failed to get defocus value so saving as None. Error:", e)
        olf_value = None
    print(f"Saved defocus OLf={olf_value} to {req.folder_path}/{req.filename}-defocus")
    data_io.local_store(req.folder_path, f"{req.filename}", olf_value, data_type='json')
    return {"status": "success", "defocus": olf_value}


@router.post("/stage-position")
async def save_stage_position(req: schemas.SaveStageRequest):
    # Build microscope controller based on config 
    microscope = build_controller(req.stage_method, req.lenses_method, req.imaging_method)
    # In the future, can add option to save absolute position from PYJEM_STAGE or just do relative as is here
    stage_location = microscope.stage.get_position()
    # in nm
    if stage_location is None:
        print("Failed to retrieve stage position. Saving dummy positions.")
        stage_location = {
            "x": np.random.randint(1,1000), 
            "y": np.random.randint(1,1000), 
            "z": np.random.randint(1,1000),
            'xt': 0,
            'yt': 0,
        }
    data_io.local_store(
        req.folder_path, 
        f'stage-position', 
        data=stage_location,
        data_type='json'   
    )
    return {"status": "success", "stage_position": stage_location}


@router.post("/scan-offline")
async def trigger_scan_offline(req: schemas.ScanAndSaveRequest):
    scanned_img_arr = imread("test.bmp", as_gray=True) # dummy image saved in the main folder
    data_io.local_store(req.folder_path, req.filename, scanned_img_arr, data_type='png')
    
    # save stage position - retrieve from PYJEM_STAGE or just do relative as is here
    data_io.local_store(
        req.folder_path, 
        f'stage-position', 
        data={'x':0.0, 'y':0.0},
        data_type='json'   
    )
    return {"status": "success", "image": f"{req.filename}.png"}

@router.post("/compucentric-tilt-calibration")
def CUTilt(req: schemas.CompUcentricCal):
    print('starting calibration')
    Correction_for_x_tilt, Correction_for_y_tilt, Shift_calibration, Tilt_calibrations, Calibration_postion, Shift_orientation, Tilt_orientation = Compucentric_calibration(req)
    print('Images successfully taken')
    if Shift_orientation is None: Shift_orientation = list(5,4)
    if Tilt_orientation is None: Tilt_orientation = list(3,2)
    data_io.local_store(
        req.folder_path, # path
        f'compucentric-data', # filename
        data={'stage-axis':[Shift_orientation, Tilt_orientation], 
              'stage-position':Calibration_postion, 
              'tilt-corrections':[Correction_for_x_tilt, Correction_for_y_tilt]
              }, # data as dict
        data_type='json'   # file type
    )
    print('data saved')
    return {"status": "success"}

@router.post("/compucentric-tilt-movement")
def CUTiltMove(req: schemas.CompUcentricCal):
    axis_data = data_io.local_retrieve(req.folder_path, "compucentric-data", 'json')
    axis_data = axis_data.get('tilt-corrections')
    angle = 0.1 # make user variable later
    angle = float(req.sign + str(angle)) 
    # req.direction req.sign
    Compucentric_tilt(req, angle=angle, direction=req.direction, Correction_for_x_tilt=axis_data[0], Correction_for_y_tilt=axis_data[1])
    return {"status": "success"}