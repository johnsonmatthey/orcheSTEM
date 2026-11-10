import requests
import os
from pathlib import Path
from dash import Input, Output, State, callback, no_update, ctx, Patch, ALL
# Assuming these are your local helper modules
from util import data_io, plotly_utils, positions_io
from util.logging_setup import set_experiment_log_target
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
from app import BACKEND_URL, BASE_LOCAL_PATH
import math
from pages.survey import FEATURE_REQUIREMENTS, _FEATURE_BOX_STYLE
from pages.survey_image_segmentation import _SEGMENTATION_METHODS
from pages.overview_manager import build_canvas_figure, build_position_rows, _STATUS_BADGE_COLOURS
from pages.progress_manager import empty_drift_figure
from pages.calibration_manager import build_connection_status
import dash_mantine_components as dmc
import glob

# ONLY FOR FORCING FOR USE IN TESTS OFFLINE!
TEST_IMAGING_METHOD = None #"qd_scanengine"#'gatan'
TEST_LENSES_METHOD = None #'pyjem'
TEST_STAGE_METHOD = None # 'pyjem'

def acquisition_method_str(pipeline_config):
    """
    helper for converting acquisition type in pipeline-config.json to string for frontend display
    """
    if not pipeline_config:
        return None
    methods = []
    if pipeline_config.get("stem4d"):
        methods.append("4D-STEM")
    if pipeline_config.get("stemsi"):
        methods.append("STEM SI")
    return " + ".join(methods) if methods else "Survey only"

def get_position_infos(folder_path):
    """
    per pos-X folder, build a row of table data in the given orderbased on acquisition, threshold, and pipeline states.
    Grab these from the jsons. Order rows according to the position_scans.json
    """
    if not folder_path or not os.path.isdir(folder_path):
        return []

    meta = positions_io.load_positions_meta(folder_path)

    pos_infos = []
    for pos in meta["positions"]:
        pos_index = pos["pos_index"]
        pos_path = os.path.join(folder_path, f"pos-{pos_index}")
        pipeline_config = data_io.local_retrieve(pos_path, "pipeline-config", data_type="json")
        threshold_metadata = data_io.local_retrieve(pos_path, "threshold-metadata", data_type="json")

        pos_infos.append({
            "pos_index": pos_index,
            "status": positions_io.get_position_status(folder_path, pos_index),
            "threshold_method": (threshold_metadata or {}).get("selected_method"),
            "acquisition_method": acquisition_method_str(pipeline_config),
            "included": pos.get("included", True),
            "stage_position": data_io.local_retrieve(pos_path, "stage-position", data_type="json"),
        })
    return pos_infos

@callback(
    Output("div-position-list", "children"),
    Output("storage-positions-list-cache", "data"),
    Output("graph-positions-overview", "figure"),
    Input("experiment-state", "data"),
    Input("stage-index-active", "data"),
    Input("storage-state-pipeline", "data"),
    Input("storage-positions-meta", "data"),
    State("storage-folder-path", "data"),
    State("storage-positions-list-cache", "data"),
)
def refresh_position_list(experiment_state, stage_index, pipeline_state, positions_meta, folder_path, cached_summaries):
    """
    Rebuild the list of positions when either positions change (positions_meta), pipeline changess (pipeline_state), 
    experiment created (experiment_state) or new pos (stage-index-active)
    """
    pos_infos = get_position_infos(folder_path)
    fig = build_canvas_figure(pos_infos, selected_pos_index=stage_index)
    if pos_infos == cached_summaries: # just to prevent stage-index-active and _pipeline_state from retriggering the row rebuild too many times
        # the position graph still needs to update just to show which new position is selected
        return no_update, no_update, fig
    return build_position_rows(pos_infos), pos_infos, fig


