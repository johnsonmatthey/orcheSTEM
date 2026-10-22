import requests
import os
from pathlib import Path
from dash import Input, Output, State, callback, no_update, ctx, Patch
# Assuming these are your local helper modules
from util import data_io, plotly_utils
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
from app import BACKEND_URL, BASE_LOCAL_PATH
import math
from pages.survey import FEATURE_REQUIREMENTS, _FEATURE_BOX_STYLE
from pages.survey_image_segmentation import _SEGMENTATION_METHODS
import glob

# ONLY FOR FORCING FOR USE IN TESTS OFFLINE!
TEST_IMAGING_METHOD = None #"qd_scanengine"#'gatan'
TEST_LENSES_METHOD = None #'pyjem'
TEST_STAGE_METHOD = None #'pyjem'

def get_latest_pos_index(folder_path):
    """Find the highest pos-N directory index in folder_path, or 0 if none"""
    if not os.path.isdir(folder_path):
        return 0
    valid_dir = glob.glob(os.path.join(folder_path, "pos-*"))
    max_idx = max([int(os.path.basename(pos_val).split("-")[1]) for pos_val in valid_dir if os.path.isdir(pos_val)], default=0)
    return max_idx

@callback(
    Output("storage-folder-path",'data'),
    Output('experiment-state','data'),
    Output("text-input-experiment-name", "disabled"),
    Output("stage-index-counter", "data", allow_duplicate=True),
    Output("storage-state-pipeline", "data", allow_duplicate=True),
    Input("button-create-experiment", "n_clicks"),
    Input('url-home','pathname'),
    State("text-input-experiment-name", "value"),
    prevent_initial_call='initial_duplicate', # initial call happens still
)
def create_experiment_and_check_initial_state(n_click, url_pathname, folder_name):
    if folder_name is None:
        raise PreventUpdate
    folder_path = os.path.join(BASE_LOCAL_PATH, folder_name)
    if ctx.triggered_id == 'button-create-experiment':
        requests.post(f"{BACKEND_URL}/create-experiment", json={"folder_path": folder_path})
        return folder_path, False, True, 0, no_update
    if url_pathname == '/':
        experiment_state = os.path.isdir(folder_path)
        # If experiment exists, get the last pos index and use that to determine pipeline state
        if experiment_state:
            latest_idx = get_latest_pos_index(folder_path)
            # Detect pipeline state from the latest position folder
            pos_path = os.path.join(folder_path, f"pos-{latest_idx}")
            acq_state = data_io.local_retrieve(pos_path, "long-acquisition-state", data_type='json')
            pipeline_state = no_update
            if acq_state == "Started":
                pipeline_state = "started"
            elif acq_state == "Finished":
                pipeline_state = "finished"
            return folder_path, experiment_state, False, latest_idx, pipeline_state
        return folder_path, experiment_state, False, 0, no_update
    raise PreventUpdate

# button options to change the directory we are working in
@callback(
    Output('tab-main-display','value'),
    Input('button-scan', 'n_clicks'),
    Input('button-threshold', 'n_clicks'),
    Input('button-cluster', 'n_clicks'),
    Input('button-search', 'n_clicks'),
    prevent_initial_call=True
)
def switch_tabs(n1, n2, n3, n4):
    button_id = ctx.triggered_id
    if button_id is not None:
        tab_map = {
            'button-scan': 'survey-image',
            'button-threshold': 'survey-image-segmentation',
            'button-cluster': 'cluster-manager',
            'button-search': 'progress-checker'
        }
        return tab_map[button_id]
    else:
        raise PreventUpdate
    
@callback(
    Output("dropdown-control-stage", "data"),
    Output("dropdown-control-stage", "value"),
    Output("dropdown-control-lenses", "data"),
    Output("dropdown-control-lenses", "value"),
    Output("dropdown-control-imaging", "data"),
    Output("dropdown-control-imaging", "value"),
    Output("dropdown-control-4dstem-detector", "data"),
    Output("dropdown-control-4dstem-detector", "value"),
    Output("dropdown-control-si-detector", "data"),
    Output("dropdown-control-si-detector", "value"),
    Input("button-create-experiment", "n_clicks"),
)
def populate_microscope_dropdowns(_):
    # This will trigger on frontend loading. Also added a second trigger on if the experiment is created
    # No prevent update here on purpose
    try:
        resp = requests.get(f"{BACKEND_URL}/microscope/status")
        resp.raise_for_status()
        status = resp.json()
        # print("Microscope status retrieved successfully:", status)
        stage = status.get("stage", {})
        lenses = status.get("lenses", {})
        imaging = status.get("imaging", {})
        stem4d = status.get("4dstem_detector", {})
        stemsi = status.get("stemsi_detector", {})
        return (
            stage.get("options", []), stage.get("default"),
            lenses.get("options", []), lenses.get("default"),
            imaging.get("options", []), imaging.get("default"),
            stem4d.get("options", []), stem4d.get("default"),
            stemsi.get("options", []), stemsi.get("default"),
        )
    except Exception as e:
        print("Error retrieving microscope status:", e)
        return [], None, [], None, [], None, [], None, [], None

@callback(
    Output("collapse-advanced-settings", "opened"),
    Input("button-advanced-settings", "n_clicks"),
)
def update(n):
    if n is not None and n > 0:
        if n % 2 == 0:
            return False
        return True
    else:
        raise PreventUpdate

@callback(
    Output("compucentric-panel-wrapper", "style"),
    Input("compucentric-strip-toggle", "n_clicks"),
    State("compucentric-panel-wrapper", "style"),
    prevent_initial_call=True,
)
def toggle_compucentric_panel(n_clicks, current_style):
    if not n_clicks:
        raise PreventUpdate
    new_style = dict(current_style)
    if current_style.get("width") == "20px":
        new_style["width"] = "230px"
    else:
        new_style["width"] = "20px"
    return new_style

