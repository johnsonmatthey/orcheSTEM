from fastapi import APIRouter, BackgroundTasks
import time
from data_models import schemas
from util import data_io
import os
from util.preprocess import bytescale
from pathlib import Path
import numpy as np
import h5py
from datetime import datetime
from microscope.controller import build_controller
from microscope.drift_corr import drift_calc
from microscope.microscope_config import MICROSCOPE_CONFIG
from endpoints.analysis import _append_analysis_log

router = APIRouter()

# THESE GLOBALS ARE JUST FOR TESTING!
VERIFY_DRIFT = False # This is to acquire an extra image as soon as drift correction is applied to verify things
RECHECK_DRIFT = False # This is to do a sanity check every 3 scans on the drift correction to catch any large drift that may have occurred
IMAGING_DETECTOR = MICROSCOPE_CONFIG.get('detector_name')

def _write_checkpoints(hdf_path, folder_path, initial_survey, cluster_index):
    """Write reference/checkpoint images into the merlin parameter HDF5 file."""
    with h5py.File(hdf_path, "a") as f:
        f.create_dataset("Cluster Index", data=cluster_index)
        if initial_survey is not None:
            f.create_dataset("Survey Scan", data=initial_survey)
        try:
            thresh = data_io.local_retrieve(folder_path, "threshold", data_type='png')
            f.create_dataset("Thresholded Image", data=thresh)
        except Exception:
            pass
        try:
            coords = data_io.local_retrieve(folder_path, "coords", data_type='json')
            # Store as a string representation since coords is a list of dicts
            f.create_dataset("Clusters Found", data=str(coords))
        except Exception:
            pass

def rescale_coords(width, height, x1,y1, scale):
    new_width = width * scale
    new_height = height * scale
    shift_x1 = x1  * scale
    shift_y1 = y1  * scale

    return new_width, new_height, shift_x1, shift_y1