@callback(
    Output({"type": "badge-position-status", "index": ALL}, "children"),
    Output({"type": "badge-position-status", "index": ALL}, "color"),
    Output("interval-check-batch-progress", "disabled"),
    Input("interval-check-batch-progress", "n_intervals"),
    State("storage-folder-path", "data"),
    State({"type": "badge-position-status", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def refresh_position_statuses(_n_intervals, folder_path, badge_ids):
    """
    Patches each badge's text/colour while a batch runs for progress updates. If done, stops interval
    """
    statuses = [positions_io.get_position_status(folder_path, b["index"]) for b in badge_ids]
    any_running = "running" in statuses
    colours = [_STATUS_BADGE_COLOURS.get(status, "gray") for status in statuses]

    # need the _ check if 'not_configured' status or future ones in _STATUS_COLOURS etc. 
    labels = [status.replace("_", " ") for status in statuses]
    return labels, colours, not any_running


@callback(
    Output("storage-positions-included", "data"),
    Input({"type": "checkbox-position-include", "index": ALL}, "checked"),
    State("storage-folder-path", "data"),
    prevent_initial_call=True,
)
def toggle_position_included(checked_list, folder_path):
    """
    storing in the json whether to include. NOTE using different store as otherwise will trigger infinite loop
    Caused by the meta store triggering the rebuilding of the pos table which then triggers this again etc.
    """
    if not folder_path or not ctx.triggered:
        raise PreventUpdate
    pos_index = ctx.triggered_id["index"]
    included = ctx.triggered[0]["value"]
    # print("here many times: ", ctx.triggered)

    meta = positions_io.load_positions_meta(folder_path)
    current = next((p["included"] for p in meta["positions"] if p["pos_index"] == pos_index), None)
    if current == included:
        raise PreventUpdate
    # store in json
    positions_io.set_position_included(folder_path, pos_index, included)
    return included


@callback(
    Output("storage-positions-meta", "data", allow_duplicate=True),
    Input({"type": "btn-position-up", "index": ALL}, "n_clicks"),
    Input({"type": "btn-position-down", "index": ALL}, "n_clicks"),
    State("storage-folder-path", "data"),
    prevent_initial_call=True,
)
def reorder_position(up_clicks, down_clicks, folder_path):
    """
    update orderings based on pressing up or down and store in position_scans.json
    """
    if not folder_path or not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    pos_index = ctx.triggered_id["index"]
    direction = -1 if ctx.triggered_id["type"] == "btn-position-up" else 1
    return positions_io.move_position(folder_path, pos_index, direction)

@callback(
    Output('stage-index-active', 'data', allow_duplicate=True),
    Input('button-new-position', 'n_clicks'),
    State('storage-folder-path', 'data'),
    State("dropdown-control-stage", "value"),
    State("dropdown-control-lenses", "value"),
    State("dropdown-control-imaging", "value"),
    prevent_initial_call=True,
)
def create_new_position(n_clicks, folder_path, stage_method, lenses_method, imaging_method):
    """
    create a new pos-x folder at the stage's current location. NOTE does not scan, but will grab stage location for now
    TODO remove stage grab if it will be done in the scan too anyway? Timewise, it is inconsequential
    """
    if not n_clicks or not folder_path:
        raise PreventUpdate
    #make the pos folder
    max_idx = positions_io.get_latest_pos_index(folder_path)
    new_index = max_idx + 1
    pos_path = os.path.join(folder_path, f"pos-{new_index}")
    Path(pos_path).mkdir(parents=True, exist_ok=True)
    Path(pos_path, 'scans').mkdir(parents=True, exist_ok=True)
    Path(pos_path, 'drift_survey').mkdir(parents=True, exist_ok=True)
    # grab and store stage position
    requests.post(f"{BACKEND_URL}/survey/stage-position", json={
        "folder_path": pos_path,
        "stage_index": new_index,
        "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD,
        "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD,
        "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD
    })
    return new_index

@callback(
    Output('stage-index-active', 'data', allow_duplicate=True),
    Output('tab-pos-display', 'value', allow_duplicate=True),
    Input({"type": "btn-position-open", "index": ALL}, "n_clicks"),
    State("storage-folder-path", "data"),
    prevent_initial_call=True,
)
def open_position(_n_clicks_list, folder_path):
    """switch the app's working position to the one whose 'Open' button was clicked.
    jump to Progress if a batch acquisition is currently running for it, otherwise Scan"""
    # NOTE inputs also fire when the row set is remade, so only react to a real click
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    pos_index = ctx.triggered_id["index"]
    status = positions_io.get_position_status(folder_path, pos_index) if folder_path else None
    target_tab = "progress" if status in ["running", 'done'] else "scan"
    return pos_index, target_tab



@callback(
    Output("storage-folder-path",'data'),
    Output('experiment-state','data'),
    Output("text-input-experiment-name", "disabled"),
    Output("stage-index-active", "data", allow_duplicate=True),
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
        set_experiment_log_target(folder_path)
        return folder_path, False, True, 0, no_update
    if url_pathname == '/':
        experiment_state = os.path.isdir(folder_path)
        # If experiment exists, get the last pos index and use that to determine pipeline state
        if experiment_state:
            # create experiment again, which will instead only reattach experiment log after a restart for backend
            requests.post(f"{BACKEND_URL}/create-experiment", json={"folder_path": folder_path})
            set_experiment_log_target(folder_path) # reattach for frontend now 
            latest_idx = positions_io.get_latest_pos_index(folder_path)
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
    Input("store-microscope-session", "data"), # changes once a connect has finished, so the available methods are refreshed
)
def populate_microscope_dropdowns(n_button, session_store):
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
    Output("dropdown-instrument", "data"),
    Output("dropdown-instrument", "value"),
    Output("store-microscope-session", "data"),
    Output("div-connection-status", "children"),
    Input("button-calibration-connect", "n_clicks"),
    State("dropdown-instrument", "value"),
    State("dropdown-holder", "value"),
    running=[(Output("button-calibration-connect", "disabled"), True, False)], # blocks repeat clicks while a connect is in progress
)
def load_or_connect_microscope(n_clicks, instrument_id, holder):
    """On page load show the backend's active instrument; on button press switch to the chosen instrument and holder and report each connection."""
    try:
        if ctx.triggered_id == "button-calibration-connect":
            resp = requests.post(f"{BACKEND_URL}/microscope/connect", json={"instrument_id": instrument_id, "holder": holder})
        else:
            resp = requests.get(f"{BACKEND_URL}/microscope/session")
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            return no_update, no_update, no_update, dmc.Alert(str(detail), color="red", title="Could not connect")
        session = resp.json()
    except Exception as e:
        return no_update, no_update, no_update, dmc.Alert(str(e), color="red", title="Backend unreachable")
    instruments = [{"value": i["value"], "label": i["label"]} for i in session["instruments"]]
    return instruments, session["instrument"], session, build_connection_status(session)

@callback(
    Output("dropdown-holder", "data"),
    Output("dropdown-holder", "value"),
    Input("dropdown-instrument", "value"),
    Input("store-microscope-session", "data"),
)
def update_holder_options(instrument_id, session):
    """Holders follow the selected instrument; the connected instrument keeps its connected holder, others start at their first."""
    if not instrument_id or not session:
        return [], None
    holders = next((i["holders"] for i in session["instruments"] if i["value"] == instrument_id), [])
    if instrument_id == session["instrument"] and session["holder"] in holders:
        return holders, session["holder"]
    return holders, (holders[0] if holders else None)

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
    Output('storage-drift-region-box-coords', 'data', allow_duplicate=True),
    Output('image-survey-driftregion', 'src', allow_duplicate=True),
    Input('button-scan', 'n_clicks'),
    Input('experiment-state', 'data'), # This triggers on page load when state is set
    Input('stage-index-active', 'data'), # Reload/clear when the open position changes
    State('storage-folder-path', 'data'),
    State("input-survey-image-size", "value"),
    State("input-survey-dwell-time", "value"),
    State("input-survey-flyback-time", "value"),
    State("dropdown-control-stage", "value"),
    State("dropdown-control-lenses", "value"),
    State("dropdown-control-imaging", "value"),
    prevent_initial_call=True
)
def scan(n_click, experiment_state, current_index, folder_path, survey_image_size, survey_dwell_time, survey_flyback_time, stage_method, lenses_method, imaging_method):
    if not folder_path:
        raise PreventUpdate
    
    triggered = ctx.triggered_id
    idx = current_index if current_index is not None else 0
    pos_path = os.path.join(folder_path, f"pos-{idx}")

    # User clicked the scan button - scan the currently open position and DONT make a new one as before
    if triggered == 'button-scan':
        requests.post(f"{BACKEND_URL}/survey/scan", json={
            "folder_path": pos_path, 
            "filename": f"survey",
            "survey_image_size": survey_image_size, # refers to the original survey size. Needed for subscanning for some hardware
            "dwell_time_us": survey_dwell_time,
            "flyback_time_us": survey_flyback_time,
            "is_subscan": False,
            "box_coords": None, # full image scan as default
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method
        })
        # update the position just in case as well as could have moved location
        requests.post(f"{BACKEND_URL}/survey/stage-position", json={
            "folder_path": pos_path, 
            "stage_index": idx,
            "stage_method": stage_method if TEST_STAGE_METHOD is None else TEST_STAGE_METHOD, # stage_method
            "lenses_method": lenses_method if TEST_LENSES_METHOD is None else TEST_LENSES_METHOD, # lenses_method
            "imaging_method": imaging_method if TEST_IMAGING_METHOD is None else TEST_IMAGING_METHOD # imaging_method

        })
        image = data_io.local_retrieve(pos_path, f"survey", data_type='png')
        if image is not None:
            fig = px.imshow(image, binary_string=True)
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), dragmode=False, xaxis={'visible': False, 'fixedrange': True}, yaxis={'visible': False, 'fixedrange': True})
            return fig, no_update, no_update
        
        return no_update, no_update, no_update

    # Initial Load / Experiment State changed / Position switched - just retrieve and display
    if experiment_state is True or triggered == "stage-index-active":
        image = data_io.local_retrieve(pos_path, "survey", data_type='png')
        if image is not None:
            fig = px.imshow(image, binary_string=True)
            # shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in bboxes]
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), dragmode=False, xaxis={'visible': False, 'fixedrange': True}, yaxis={'visible': False, 'fixedrange': True})

            #restore the previously-acquired drift region box for this position if exists too
            drift_region = data_io.local_retrieve(os.path.join(pos_path, 'drift_survey'), "drift-region", data_type='json')
            box_coords = drift_region.get("box_coords") if drift_region else None
            drift_src = None
            if box_coords:
                fig.update_layout(shapes=[{
                    "type": "rect",
                    "x0": box_coords[2],
                    "y0": box_coords[3],
                    "x1": box_coords[0] + box_coords[2],
                    "y1": box_coords[1] + box_coords[3],
                    "line": {"color": "red", "width": 2},
                }])
                drift_image = data_io.local_retrieve(os.path.join(pos_path, "drift_survey"), "drift_survey-0", data_type='png')
                if drift_image is not None:
                    drift_src = data_io.array_to_data_url_cv2(drift_image)

            return fig, box_coords, drift_src

        # New position is opened so clear old survey/drift visuals from the previous position ready for new scans
        if triggered == "stage-index-active":
            return go.Figure(), None, None  

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
    # State('stage-index-active', 'data'),
    prevent_initial_call=True,
)
def place_drift_box(click_data, method, region_size, current_fig):
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
    State('stage-index-active', 'data'),
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

    #Store box coords for reloading (becomes unneccesary after pipeline) - this is just for replotting if not configured properly before then
    data_io.local_store(os.path.join(pos_path, 'drift_survey'), 'drift-region', data={"box_coords": box_coords, "method": method}, data_type='json')

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
    # Input("button-threshold", "n_clicks"),
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
    Input('stage-index-active', 'data'),
    State("segment-segcontrol-method", "value"),
    prevent_initial_call=True,
)
def run_segmentation(
    # n, 
    experiment_state, 
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
    # print(triggered, experiment_state)
    # check experiment state trigger and if experiment state is true -> means refresh. Otherwise change when index changes
    if (triggered == "experiment-state" and experiment_state is True) or triggered == "stage-index-active":
        overlay_image = data_io.local_retrieve(pos_path, "threshold-overlay", "object")
        if overlay_image is not None:
            return data_io.array_to_data_url_cv2(overlay_image)
        if triggered == "stage-index-active":
            return None  # clear stale overlay from the previous position
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
    Input("tab-pos-display", "value"),
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
    Input('stage-index-active', 'data'),
    prevent_initial_call=True 
)
def watershed_and_interaction_manager(pos_tab_value, n_cluster, n_reset, exp_state, relayout_data, 
                                      s_val, folder_path, original_bboxes, current_filtered,
                                      sampling, survey_size, full_size, 
                                      current_index):
    
    if not folder_path:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")

    triggered = ctx.triggered_id
    # print('cluster trigger:' , triggered)
    # Cluster button pressed, apply watershed, cluster, and then display
    if triggered == "button-cluster":
        requests.post(f"{BACKEND_URL}/cluster/watershed", json={
            "folder_path": pos_path, "s_value": s_val, "sampling_res": sampling,
            'survey_image_size': survey_size, 'full_image_size': full_size
        })
        bboxes = data_io.local_retrieve(pos_path, 'coords', data_type='json')
        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')
        if image is None or bboxes is None: raise PreventUpdate

        fig = px.imshow(image, binary_string=True)
        shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in bboxes]
        fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawclosedpath', newshape=dict(line_color='cyan'))
        return fig, bboxes, bboxes

    # We trigger if we switched to the cluster tab, the experiment state changed, or the open position changed
    if (triggered == "tab-pos-display" and pos_tab_value == "cluster") or \
       (triggered == "experiment-state" and exp_state is True) or \
       triggered == "stage-index-active":
        saved_coords = data_io.local_retrieve(pos_path, 'coords', data_type='json')
        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')

        # Position has cluster data, display
        if image is not None and saved_coords is not None:
            fig = px.imshow(image, binary_string=True)
            shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in saved_coords]
            # print(len(shapes))
            fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawclosedpath', newshape=dict(line_color='cyan'))
            return fig, saved_coords, saved_coords

        #Position switched but has no cluster saved yet - clear old figure/boxes from the previously open position
        if triggered == "stage-index-active":
            fig = go.Figure()
            if image is not None:
                fig = px.imshow(image, binary_string=True)
                fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), dragmode='drawclosedpath')
            return fig, None, None
        

    # Reset the boxes that were selected, showing all now
    if triggered == "btn-reset-boxes":
        if not original_bboxes: return no_update, no_update, no_update

        image = data_io.local_retrieve(pos_path, 'survey', data_type='png')
        fig = px.imshow(image, binary_string=True)
        shapes = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in original_bboxes]
        fig.update_layout(height=800, width=800, margin=dict(l=0, r=0, b=0, t=0), shapes=shapes, dragmode='drawclosedpath')
        return fig, no_update, original_bboxes

    # based on the dragged lasso, only include boxes whose centroids lie within
    if triggered == "graph-survey-image-clustering" and relayout_data:
        if 'shapes' in relayout_data and len(relayout_data['shapes']) > 0:
            latest_shape = relayout_data['shapes'][-1]
            if latest_shape.get('type') == 'path':
                roi = plotly_utils.plotly_path_to_polygon(latest_shape)
            else:
                roi = plotly_utils.plotly_shape_to_skimage(latest_shape)
            source = original_bboxes if original_bboxes else current_filtered
            if not source: raise PreventUpdate

            filtered = [b for b in source if plotly_utils.is_inside(b['centroid'], roi)]
            data_io.local_store(pos_path, 'coords', data=filtered, data_type='json')
            
            patch_fig = Patch()
            patch_fig['layout']['shapes'] = [plotly_utils.skimage_to_plotly_shape(b['bbox'], b['id']) for b in filtered]
            return patch_fig, no_update, filtered

    raise PreventUpdate