@callback(
    *[
        Output(f"feature-status-{feature.lower().replace(' ', '-')}", "style")
        for feature in FEATURE_REQUIREMENTS
    ],
    Input("dropdown-control-stage", "value"),
    Input("dropdown-control-lenses", "value"),
    Input("dropdown-control-imaging", "value"),
)
def update_feature_availability(stage, lenses, imaging):
    selections = {"stage": stage, "lenses": lenses, "imaging": imaging}
    base_style = _FEATURE_BOX_STYLE.copy()

    styles = []
    for feature, reqs in FEATURE_REQUIREMENTS.items():
        available = all(
            selections.get(cat) in allowed
            for cat, allowed in reqs.items()
        )
        styles.append(
            {
                **base_style, 
                #"color": "green" if available else "red", 
                "border": "2px solid green" if available else "2px solid red",
                "backgroundColor":"#e3fdea" if available else "#fae0e0"
            }
                
        )

    return tuple(styles)

@callback(
    Output("collapse-4dstem-options", "opened"),
    Input("checkbox-enable-4dstem", "checked"),
)
def toggle_4dstem_options(checked):
    if checked is None:
        raise PreventUpdate
    return bool(checked)                                

@callback(
    Output("collapse-si-options", "opened"),
    Input("checkbox-enable-si", "checked"),
)
def toggle_si_options(checked):
    if checked is None:
        raise PreventUpdate
    return bool(checked)                                


def snap_to_step(value, step=16, low=16, high=512):
    """Snap a value to the nearest step interval, clamped to [low, high].
    """
    if value is None:
        return low
    return max(low, min(high, round(value / step) * step))

@callback(
    Output("input-drift-region-size", "value"),
    Input("input-drift-region-size", "value"),
    State("input-survey-image-size", "value"),
    prevent_initial_call=True,
)
def snap_drift_region_size_ui(value, survey_image_size):
    snapped = snap_to_step(value, high=survey_image_size)
    if snapped == value:
        raise PreventUpdate
    return snapped

@callback(
    Output('graph-survey', 'figure', allow_duplicate=True),
    Output('stage-index-counter', 'data', allow_duplicate=True),
    Input('button-scan', 'n_clicks'),
    Input('experiment-state', 'data'), # This triggers on page load when state is set
    State('storage-folder-path', 'data'),
    State('stage-index-counter', 'data'),
    State("input-survey-image-size", "value"),
    State("input-survey-dwell-time", "value"),
    State("input-survey-flyback-time", "value"),
    State("dropdown-control-stage", "value"),
    State("dropdown-control-lenses", "value"),
    State("dropdown-control-imaging", "value"),
    prevent_initial_call=True
)
def scan(n_click, experiment_state, folder_path, current_index, survey_image_size, survey_dwell_time, survey_flyback_time, stage_method, lenses_method, imaging_method):
    if not folder_path:
        raise PreventUpdate
    
    triggered = ctx.triggered_id
    idx = current_index if current_index is not None else 0

    # CASE A: User clicked the scan button
    if triggered == 'button-scan':
        new_index = idx + 1
        pos_path = os.path.join(folder_path, f"pos-{new_index}")
        # Creates new folder for the new position/stage etc. For now assume you want only most recent scan but can iterate through later
        # Also create subfolders for organisation
        Path(pos_path).mkdir(parents=True, exist_ok=True)
        Path(pos_path, 'scans').mkdir(parents=True, exist_ok=True)
        Path(pos_path, 'drift_survey').mkdir(parents=True, exist_ok=True)
        Path(pos_path, 'logs').mkdir(parents=True, exist_ok=True)

        requests.post(f"{BACKEND_URL}/survey/scan", json={
            "folder_path": pos_path, 
            "filename": f"survey",
            "survey_image_size": survey_image_size, # refers to the original survey size. Needed for subscanning
            "dwell_time_us": survey_dwell_time,
            "flyback_time_us": survey_flyback_time,
            "is_subscan": False,
            "box_coords": None, # full image scan as default
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method
        })
        
        requests.post(f"{BACKEND_URL}/survey/stage-position", json={
            "folder_path": pos_path, 
            "stage_index": new_index,
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method

        })


        image = data_io.local_retrieve(pos_path, f"survey", data_type='png')
        if image is not None:
            fig = px.imshow(image, binary_string=True)
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), dragmode=False, xaxis={'visible': False, 'fixedrange': True}, yaxis={'visible': False, 'fixedrange': True})
            return fig, new_index # NOTE no need to increment it in the future as it is returned incremented
        
        return no_update, new_index

    # CASE B: Initial Load / Experiment State changed
    # We only auto-load if the button WASN'T the trigger
    if experiment_state is True:
        pos_path = os.path.join(folder_path, f"pos-{idx}")
        image = data_io.local_retrieve(pos_path, "survey", data_type='png')
        if image is not None:
            fig = px.imshow(image, binary_string=True)
            # shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in bboxes]
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), dragmode=False, xaxis={'visible': False, 'fixedrange': True}, yaxis={'visible': False, 'fixedrange': True})

            return fig, idx

    raise PreventUpdate

def snap_drift_region_box(survey_size, region_box):
    """Snapping the region box to be within the scanned image"""
    x0, y0, x1, y1 = region_box
    box_size = x1 - x0
    if x0 < 0:
        x0, x1 = 0, box_size
    elif x1 > survey_size:
        x0, x1 = survey_size - box_size, survey_size

    if y0 < 0:
        y0, y1 = 0, box_size
    elif y1 > survey_size:
        y0, y1 = survey_size - box_size, survey_size

    return x0, y0, x1, y1

@callback(
    Output("graph-survey", "figure", allow_duplicate=True),
    Input("graph-survey", "clickData"),
    State("radiocard-group-drift-correction-method", "value"),
    State("input-drift-region-size", "value"),
    State("graph-survey", "figure"),
    State('stage-index-counter', 'data'),
    prevent_initial_call=True,
)
def place_drift_box(click_data, method, region_size, current_fig, current_index):
    if method != "Box Region" or click_data is None or current_fig is None:
        raise PreventUpdate

    # Get actual image size from the figure's axis ranges
    layout = current_fig.get("layout", {})
    x_range = layout.get("xaxis", {}).get("range", [0, 0])
    survey_image_size = round(max(x_range) - min(x_range))

    size = snap_to_step(region_size, high=survey_image_size)
    half = size // 2
    point = click_data["points"][0]
    cx, cy = point["x"], point["y"]

    # Compute box, then clamp to image bounds while maintaining size
    x0 = cx - half
    y0 = cy - half
    x1 = cx + half
    y1 = cy + half
    print("Initial box coords:", (x0, y0, x1, y1))
    x0, y0, x1, y1 = snap_drift_region_box(survey_image_size, (x0, y0, x1, y1))
    print("Snapped box coords:", (x0, y0, x1, y1))
    patch = Patch()
    patch["layout"]["shapes"] = [
        {
            "type": "rect",
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "line": {"color": "cyan", "width": 2},
        }
    ]
    return patch