def background_pipeline(req):
    microscope = build_controller(
        req.stage_method, 
        req.lenses_method, 
        req.imaging_method,
        "merlin" if req.stem4d is not None else None,
        "gatan" if req.stemsi is not None else None,
    )
    full_image_size = req.full_image_size
    survey_image_size = req.survey_image_size

    scan_rescaling = full_image_size//survey_image_size # Rescale coords from box to this
    # NOTE make this arbitrary for scaling!
    drift_rescaling = full_image_size//survey_image_size # Rescale coords from drift correction box to this 

    overall_drift_vector = [0,0] #in pixels to apply to the top left corner of the box
    prev_drift_box_offset = np.array([0.0, 0.0])  # tracks the box origin offset (survey res) used for the previous drift survey
    boxes_scan = data_io.local_retrieve(req.folder_path,"coords",data_type='json')
    full_survey_ref = data_io.local_retrieve(req.folder_path, "survey", data_type='png') # full survey for metadata
    full_survey_mask = data_io.local_retrieve(req.folder_path, 'threshold', data_type='array')

    initial_survey = data_io.local_retrieve(os.path.join(req.folder_path, "drift_survey"), "drift_survey-0", data_type='png')
    drift_sanity_ref = initial_survey.copy()  # stores every 3rd drift survey for sanity checks
    drift_survey_path = os.path.join(req.folder_path, "drift_survey")

    focus_output_path = os.path.join(req.folder_path, "focus")
    Path(focus_output_path).mkdir(parents=True, exist_ok=True)

    microscope.lenses.set_detector_position(IMAGING_DETECTOR, True) # make sure detector is inserted initially and change as needed
    counter = 0
    total_objects = len(boxes_scan)
    data_io.local_store(req.folder_path, "long-acquisition-state", data="Started", data_type="json")# setting the initial state

    # create analysis tracking json to be updated per iteration
    _append_analysis_log(req.folder_path, {
        "analysis_type": req.analysis_method, # "autoptych" or "manual" or etc.
        "total_num_boxes": total_objects,
    })
    zfill_len = len(str(total_objects))
    for i, box in enumerate(boxes_scan):
        print(f"box:{i}")
        data_io.local_store(req.folder_path, "box-index", i, data_type='object')
        scan_result = None
        # upscale the bbox to full scan size
        bbox = box['bbox']  # Assuming bbox is [x1, y1, x2, y2] - x1,y1 = top left
        box_id = box['id']
        y1, x1, y2, x2 = bbox
        width = x2 - x1
        height = y2 - y1
        scan_mask = full_survey_mask[y1:y2, x1:x2]
        print(scan_mask)

        # FOCUS FIRST!
        ########################
        # TODO make this either per particle or over everything
        print(f"Applying autofocus for box {i}...")
        # use scan dwells to autofocus
        microscope.imaging.set_dwell_time(req.scan_dwell_time_us / 1e6)
        microscope.imaging.set_flyback_time(req.scan_flyback_time_us / 1e6)

        # Apply accumulated drift to focus box coords
        focus_subscan = None
        if req.focus.focus_region == "box":
            fw, fh, fx1, fy1 = rescale_coords(width, height, x1, y1, scan_rescaling)
            fx1 += int(overall_drift_vector[0])
            fy1 += int(overall_drift_vector[1])
            # clamp to scan bounds
            fx1 = max(0, min(int(fx1), full_image_size - int(fw)))
            fy1 = max(0, min(int(fy1), full_image_size - int(fh)))
            focus_subscan = (fw, fh, fx1, fy1)
        microscope.lenses.autofocus(
            imaging=microscope.imaging, 
            method = req.focus.focus_method,
            focus_region = req.focus.focus_region, # can be full or box
            full_image_size= (full_image_size, full_image_size),
            survey_image_size= (survey_image_size, survey_image_size),
            subscan_region = focus_subscan, # only used if focus_region is box
            save_path = focus_output_path,
            region_loop_num = i
        )

        if req.drift.drift_every > 0 and i % req.drift.drift_every == 0:
            microscope.imaging.set_dwell_time(req.drift.dwell_time_us * 1e-6)
            microscope.imaging.set_flyback_time(req.drift.flyback_time_us * 1e-6)

            # apply drift here too if is subscan
            drift_coords = req.drift.box_coords
            cur_drift_box_offset = np.array([0.0, 0.0])  # offset applied to the current drift box (survey res)
            if drift_coords is not None:
                drift_coords = list(drift_coords)  # dont change original input
                original_x1 = drift_coords[2]
                original_y1 = drift_coords[3]
                # convert drift vector to be in survey res coords and apply to drift box coords
                drift_coords[2] += round(overall_drift_vector[0] / drift_rescaling)  # x1
                drift_coords[3] += round(overall_drift_vector[1] / drift_rescaling)  # y1

                # clamp to bounds
                drift_coords[2] = max(0, min(drift_coords[2], survey_image_size - drift_coords[0]))
                drift_coords[3] = max(0, min(drift_coords[3], survey_image_size - drift_coords[1]))

                # Record the ACTUAL offset applied after clamping (survey res)
                cur_drift_box_offset = np.array([
                    float(drift_coords[2] - original_x1),
                    float(drift_coords[3] - original_y1),
                ])

            # How much the box origin changed between the previous and current drift box (survey res)
            # so real_drift = apparent_shift + box_offset_change
            box_offset_change = cur_drift_box_offset - prev_drift_box_offset

            print(f"Running drift correction for box {i} with drift coords (in survey res): {drift_coords}...")
            print(f"original drift box coords (in survey res): {req.drift.box_coords}")

            # move to the defocus used when the drift region was initially acquired then restore the current defocus
            _drift_defocus = data_io.local_retrieve(
                os.path.join(req.folder_path, "drift_survey"),
                "drift_survey-0-defocus",
                data_type='json',
            )
            _current_defocus = microscope.lenses.get_defocus()
            if _drift_defocus is not None and _current_defocus is not None:
                print(f"Setting defocus to drift OLf={_drift_defocus} (current OLf={_current_defocus})")
                microscope.lenses.set_defocus(_drift_defocus)

            try:
                drift_px, drift_survey = microscope.imaging.drift_correct(
                    lenses=microscope.lenses,
                    survey_size=(survey_image_size, survey_image_size),  
                    initial_survey_img=initial_survey,
                    drift_subscan_coords=drift_coords, # width, height, x1, y1 - if None will do full image at survey res for drift correction
                    savefolder=Path(drift_survey_path).resolve().as_posix(),
                    savefile=f"drift_survey-{i+1}",
                )
            finally:
                if _drift_defocus is not None and _current_defocus is not None:
                    print(f"Restoring defocus to OLf={_current_defocus}")
                    microscope.lenses.set_defocus(_current_defocus)
            #data_io.local_store(os.path.join(req.folder_path, "drift_survey"), f"drift_survey-{i+1}", drift_survey, data_type='array')

            drift_survey = bytescale(drift_survey) # rescale for saving as png  
            data_io.local_store(os.path.join(req.folder_path, "drift_survey"), f"drift_survey-{i+1}", drift_survey, data_type='png')


            # OPTIONAL EXTRA IMAGE!#####################################
            if VERIFY_DRIFT:
                verify_drift = list(drift_coords) if drift_coords is not None else None
                if verify_drift is not None:
                    verify_drift[2] += round(drift_px[0])
                    verify_drift[3] += round(drift_px[1])
                    verify_drift[2] = max(0, min(verify_drift[2], survey_image_size - verify_drift[0]))
                    verify_drift[3] = max(0, min(verify_drift[3], survey_image_size - verify_drift[1]))

                _, verify_drift_image = microscope.imaging.drift_correct(
                    lenses=microscope.lenses, 
                    survey_size=(survey_image_size, survey_image_size),
                    initial_survey_img=initial_survey,
                    drift_subscan_coords=verify_drift, # width, height, x1, y1 - if None will do full image at survey res for drift correction
                    savefolder=Path(drift_survey_path).resolve().as_posix(),
                    savefile=f"drift_survey-{i+1}-check",
                )
                verify_drift_image = bytescale(verify_drift_image) # rescale for saving as png  
                data_io.local_store(os.path.join(req.folder_path, "drift_survey"), f"drift_survey-{i+1}-check", verify_drift_image, data_type='png')

            # drift_px is apparent_shift so add box_offset_change
            corrected_drift_px = drift_px + box_offset_change
            print("apparent drift (survey res):", drift_px)
            print("box offset change (survey res):", box_offset_change)
            print("corrected drift (survey res):", corrected_drift_px)

            # rescales this to the full scan res to allow sub pixel shifts
            # NOTE this is the vector to the top left corner to FOLLOW the object
            # *-1 to counteract the drift if needed
            overall_drift_vector[0] += corrected_drift_px[0] * drift_rescaling
            overall_drift_vector[1] += corrected_drift_px[1] * drift_rescaling
            overall_drift_vector = np.round(overall_drift_vector)
            print("overall drift vector (in pixels 4k res):", overall_drift_vector)

            prev_drift_box_offset = cur_drift_box_offset.copy()
            initial_survey = drift_survey # update for next iter

            # OPTIONAL FOR CONFIRMING DRIFT CORRECTION HAS NOT GONE WRONG!
            if RECHECK_DRIFT:
                # after every 3 scans, recheck incase a large gradual jump occurred
                # (both images were taken at drift corrected positions so any shift is  error
                if i > 0 and i % 3 == 0:
                    print(f"Sanity check at box {i} ===")
                    sanity_drift_px, sanity_response = drift_calc(
                        drift_sanity_ref,
                        drift_survey,
                        max_shift_pixel = min(drift_survey.shape) , # max is drift survey shape for safety?
                    )
                    sanity_drift_full = sanity_drift_px * drift_rescaling
                    print(f"Residual drift since last checkpoint (survey res): {sanity_drift_px} (response: {sanity_response:.3f})")
                    print(f"overall_drift_vector BEFORE correction: {overall_drift_vector}")

                    # Apply residual correction where should not need to do the extra correction given this is in post
                    overall_drift_vector[0] += sanity_drift_full[0]
                    overall_drift_vector[1] += sanity_drift_full[1]
                    overall_drift_vector = np.round(overall_drift_vector)
                    print(f"overall_drift_vector AFTER correction:  {overall_drift_vector}")

                    drift_sanity_ref = drift_survey.copy()


        # rescale to 4K coords and correct for drift, assigning correct vals
        width, height, x1,y1 = rescale_coords(width,height, x1,y1, scan_rescaling)        
        x1 += int(overall_drift_vector[0])
        y1 += int(overall_drift_vector[1])
        height += 1 #Add extra pixel for merlin scans
        
        progress_metadata = {
            "box_index": i,
            "box_id": box_id,
            "bbox": bbox,
            "survey_image_size": survey_image_size,
            "full_image_size": full_image_size,
            "drift_vector_upscaled": [int(overall_drift_vector[0]), int(overall_drift_vector[1])],
            "drift_vector_survey": [round(overall_drift_vector[0]/drift_rescaling), round(overall_drift_vector[1]/drift_rescaling)],
        }

        # NOW CHECK IF OUTSIDE SCANNING REGION!!!
        is_outside_bounds = x1 < 0 or y1 < 0 or (x1 + width) > full_image_size or (y1 + height) > full_image_size
        if is_outside_bounds:
            print(f"Box {i} with top left {x1}, {y1} outside bounds of scan!")
            analysis_dict = {
                **progress_metadata,
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "analysis_status": "skipped",
            }
            # append to analysis log for frontend to track and triigger analysis
            _append_analysis_log(req.folder_path, {str(i): analysis_dict})

            # progress dict
            counter += 1
            progress =  (counter/total_objects) * 100
            progress_dict = {
                **progress_metadata,
                "progress": progress
            }
            data_io.local_store(req.folder_path, "progress-metadata", progress_dict, data_type='json')
            continue

        scan_subfolder = os.path.join(req.folder_path, "scans", f"scan-{str(i).zfill(zfill_len)}")
        Path(scan_subfolder).mkdir(parents=True, exist_ok=True)

        # Attempt Merlin 4D STEM scan if configured
        if microscope.stem4d_detector is not None:
            microscope.imaging.set_dwell_time(req.stem4d.dwell_time_us / 1e6)
            microscope.imaging.set_flyback_time(req.stem4d.flyback_time_us / 1e6)

            with microscope.lenses.detector_removed(IMAGING_DETECTOR):
                timestamp = microscope.stem4d_detector.acquire(
                    lenses=microscope.lenses,
                    full_image_size=(full_image_size, full_image_size),
                    subscan_region=(width, height, x1, y1),
                    merlin_dwell_time_s=req.stem4d.dwell_time_us / 1e6, # convert from us to s
                    merlin_save_path= req.stem4d.savepath,
                    merlin_bit_depth= req.stem4d.bitdepth,
                )
            # Write checkpoint/reference images into the same HDF file
            merlin_save = req.stem4d.savepath.replace("/", "\\")
            params_savepath = f"{merlin_save}\\{timestamp}.hdf"
            _write_checkpoints(params_savepath, req.folder_path, full_survey_ref, i)

        elif microscope.stemsi is not None:
            microscope.imaging.set_dwell_time(req.stemsi.dwell_time_us / 1e6)
            microscope.imaging.set_flyback_time(req.stemsi.flyback_time_us / 1e6)
            survey_scaled_box_coords = rescale_coords(width,height-1, x1,y1, 1/scan_rescaling)

            si_drift_region = req.drift.box_coords
            if si_drift_region is not None:
                si_drift_region = list(si_drift_region)
                si_drift_region[2] += round(overall_drift_vector[0] / drift_rescaling)
                si_drift_region[3] += round(overall_drift_vector[1] / drift_rescaling)
                si_drift_region[2] = max(0, min(si_drift_region[2], survey_image_size - si_drift_region[0]))
                si_drift_region[3] = max(0, min(si_drift_region[3], survey_image_size - si_drift_region[1]))

            timestamp = microscope.stemsi.acquire(
                savefolder=Path(scan_subfolder).resolve().as_posix(),
                savefile="subscan",
                acquire_eels=req.stemsi.enable_eels,
                acquire_eds=req.stemsi.enable_eds,
                subscan_region= survey_scaled_box_coords, # need to be survey res coords as FOV
                survey_size=survey_image_size,
                drift_region=si_drift_region,
                subscan_size=req.stemsi.subscan_size,
                passes=req.stemsi.passes,
                custom_scan_mask = scan_mask if req.stemsi.enable_custom else None,
            )

        # Assumes detector is already inserted so no need to insert/remove every time
        else:
            microscope.imaging.set_dwell_time(req.scan_dwell_time_us / 1e6)
            microscope.imaging.set_flyback_time(req.scan_flyback_time_us / 1e6)
            with microscope.lenses.beam_unblanked(): # make sure beam is unblanked for scanning
                try:
                    scan_result = microscope.imaging.get_image(
                        full_image_size=(full_image_size, full_image_size),
                        subscan_region=(
                            width, height, 
                            x1, 
                            y1
                        ),
                        savefolder=Path(scan_subfolder).resolve().as_posix(),
                        savefile='subscan',
                        survey_image_size=(survey_image_size, survey_image_size),
                    )
                    time.sleep(1) # just a delay here until beam blanking etc
                except Exception as e:
                    print(f"Subscan for box {i} failed: {e}.")
                    scan_result = None

        if scan_result is not None:
            scan_result = bytescale(scan_result) # rescale for saving as png
            data_io.local_store(
                scan_subfolder, f'subscan', scan_result, data_type='png'
            )

        counter += 1
        progress =  (counter/total_objects) * 100

        data_io.local_store(req.folder_path, "progress-metadata", {
            **progress_metadata,
            "progress": progress
            }, data_type='json')

        # append to analysis log for frontend to track and triigger analysis
        _append_analysis_log(req.folder_path, {
            str(i): {
                **progress_metadata,
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "analysis_status": "pending-a",
            }
        })


    print(f"Completed {counter} / {len(boxes_scan)} scans.")
    data_io.local_store(req.folder_path, "long-acquisition-state", data="Finished", data_type="json")
    _append_analysis_log(req.folder_path, {"pipeline_complete": True})