@callback(
    Output("button-store-pipe", "disabled"),
    Input("storage-bounding-boxes", "data"),
)
def toggle_search_button(bounding_boxes):
    "Wait until cluster boxes exists before allowed to store"
    return not bounding_boxes


@callback(
    Output('storage-state-pipeline','data', allow_duplicate=True),# Note interval is located in pages/progress_manager.py
    Output("tab-main-display", "value", allow_duplicate=True),
    Input("button-store-pipe","n_clicks"),
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
    State('stage-index-active', 'data'),
    State("input-drift-dwell-time", "value"),
    State("input-drift-flyback-time", "value"),
    State("storage-drift-region-box-coords", "data"),
    State("input-survey-dwell-time", "value"),
    State("input-survey-flyback-time", "value"),
    prevent_initial_call=True
)
def store_pipeline_configuration(
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
                    "savepath": stem4d_savepath,
                    "dwell_time_us": stem4d_dwell_time_us,
                    "flyback_time_us": stem4d_flyback_time_us,
                    "bitdepth": stem4d_bitdepth,
                }
            if enable_si:
                config_preferences["stemsi_settings"] = {
                    "enable_eels": enable_si_eels,
                    "enable_eds": enable_si_eds,
                    "enable_custom": enable_si_custom,
                    "dwell_time_us": si_dwell_time,
                    "flyback_time_us": si_flyback_time,
                    "subscan_size": si_subscan,
                    "passes": si_passes,
                }

            requests.post(f"{BACKEND_URL}/microscope/config", json=config_preferences)
            print("Updated microscope configuration with current user preferences.")

            # store this as a json for the backend to read once everything is ready
            pipeline_config={
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
                    'box_coords': drift_box_coords,
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
            # )
            print("pipeline stored in:", pos_path)
            data_io.local_store(pos_path, 'pipeline-config', data=pipeline_config, data_type='json')

            return "started", "overview" 
        else:
            raise PreventUpdate
    else:
        raise PreventUpdate

@callback(
    Output("text-batch-status", "children"),
    Output("interval-check-batch-progress", "disabled", allow_duplicate=True),
    Input("button-begin-all", "n_clicks"),
    State("storage-folder-path", "data"),
    prevent_initial_call=True,
)
def begin_all_positions(n_click, folder_path):
    """
    This is where the overall serach now begins!
    """
    if not n_click or not folder_path:
        raise PreventUpdate

    pos_meta = positions_io.load_positions_meta(folder_path)
    pos_order = [
        pos["pos_index"] for pos in pos_meta["positions"]
        if pos.get("included", True) and positions_io.get_position_status(folder_path, pos["pos_index"]) == "ready"
    ]
    if not pos_order:
        return "No 'ready' positions ticked to run - configure and save at least one position first.", no_update

    requests.post(f"{BACKEND_URL}/pipeline/search-pipeline-batch", json={
        "folder_path": folder_path,
        "pos_order": pos_order,
    })
    return f"Started: running positions {pos_order} in order.", False #start the interval checks for batch progress

@callback(
    Output('graph-survey-progress', 'figure'),
    Output('progress-bar-section', 'value'),
    Output('progress-bar-label', 'children'), # Changed 'value' to 'children' (standard for labels)
    Output('img-prev-scan', 'src'),
    Output('img-current-scan', 'src'),
    Output('storage-state-pipeline', 'data', allow_duplicate=True),
    Output('graph-overall-drift', 'figure'),
    Input('interval-check-progress', 'n_intervals'),
    Input('stage-index-active', 'data'), # Reload/clear when the open position changes
    State('storage-state-pipeline', 'data'),
    State('storage-folder-path', 'data'),
    State("storage-bounding-boxes", "data"), 
    State('graph-overall-drift', 'figure'),
    prevent_initial_call=True
)
def check_progress(n_interval, current_index, pipeline_state, folder_path, original_bboxes, current_drift_fig):
    if not folder_path:
        raise PreventUpdate
    pos_path = os.path.join(folder_path, f"pos-{current_index}")
    triggered = ctx.triggered_id
    switched_position = triggered == "stage-index-active"

    # If bboxes aren't in the store yet (e.g. after page reload or a position switch), try loading from disk
    if switched_position or not original_bboxes:
        original_bboxes = data_io.local_retrieve(pos_path, "coords", data_type='json')
        if not original_bboxes:
            if switched_position:
                # No scan data for this position yet - clear old visuals from the previous one
                return go.Figure(), "0", "Not started", None, None, no_update, empty_drift_figure()
            raise PreventUpdate
    zfill_len = len(str(len(original_bboxes)))
    # 1. Check current acquisition status
    # If the file hasn't been created yet, the pipeline is still initialising
    acq_state = data_io.local_retrieve(pos_path, "long-acquisition-state", data_type='json')
    if acq_state is None:
        if switched_position:
            return go.Figure(), "0", "Not started", None, None, no_update, empty_drift_figure()
        return no_update, str(0), "Initialising...", no_update, no_update, "started", no_update

    # 2. Retrieve Progress Data
    # box_index = data_io.local_retrieve(pos_path, "box-index", data_type='object')
    progress_metadata = data_io.local_retrieve(pos_path, "progress-metadata", data_type='json')
    progress_val = progress_metadata.get("progress") if progress_metadata else 0
    overall_drift = progress_metadata.get("drift_vector_survey") if progress_metadata else [0, 0]  # X,Y drift vector in pixels for survey
    survey_image_size = progress_metadata.get("survey_image_size") if progress_metadata else 512  # Default to 512 if not available
    idx = progress_metadata.get("box_index") if progress_metadata else 0  # Use metadata if available

    # 3 drift scatter - rebuilt fully on position switch, patched per iteration otherwise
    drift_fig = Patch()
    if overall_drift:
        existing_traces = (current_drift_fig or {}).get("data") or []
        existing_x = (existing_traces[0].get("x") if existing_traces else None) or [] # check if existing x values
        # check if new position or an empty plot with existing data
        needs_rebuild = switched_position or (not existing_x and os.path.exists(os.path.join(pos_path, "scan-results.json")))
        if needs_rebuild:
            # rebuild full history from scan-results (refreshed page or new position lost the running Patch state)
            scan_data = data_io.local_retrieve(pos_path, "scan-results", data_type='json') 
            drift_history = [
                scan_data[k]["drift_vector_survey"]
                for k in sorted(filter(str.isdigit, scan_data), key=int)# ensure to exclude unrelated keys
                if scan_data[k].get("drift_vector_survey") is not None
            ] if scan_data else []
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
        drift_fig["layout"]["yaxis"] = {"range": [half, -half]}
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

    # 5. Handle Subscan Images # TODO this needs to be compatible with differnt filetypes
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

    # 6. check if finished/ current progress label
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
    Input('stage-index-active', 'data'),
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
    State('stage-index-active', 'data'),
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
    Input('stage-index-active', 'data'), # Reload/clear when the open position changes
    State('storage-folder-path', 'data'),
    prevent_initial_call=True
)
def check_analysis_progress(analysis_state, current_index, folder_path):
    """Update display when storage-state-analysis changes, or immediately clear/reload when the open position switches"""
    if not folder_path:
        raise PreventUpdate

    triggered = ctx.triggered_id
    switched_position = triggered == "stage-index-active"
    if not switched_position and not analysis_state:
        raise PreventUpdate

    pos_path = os.path.join(folder_path, f"pos-{current_index}")
    data = data_io.local_retrieve(pos_path, "scan-results", data_type='json')
    scan_entries = {k: v for k, v in data.items() if k.isdigit()} if data else {} # for box enties
    if not scan_entries:
        if switched_position:
            # No analysis data for this position yet - clear old visuals from the previous one
            return go.Figure(), "0", "Not started", True
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