@callback(
    Output("graph-survey", "figure", allow_duplicate=True),
    Output("image-survey-driftregion", "src"),
    Output("storage-drift-region-box-coords", "data"),
    Input("button-acquire-drift-region", "n_clicks"),
    State("graph-survey", "figure"),
    State("radiocard-group-drift-correction-method", "value"),
    State("input-drift-dwell-time", "value"),
    State("input-drift-flyback-time", "value"),
    State('storage-folder-path', 'data'),
    State('stage-index-counter', 'data'),
    # State("input-survey-image-size", "value"),
    State("dropdown-control-stage", "value"),
    State("dropdown-control-lenses", "value"),
    State("dropdown-control-imaging", "value"),
    prevent_initial_call=True,
)
def acquire_drift_region(n_clicks, current_fig, method, drift_dwell_time, drift_flyback_time, folder_path, current_index, stage_method, lenses_method, imaging_method):
    if n_clicks is None or current_fig is None:
        raise PreventUpdate
    if method not in ["Box Region", "Full Search"]:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")

    # Get actual image size from the figure's axis ranges
    layout = current_fig.get("layout", {})
    x_range = layout.get("xaxis", {}).get("range", [0, 0])
    survey_image_size = round(max(x_range) - min(x_range))

    if method == "Box Region":
        is_subscan = True
        # Grab box coordinates from the current figure
        box_shape = current_fig.get("layout", {}).get("shapes", [])[0] #only 1 box
        if not box_shape:
            raise PreventUpdate
        
        box_coords = [
            box_shape.get("x1") - box_shape.get("x0"), # convert to width
            box_shape.get("y1") - box_shape.get("y0"), # convert to height
            box_shape.get("x0"),
            box_shape.get("y0"),
        ] # convert to (width, height, x0, y0) format for backend where x0,y0 is the top left corner

    elif method == "Full Search":
        is_subscan = False
        # Ideally just use the scan size field but need to add a check to make sure it is the one used when scanned (in case user changes it after scanning)
        layout = current_fig.get("layout", {})
        x_range = layout.get("xaxis", {}).get("range", [0, 0])
        y_range = layout.get("yaxis", {}).get("range", [0, 0])
        # px.imshow offsets ranges by ±0.5px, so round to get actual image size
        img_w = round(max(x_range) - min(x_range))
        img_h = round(max(y_range) - min(y_range))
        box_coords = [img_w, img_h, 0,0] # full image as box coords

    # Acquire drift region using the specified dwell and flyback times
    print(box_coords)
    drift_survey_path = os.path.join(pos_path, "drift_survey")
    requests.post(
        f"{BACKEND_URL}/survey/scan", 
        json={
            "folder_path": drift_survey_path,
            "filename": "drift_survey-0",
            "survey_image_size": survey_image_size, # refers to the original survey size. Needed for subscanning
            "dwell_time_us": drift_dwell_time, 
            "flyback_time_us": drift_flyback_time,
            "is_subscan": is_subscan,
            "box_coords": box_coords,
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method
        })
    requests.post(
        f"{BACKEND_URL}/survey/save-defocus",
        json={
            "folder_path": drift_survey_path,
            "filename": "drift_survey-0-defocus",
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD,
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD,
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD,
        })

    # When complete, change box border to red to indicate acquisition is done
    patch = Patch()
    patch["layout"]["shapes"] = [ # convert back to x0,y0,x1,y1 format for plotting
        {
            "type": "rect",
            "x0": box_coords[2],
            "y0": box_coords[3],
            "x1": box_coords[0] + box_coords[2],
            "y1": box_coords[1] + box_coords[3],
            "line": {"color": "red", "width": 2},
        }
    ]
    image = data_io.local_retrieve(drift_survey_path, f"drift_survey-0", data_type='png')

    if image is not None:
        return patch, data_io.array_to_data_url_cv2(image), box_coords
    else:
        return patch, no_update, box_coords

@callback(
    *[Output(m["method_id"], "style") for m in _SEGMENTATION_METHODS.values()],
    Input("segment-segcontrol-method", "value"),
)
def toggle_method_panels(value):
    show, hide = {"display": "block"}, {"display": "none"}
    selected_id = _SEGMENTATION_METHODS[value]["method_id"]
    method_states = []
    for method_dict in _SEGMENTATION_METHODS.values():
        method_states.append(show if method_dict["method_id"] == selected_id else hide)
    return method_states