@router.post("/search-pipeline")
async def run_search_pipeline(req: schemas.SearchPipelineRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(background_pipeline, req)
    return {
        "status": "Submitted background task"
    }


# offline pipeline to just test the code and see how things are working
def background_task_offline_mode(req):
    # load the survery image
    # load the coords that we want to scan
    survey_image = data_io.local_retrieve(req.folder_path, "survey", data_type='png')
    boxes_scan = data_io.local_retrieve(req.folder_path,"coords",data_type='json')
    
    full_image_size = req.full_image_size
    survey_image_size = req.survey_image_size
    
    scan_rescaling = full_image_size//survey_image_size # Rescale coords from box to this
    
    counter = 0
    total_objects = len(boxes_scan)
    data_io.local_store(req.folder_path, "long-acquisition-state", data="Started", data_type="json")# setting the initial state
    
    
    for i, box in enumerate(boxes_scan):
        time.sleep(3)
        print(f"box:{i}")
        
        
        
        data_io.local_store(req.folder_path, "box-index", i, data_type='object')
        
        # code for calculating drift 
        # get a survey image, compare it to previous survey image
        # get the drift vector
        # save the drift vector
        
        # change the box position based on what was provided
        # save the new box position for a given index
        
        
        # placeholder scan code so that we can crop the images how we want
        # thinking of this as a subscan of the region where we want to save the data
        bbox = box['bbox']
        box_id = box['id']
        y1, x1, y2, x2 = bbox # adjust box here? ? 
        
        
        scan_result = survey_image[y1:y2, x1:x2] # just a general test for the results returned
        data_io.local_store(
            req.folder_path, f'subscan-{i}', scan_result, data_type='png'
        )  
        # rest of Zaeem's code.... 
    
        counter += 1
        progress =  (counter/total_objects) * 100
        data_io.local_store(req.folder_path, "progress-percentage", progress, data_type='object')
        
    print(f"Completed {counter} / {len(boxes_scan)} scans.")
    data_io.local_store(req.folder_path, "long-acquisition-state", data="Finished", data_type="json")
        

@router.post("/search-pipeline-offline")
async def run_search_pipeline_offline(req: schemas.SearchPipelineRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(background_task_offline_mode, req)
    return {
        "status": "Submitted background task", 
    }