@callback(
    Output("image-survey-segmentation", "src"),
    Input("button-threshold", "n_clicks"),
    Input('experiment-state', 'data'),
    # For Classical
    Input("slider-median-filter-classical", "value"),
    # For ML
    Input("button-apply-ml", "n_clicks"),
    Input("input-ml-model-ip", "value"),
    Input("input-ml-port", "value"),
    # For Thresholding
    Input("slider-median-filter-threshold", "value"),
    Input("range-slider-threshold", "value"),
    # For Thin feature segmentation
    Input("dropdown-smoothing", "value"),
    Input("input-smoothing", "value"),
    Input("dropdown-background", "value"),
    Input("input-background", "value"),
    #Input("clahe_on_off", "value"), # not currently used
    Input("polarity-selector", "value"),
    Input("dropdown-segmentation", "value"),
    Input("input-threshold-value", "value"), 
    Input("input-threshold-sigma", "value"),
    #Input("canny_on_off", "value"), # not currently used
    Input("dropdown-watershed", "value"),
    Input("input-watershed-distance", "value"),
    Input("input-min-open", "value"),
    Input("input-min-close", "value"),
    Input("input-min-object", "value"),
    Input("input-min-hole", "value"),
    #Input("Area-size-selector", "value"),
    #Input("hw-ratio-selector", "value"),
    # State info needed for pathing 
    State('storage-folder-path', 'data'),
    State('stage-index-counter', 'data'),
    State("segment-segcontrol-method", "value"),
    prevent_initial_call=True,
)
def run_segmentation(
    n, experiment_state, 
    # Classical params
    median_val_classical, 
    # ML params
    button_apply_ml, ml_model_ip, ml_model_port,
    # Thresholding params
    median_val_threshold,
    thresh_range, 
    # Thin feature params
    smoothing_mode, smoothing_sigma, background_sub_mode, background_sigma,
    polarity_selector, dropdown_segmentation, input_threshold_value, input_threshold_sigma,
    dropdown_watershed, input_watershed_distance,
    input_min_open, input_min_close, input_min_object, input_min_hole,
    # General params
    folder_path, current_index, selected_method
    ):
    if not folder_path:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")

    triggered = ctx.triggered_id
    # First check if experiment already exists, load if so for visual reasons
    if experiment_state is True:
        overlay_image = data_io.local_retrieve(pos_path, "threshold-overlay", "object")
        if overlay_image is not None:
            return data_io.array_to_data_url_cv2(overlay_image)
    
    # Now check which method is being used and group up the triggers
    payloads = {
        "Classical": {
            "folder_path": pos_path,
            "median_val": median_val_classical,
        },
        "ML": {
            "folder_path": pos_path,
            "model_ip": ml_model_ip,
            "model_port": ml_model_port,
        },
        "Thresholding": {
            "folder_path": pos_path,
            "range": thresh_range,
            "median_val": median_val_threshold,
        },
        "Thin Features": { #turn into schema when you finish
            "folder_path": pos_path,
            "dropdown_smoothing": smoothing_mode,
            "input_smoothing": smoothing_sigma,
            "dropdown_background": background_sub_mode,
            "input_background": background_sigma,
            "polarity_selector": polarity_selector,
            "dropdown_segmentation":  dropdown_segmentation, 
            "input_threshold_value": input_threshold_value, 
            "input_threshold_sigma": input_threshold_sigma,
            "dropdown_watershed": dropdown_watershed, 
            "input_watershed_distance": input_watershed_distance,
            "input_min_open": input_min_open, 
            "input_min_close": input_min_close, 
            "input_min_object": input_min_object, 
            "input_min_hole": input_min_hole,
        },
    }
    # selected_method is the key and will then map to the relevant endpoint and payload
    method = _SEGMENTATION_METHODS[selected_method]
    # if triggered == "segment-segcontrol-method":
    #     return None

    if triggered in method["triggers"]:
        payload = payloads[selected_method]
        payloads["selected_method"] = selected_method #indicate which method used
        # print(payload)
        requests.post(f"{BACKEND_URL}/segmentation/{method['endpoint']}", json=payload)
        data_io.local_store(pos_path, 'threshold-metadata', data=payloads, data_type="json") # store everything for convenience
        overlay_image = data_io.local_retrieve(pos_path, "threshold-overlay", "object")
        if overlay_image is not None:
            return data_io.array_to_data_url_cv2(overlay_image)

    raise PreventUpdate

@callback(
    Output("graph-survey-image-clustering", "figure"),
    Output("storage-original-boxes", "data"),
    Output("storage-bounding-boxes", "data"),
    Input("tab-main-display", "value"),           # <--- Add the Tab Input
    Input("button-cluster", "n_clicks"),
    Input("btn-reset-boxes", "n_clicks"),
    Input("experiment-state", "data"),
    Input("graph-survey-image-clustering", "relayoutData"),
    State("slider-clustering", "value"),
    State('storage-folder-path', 'data'),
    State("storage-original-boxes", "data"),
    State("storage-bounding-boxes", "data"),
    State('input-sampling', "value"),
    State("input-survey-image-size", "value"),
    State("input-full-image-size", "value"),
    State('stage-index-counter', 'data'),
    prevent_initial_call=True 
)
def watershed_and_interaction_manager(tab_value, n_cluster, n_reset, exp_state, relayout_data, 
                                      s_val, folder_path, original_bboxes, current_filtered,
                                      sampling, survey_size, full_size, 
                                      current_index):
    
    if not folder_path:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")

    triggered = ctx.triggered_id

    # --- 1. RUN NEW WATERSHED (Manual Click) ---
    if triggered == "button-cluster":
        # ... (Your existing watershed logic remains same)
        requests.post(f"{BACKEND_URL}/cluster/watershed", json={
            "folder_path": pos_path, "s_value": s_val, "sampling_res": sampling,
            'survey_image_size': survey_size, 'full_image_size': full_size
        })
        bboxes = data_io.local_retrieve(pos_path, 'coords', data_type='json')
        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')
        if image is None or bboxes is None: raise PreventUpdate

        fig = px.imshow(image, binary_string=True)
        shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in bboxes]
        fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawrect', newshape=dict(line_color='cyan'))
        return fig, bboxes, bboxes

    # --- 2. AUTO-LOAD (Tab Switch or Page Load) ---
    # We trigger if we switched to the cluster tab OR the experiment state changed
    if (triggered == "tab-main-display" and tab_value == "cluster-manager") or \
       (triggered == "experiment-state" and exp_state is True):
        
        saved_coords = data_io.local_retrieve(pos_path, 'coords', data_type='json')
        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')
        
        if image is not None and saved_coords is not None:
            fig = px.imshow(image, binary_string=True)
            shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in saved_coords]
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawrect', newshape=dict(line_color='cyan'))
            return fig, saved_coords, saved_coords

    # --- 3. RESET BOXES ---
    if triggered == "btn-reset-boxes":
        # ... (Existing logic)
        if not original_bboxes: return no_update, no_update, no_update
        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')
        fig = px.imshow(image, binary_string=True)
        shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in original_bboxes]
        fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawrect')
        return fig, no_update, original_bboxes

    # --- 4. ROI FILTERING (Using Patch) ---
    if triggered == "graph-survey-image-clustering" and relayout_data:
        # Note: Patch ONLY works if the graph already exists. 
        # Since we load the full figure in Step 2, Patch will now work here.
        if 'shapes' in relayout_data and len(relayout_data['shapes']) > 0:
            latest_shape = relayout_data['shapes'][-1]
            roi_bbox = plotly_utils.plotly_shape_to_skimage(latest_shape)
            source = original_bboxes if original_bboxes else current_filtered
            if not source: raise PreventUpdate

            filtered = [b for b in source if plotly_utils.is_inside(b['centroid'], roi_bbox)]
            data_io.local_store(pos_path, 'coords', data=filtered, data_type='json')
            
            patch_fig = Patch()
            patch_fig['layout']['shapes'] = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in filtered]
            return patch_fig, no_update, filtered

    raise PreventUpdate


@callback(
    Output('storage-state-pipeline','data', allow_duplicate=True),# Note interval is located in pages/progress_manager.py
    Input("button-search","n_clicks"),
    State("storage-folder-path","data"),
    Input("input-sampling","value"),
    Input("input-focus-freq","value"),
    Input("input-drift-freq","value"),
    Input("input-survey-image-size","value"),
    Input("input-full-image-size","value"),
    # Microscope controls
    State("dropdown-control-stage","value"),
    State("dropdown-control-lenses","value"),
    State("dropdown-control-imaging","value"),
    # 4D-STEM
    State("checkbox-enable-4dstem","checked"),
    State("dropdown-control-4dstem-detector","value"),
    State("input-4dstem-savepath","value"),
    State("input-4dstem-dwell-time","value"),
    State("input-4dstem-flyback-time","value"),
    State("input-4dstem-bitdepth","value"),
    # SI
    State("checkbox-enable-si", "checked"),
    State("dropdown-control-si-detector", "value"),
    State("checkbox-enable-si-eels", "checked"),
    State("checkbox-enable-si-eds", "checked"),
    State("checkbox-enable-si-custom", "checked"),
    State("input-si-dwell-time", "value"),
    State("input-si-flyback-time", "value"),
    State("input-si-subscan", "value"),
    State("input-si-passes", "value"),
    # analysis states
    State("checkbox-enable-autoptych", "checked"),
    # Other states
    State('stage-index-counter', 'data'),
    State("input-drift-dwell-time", "value"),
    State("input-drift-flyback-time", "value"),
    State("storage-drift-region-box-coords", "data"),
    State("input-survey-dwell-time", "value"),
    State("input-survey-flyback-time", "value"),
    prevent_initial_call=True
)
def start_search(
    n_click, folder_path, sampling, n_focus, n_drift, survey_image_size, full_image_size,
    ctrl_stage, ctrl_lenses, ctrl_imaging,
    enable_4dstem, ctrl_4dstem, stem4d_savepath, stem4d_dwell_time_us, stem4d_flyback_time_us, stem4d_bitdepth,
    enable_si, ctrl_si, enable_si_eels, enable_si_eds, enable_si_custom, si_dwell_time, si_flyback_time, si_subscan, si_passes,
    enable_autoptych,
    current_index,
    drift_dwell_time_us, drift_flyback_time_us, drift_box_coords,
    survey_dwell_time, survey_flyback_time
              
    ):
    if folder_path is not None:
        pos_path = os.path.join(folder_path, f"pos-{current_index}")
        print(pos_path)
        if n_click:
            # Save selected configuration to backend config.json
            config_preferences = {
                "preferences": {
                    "stage": ctrl_stage,
                    "lenses": ctrl_lenses,
                    "imaging": ctrl_imaging,
                    "4dstem_detector": ctrl_4dstem,
                    "stemsi_detector": ctrl_si,
                },
            }
            if enable_4dstem:
                config_preferences["stem4d_settings"] = {
                    "save_path": stem4d_savepath,
                    "dwell_time_us": stem4d_dwell_time_us,
                    "flyback_time_us": stem4d_flyback_time_us,
                    "bit_depth": stem4d_bitdepth,
                }
            if enable_si:
                config_preferences["stemsi_settings"] = {
                    "enable_eels": enable_si_eels,
                    "enable_eds": enable_si_eds,
                    "dwell_time_us": si_dwell_time,
                    "flyback_time_us": si_flyback_time,
                    "subscan_size": si_subscan,
                    "passes": si_passes,
                }

            requests.post(f"{BACKEND_URL}/microscope/config", json=config_preferences)
            print("Updated microscope configuration with current user preferences.")

            requests.post( 
                f"{BACKEND_URL}/pipeline/search-pipeline",
                json={
                    'folder_path':pos_path,
                    'sampling':sampling, # sampling res - not really needed as known via box coords
                    'survey_image_size':survey_image_size,
                    'scan_dwell_time_us': survey_dwell_time, # temp for now as fallback if only HAADF
                    'scan_flyback_time_us': survey_flyback_time,

                    'full_image_size':full_image_size,
                    "stage_method": ctrl_stage if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, 
                    "lenses_method": ctrl_lenses if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD,
                    "imaging_method": ctrl_imaging if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD,
                    "analysis_method" : "autoptych" if enable_autoptych else 'manual', # placeholder for now, can add more options later
                    "drift" : {
                        'drift_every':n_drift,
                        'dwell_time_us': drift_dwell_time_us,
                        'flyback_time_us': drift_flyback_time_us,
                        'box_coords': drift_box_coords, # for now just pass None and do full image drift correction. Can add option for box region later
                        'window_type': "hanning",
                        'max_shift_pixel': None, # None means auto which is half the survey size
                    },
                    "focus": {
                        "focus_every": n_focus,
                        "focus_method": "custom", # options are "pyjem" or "custom" - pyjem only if pyjem lens control available
                        "focus_region": "box", # options are "full" or "box"
                    },
                    "stem4d": {
                        "savepath": stem4d_savepath,
                        "dwell_time_us": stem4d_dwell_time_us,
                        "flyback_time_us": stem4d_flyback_time_us,
                        "bitdepth": stem4d_bitdepth,
                    } if enable_4dstem else None,
                    "stemsi": {
                        "detector": ctrl_si,
                        "enable_eels": enable_si_eels,
                        "enable_eds": enable_si_eds,
                        "enable_custom": enable_si_custom,
                        "dwell_time_us": si_dwell_time,
                        "flyback_time_us": si_flyback_time,
                        "subscan_size": si_subscan,
                        "passes": si_passes,
                    } if enable_si else None
                }
            )
            return "started"
        else:
            raise PreventUpdate
    else:
        raise PreventUpdate

@callback(
    Output('graph-survey-progress', 'figure'),
    Output('progress-bar-section', 'value'),
    Output('progress-bar-label', 'children'), # Changed 'value' to 'children' (standard for labels)
    Output('img-prev-scan', 'src'),
    Output('img-current-scan', 'src'),
    Output('storage-state-pipeline', 'data', allow_duplicate=True),
    Output('graph-overall-drift', 'figure'),
    Input('interval-check-progress', 'n_intervals'),
    State('storage-state-pipeline', 'data'),
    State('storage-folder-path', 'data'),
    State("storage-bounding-boxes", "data"), 
    State('stage-index-counter', 'data'),
    State('graph-overall-drift', 'figure'),
    prevent_initial_call=True
)
def check_progress(n_interval, pipeline_state, folder_path, original_bboxes, current_index, current_drift_fig):
    if not folder_path:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")

    # If bboxes aren't in the store yet (e.g. after page reload), try loading from disk
    if not original_bboxes:
        original_bboxes = data_io.local_retrieve(pos_path, "coords", data_type='json')
        if not original_bboxes:
            raise PreventUpdate
    zfill_len = len(str(len(original_bboxes)))
    # 1. Check current acquisition status
    acq_state = data_io.local_retrieve(pos_path, "long-acquisition-state", data_type='json')
    
    # If the file hasn't been created yet, the pipeline is still initializing
    if acq_state is None:
        return no_update, str(0), "Initializing...", no_update, no_update, "started", no_update

    # 2. Retrieve Progress Data
    # box_index = data_io.local_retrieve(pos_path, "box-index", data_type='object')
    progress_metadata = data_io.local_retrieve(pos_path, "progress-metadata", data_type='json')
    progress_val = progress_metadata.get("progress") if progress_metadata else 0
    overall_drift = progress_metadata.get("drift_vector_survey") if progress_metadata else [0, 0]  # X,Y drift vector in pixels for survey
    survey_image_size = progress_metadata.get("survey_image_size") if progress_metadata else 512  # Default to 512 if not available
    idx = progress_metadata.get("box_index") if progress_metadata else 0  # Use metadata if available

    # 3 drift scatter updated via Patch
    drift_fig = Patch()
    if overall_drift:
        existing_x = (current_drift_fig or {}).get("data", [{}])[0].get("x") or []
        if not existing_x and os.path.exists(os.path.join(pos_path, "scan-results.json")):
            # rebuild full history from scan-results as refreshed page lost it
            scan_data = data_io.local_retrieve(pos_path, "scan-results", data_type='json') 
            drift_history = [
                scan_data[k]["drift_vector_survey"]
                for k in sorted(filter(str.isdigit, scan_data), key=int)# ensure to exclude unrelated keys
                if scan_data[k].get("drift_vector_survey") is not None
            ]
            drift_fig["data"][0]["x"] = [p[0] for p in drift_history]
            drift_fig["data"][0]["y"] = [p[1] for p in drift_history]
        else:
            drift_fig["data"][0]["x"].append(overall_drift[0])
            drift_fig["data"][0]["y"].append(overall_drift[1])

        drift_fig["data"][1]["x"] = [overall_drift[0]]
        drift_fig["data"][1]["y"] = [overall_drift[1]]
        drift_fig["data"][1]["hovertemplate"] = f"{idx}: {overall_drift[0]}, {overall_drift[1]}<extra></extra>"
        half = (survey_image_size or 512) // 2
        drift_fig["layout"]["xaxis"] = {"range": [-half, half]}
        drift_fig["layout"]["yaxis"] = {"range": [-half, half]}
    percent = progress_val if progress_val is not None else 0

    # 4. Update the Survey Map (Green for completed, Cyan for pending)
    survey_image = data_io.local_retrieve(pos_path, "survey", data_type='png')
    fig = no_update
    if survey_image is not None:
        fig = px.imshow(survey_image, binary_string=True)
        shapes = []
        for i, b in enumerate(original_bboxes):
            shape = plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id'])
            # Logic: If current index is 5, boxes 0-4 are green, box 5 is yellow/cyan
            shape['line_color'] = 'green' if i < idx else ('yellow' if i == idx else 'cyan')
            shapes.append(shape)
        fig.update_layout(shapes=shapes, margin=dict(l=0, r=0, b=0, t=0), height=800, width=800)

    # 5. Handle Subscan Images
    current_src = no_update
    prev_src = no_update
    curr_img = data_io.local_retrieve(
        os.path.join(pos_path, "scans", f"scan-{str(idx).zfill(zfill_len)}"),
        f'subscan', data_type='png')
    if curr_img is not None:
        current_src = data_io.array_to_data_url_cv2(curr_img)
    
    if idx > 0:  
        prev_img = data_io.local_retrieve(
            os.path.join(pos_path, "scans", f"scan-{str(idx-1).zfill(zfill_len)}"), 
            f'subscan', data_type='png')
        if prev_img is not None:
            prev_src = data_io.array_to_data_url_cv2(prev_img)

    # 6. Handle Finished State
    new_pipeline_state = pipeline_state
    label_text = f"Scanning Box {idx+1}/{len(original_bboxes)} ({percent:.1f}%)"
    
    if acq_state == "Finished":
        new_pipeline_state = "finished"
        percent = 100
        label_text = "Pipeline Complete"

    return fig, str(percent), label_text, prev_src, current_src, new_pipeline_state, drift_fig

@callback(
    Output('tilt-shift-orientation', 'figure'),
    Output('stage-axis', 'data'),
    Input('button-survey-compucentric', 'n_clicks'),
    State("storage-folder-path","data"), 
    State('stage-axis', 'data'),
    State("input-survey-image-size", "value"),
    State("input-survey-dwell-time", "value"),
    State("input-survey-flyback-time", "value"),
    State("dropdown-control-stage", "value"),
    State("dropdown-control-lenses", "value"),
    State("dropdown-control-imaging", "value"),
)
def calc_compucentric(n, folder_path, axis_data, survey_image_size, dwell_time_us, flyback_time_us, stage_method, lenses_method, imaging_method):
    if n:

        compcal_path = os.path.join(folder_path, "compcal")
        os.makedirs(compcal_path, exist_ok=True)
        requests.post(
            f"{BACKEND_URL}/survey/compucentric-tilt-calibration", 
            json={
                "folder_path": compcal_path,
                "filename": "compcent",
                'direction' : '',
                'sign' : '',
                'survey_image_size': survey_image_size,
                'dwell_time_us': dwell_time_us,
                'flyback_time_us': flyback_time_us,
                "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
                "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
                "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method
            }
        )
        print('compucentric button pressed')
        print(compcal_path)
        axis_data = data_io.local_retrieve(compcal_path, "compucentric-data", 'json')
        print(axis_data)
        axis_data = axis_data.get('stage-axis')
        print('callbacks', axis_data, "axis")
        shift_orientation, tilt_orientation = axis_data if axis_data is not None else [(2,3), (3,1)]

        r = 3 # arrow length
        shift_axis = (r*math.sin(math.radians(shift_orientation[0])), r*math.cos(math.radians(shift_orientation[0])))
        tilt_axis = (r*math.sin(math.radians(tilt_orientation[0])), r*math.cos(math.radians(tilt_orientation[0])))         

        fig = go.Figure()
        fig.add_annotation(x=0, y=0,
            xref='x', axref='x', 
            yref='y', ayref= 'y',
            ax=shift_axis[0], ay=shift_axis[1],                
            showarrow=True,
            arrowhead=1, 
            arrowside='start', 
            text='positive x')
        fig.add_annotation(x=0, y=0,
            xref='x', axref='x', 
            yref='y', ayref= 'y',
            ax=shift_axis[1], ay=-shift_axis[0],                
            showarrow=True,
            arrowhead=1, 
            arrowside='start', 
            text='positive y')
        fig.add_annotation(x=0, y=0,
            xref='x', axref='x', 
            yref='y', ayref= 'y',
            ax=tilt_axis[0], ay=tilt_axis[1],                
            showarrow=True,
            arrowhead=1, 
            arrowside='start',
            arrowcolor='red',
            text= 'positive tilt x')
        fig.add_annotation(x=0, y=0,
            xref='x', axref='x', 
            yref='y', ayref= 'y',
            ax=tilt_axis[1], ay=-tilt_axis[0],                
            showarrow=True,
            arrowhead=1,
            arrowside='start',
            arrowcolor='red',
            text= 'positive tilt y')

        # fig.update_layout(showlegend=False)
        fig.update_layout(height=200, width=200, margin=dict(l=10, r=10, t=10, b=10))
        fig.update_layout(yaxis_range=[-4,4])
        fig.update_layout(xaxis_range=[-4,4])
        fig.update_annotations(hovertext='Tilt and move axes found via calibration')

        return [fig, axis_data]
    else:
        raise PreventUpdate

@callback(
    [
        Output('tilt-shift-text', 'children'),
    ],
    [
        Input("button-+x-compucentric", 'n_clicks'),
        Input("button--x-compucentric", 'n_clicks'),
        Input("button-+y-compucentric", 'n_clicks'),
        Input("button--y-compucentric", 'n_clicks'),
    ],
    [
        State("storage-folder-path","data"),
        State("dropdown-control-stage", "value"),
        State("dropdown-control-lenses", "value"),
        State("dropdown-control-imaging", "value"),
    ], prevent_initial_call =True
)
def tilt_compucentric(n1,n2,n3,n4, folder_path, stage_method, lenses_method, imaging_method): # n are buttons
    if folder_path:
        triggered = ctx.triggered_id
        clean_trig = triggered.replace('button-', '').replace('-compucentric', '')
        sign_move = clean_trig[0]
        direction = clean_trig[1]

        compcal_path = os.path.join(folder_path, "compcal")

        if triggered in ["button-+x-compucentric", "button--x-compucentric", "button-+y-compucentric", "button--y-compucentric"]:
            requests.post(
                f"{BACKEND_URL}/survey/compucentric-tilt-movement", 
                json={
                    "folder_path": compcal_path,
                    'direction' : direction,
                    'sign' : sign_move,
                    "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
                    "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
                    "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method
                    }
            )
            return [f'tilt {sign_move}{direction} button pressed']
    else:
        raise PreventUpdate

# @callback(
#     Output('tilt-shift-text', 'children',allow_duplicate=True),
#     Input("button-+y-compucentric", 'n_clicks'),
#     State("storage-folder-path","data"), prevent_initial_call =True
# )
# def pos_y_compucentric(n, folder_path):
#     if n:
#         requests.post(
#             f"{BACKEND_URL}/survey/compucentric-tilt-movement", 
#             json={"folder_path": folder_path}
#         )
#         print('tilt +y button pressed')

#         return 'tilt +y button pressed'
#     else:
#         raise PreventUpdate

# @callback(
#     Output('tilt-shift-text', 'children'),
#     Input("button--x-compucentric", 'n_clicks'),
#     State("storage-folder-path","data"), 
# )
# def neg_x_compucentric(n, folder_path):
#     if n:
#         requests.post(
#             f"{BACKEND_URL}/survey/compucentric-tilt-movement", 
#             json={"folder_path": folder_path}
#         )
#         print('tilt -x button pressed')

#         return 'tilt -x button pressed'
#     else:
#         raise PreventUpdate
    
# @callback(
#     Output('tilt-shift-text', 'children'),
#     Input("button--y-compucentric", 'n_clicks'),
#     State("storage-folder-path","data"), 
# )
# def neg_y_compucentric(n, folder_path):
#     if n:
#         requests.post(
#             f"{BACKEND_URL}/survey/compucentric-tilt-movement", 
#             json={"folder_path": folder_path}
#         )
#         print('tilt -y button pressed')

#         return 'tilt -y button pressed'
#     else:
#         raise PreventUpdate

# Analysis things here
# colour scheme matching progress checker
_ANALYSIS_STATUS_COLOUR = {
    "pending-a": "cyan",
    "running-a": "yellow",
    "pending-b": "DeepSkyBlue",
    "running-b": "orange",
    "complete":  "green",
    "failed":    "MediumPurple",
    "skipped":   "red",
    "not-scanned": "gray"
}

@callback(
    Output('interval-check-analysis-progress', 'disabled', allow_duplicate=True),
    Output('storage-state-analysis', 'data', allow_duplicate=True),
    Input('stage-index-counter', 'data'),
    prevent_initial_call=True,
)
def reset_analysis_on_new_position(_):
    """Re-enable the analysis interval whenever the position
    index changes (new experiment created or new scan started), so a previously
    completed run does not keep the interval permanently disabled."""
    return False, None


@callback(
    Output('storage-state-analysis', 'data'),
    Input('interval-check-analysis-progress', 'n_intervals'),
    State('storage-state-analysis', 'data'),
    State('storage-folder-path', 'data'),
    State('stage-index-counter', 'data'),
    prevent_initial_call=True
)
def trigger_analysis(n_intervals, analysis_state, folder_path, current_index):
    """
    Every interval tick, check box statuses and if there are entries, do th following:
    1) determine overall state based on the status of all boxes
    2) get number of completed boxes
    3) If pending boxes and not already running, POST to backend to start analysis
    4) Update storage-state-analysis to trigger display update if state changed or if number of completed boxes changed"""
    if not folder_path:
        raise PreventUpdate

    pos_path = os.path.join(folder_path, f"pos-{current_index}")
    try:
        data = data_io.local_retrieve(pos_path, "scan-results", data_type='json')
    except Exception:
        raise PreventUpdate  # mid-write torn read — retry next tick
    if not data:
        raise PreventUpdate

    scan_entries = {k: v for k, v in data.items() if k.isdigit()}
    if not scan_entries:
        raise PreventUpdate

    statuses = {v.get("analysis_status") for v in scan_entries.values()}
    _PENDING = {"pending-a", "pending-b"}
    _RUNNING = {"running-a", "running-b"}

    if statuses & _PENDING: # check if they intersect aka pending or running boxes
        new_state = "pending"
    elif statuses & _RUNNING:
        new_state = "running"
    elif statuses <= {"complete", "skipped", "failed"}:
        new_state = "complete"
    else:
        raise PreventUpdate

    #how many boxes are done (either success skip or failed) and previous states if available
    n_complete = sum(1 for v in scan_entries.values() if v.get("analysis_status") in {"complete", "skipped", "failed"})
    prev_state = analysis_state.get("state") if analysis_state else None
    prev_complete = analysis_state.get("complete") if analysis_state else -1

    # If pending boxes and not running, post to backend to analyse
    if new_state == "pending" and prev_state != "running":
        pending_indices = [
            int(k) for k, v in scan_entries.items()
            if v.get("analysis_status") in {"pending-a", "pending-b"}
        ]
        requests.post(
            f"{BACKEND_URL}/analysis/run-analysis",
            json={"folder_path": pos_path, "box_indices": pending_indices},
        )
        return {"state": "running", "complete": n_complete}

    # else already running so just update if new box done
    if new_state == "running" and n_complete != prev_complete:
        return {"state": "running", "complete": n_complete}

    #to change state overall and trigger display
    if new_state != prev_state:
        return {"state": new_state, "complete": n_complete}

    raise PreventUpdate


@callback(
    Output('graph-analysis-progress', 'figure'),
    Output('progress-bar-analysis', 'value'),
    Output('progress-bar-analysis-label', 'children'),
    Output('interval-check-analysis-progress', 'disabled'),
    Input('storage-state-analysis', 'data'),
    State('storage-folder-path', 'data'),
    State('stage-index-counter', 'data'),
    prevent_initial_call=True
)
def check_analysis_progress(analysis_state, folder_path, current_index):
    """Update display only when storage-state-analysis changes AKA when states changes or n_complete increments"""
    if not folder_path or not analysis_state:
        raise PreventUpdate

    pos_path = os.path.join(folder_path, f"pos-{current_index}")
    data = data_io.local_retrieve(pos_path, "scan-results", data_type='json')
    if not data:
        raise PreventUpdate

    scan_entries = {k: v for k, v in data.items() if k.isdigit()} # for box enties
    if not scan_entries:
        raise PreventUpdate

    #survey map coloured by analysis status
    survey_image = data_io.local_retrieve(pos_path, "survey", data_type='png')
    fig = no_update
    if survey_image is not None:
        fig = px.imshow(survey_image, binary_string=True)
        shapes = []
        original_bboxes = data_io.local_retrieve(pos_path, "coords", data_type='json') or []
        for i, b in enumerate(original_bboxes):
            shape = plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id'])
            status = scan_entries.get(str(i), {}).get("analysis_status", "not-scanned")
            shape['line_color'] = _ANALYSIS_STATUS_COLOUR.get(status, "gray")
            shapes.append(shape)

        # add hovertext via hidden scatter in centroid location
        cx = [(b['bbox'][1] + b['bbox'][3]) / 2 for b in original_bboxes]
        cy = [(b['bbox'][0] + b['bbox'][2]) / 2 for b in original_bboxes]
        hover_texts = [
            f"{i}: {scan_entries.get(str(i), {}).get('analysis_status', 'not-scanned')}" for i, b in enumerate(original_bboxes)
        ]
        fig.add_trace(go.Scatter(
            x=cx, y=cy,
            mode='markers',
            marker=dict(size=12, opacity=0),
            hoverinfo='text',
            hovertext=hover_texts,
            showlegend=False,
        ))
        fig.update_layout(shapes=shapes, margin=dict(l=0, r=0, b=0, t=0), height=800, width=800)

    #progress bar and label
    done = sum(1 for v in scan_entries.values() if v.get("analysis_status") in ["complete", "skipped", "failed"])
    total = data.get("total_num_boxes") or len(scan_entries)
    percent = (done / total * 100) if total > 0 else 0

    # Check if caught up and all entries done
    all_done = done >= total and len(scan_entries) >= total
    label_text = "Analysis Complete" if all_done else f"Analysed {done}/{total} ({percent:.1f}%)"

    return fig, str(percent), label_text, all_done