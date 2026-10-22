from pydantic import BaseModel, ConfigDict

# Experiment setup
class ExperimentRequest(BaseModel):
    folder_path: str

# General scanning for survey and drift correction and stage saving
class ScanAndSaveRequest(BaseModel):
    folder_path:str
    filename:str
    survey_image_size:int
    dwell_time_us:int
    flyback_time_us:int
    is_subscan:bool
    box_coords:list | None = None
    # hardware options
    stage_method:str
    lenses_method:str
    imaging_method:str

class SaveDefocusRequest(BaseModel):
    folder_path: str
    filename: str
    # hardware options
    stage_method: str
    lenses_method: str
    imaging_method: str

class SaveStageRequest(BaseModel):
    folder_path:str
    stage_index: int
    # hardware options
    stage_method:str
    lenses_method:str
    imaging_method:str

# Segmentation methods
class ThresholdRequest(BaseModel):
    folder_path: str
    range: list
    median_val: int

class ThinRequest(BaseModel):
    folder_path : str
    dropdown_smoothing : str
    input_smoothing : float
    dropdown_background : str
    input_background : float
    polarity_selector: str
    dropdown_segmentation : str
    input_threshold_value : float
    input_threshold_sigma : float
    dropdown_watershed : str
    input_watershed_distance : int
    input_min_open : int
    input_min_close : int
    input_min_object : int
    input_min_hole : int

class MLRequest(BaseModel):
    folder_path: str
    model_ip: str
    model_port: int
    # median_val: int

class SegClassicalRequest(BaseModel):
    folder_path: str
    median_val: int


# Clustering
class ClusterRequest(BaseModel):
    folder_path: str
    s_value: int
    sampling_res: int = 128 # Default value
    overlap: int = 0        # Default value
    full_image_size:int
    survey_image_size:int

# Pipeline search
class DriftSettings(BaseModel):
    """
    These are the default settings for drift correction
    """
    drift_every: int  = 1
    dwell_time_us: int = 15
    flyback_time_us: int = 100
    box_coords: list | None = None      # (width, height, x0, y0) or None for full survey
    window_type: str = "hanning"
    max_shift_pixel: int | None = None  # None = auto (half survey size)

class FocusSettings(BaseModel):
    focus_every: int = 1
    focus_method: str = "custom" # options are "center", "grid", "random"
    focus_region: str = "scan_box" # options are "scan_box", "full" or "drift_box"

class STEM4DSettings(BaseModel):
    dwell_time_us: int = 1000 
    flyback_time_us: int = 10000 
    bitdepth: int = 6
    savepath: str = ""

class STEMSISettings(BaseModel):
    enable_eels: bool = False
    enable_eds: bool = False
    enable_custom: bool = False
    dwell_time_us: int = 1000 
    flyback_time_us: int = 10000 
    subscan_size: int = 1
    passes: int = 1

class SearchPipelineRequest(BaseModel):
    folder_path: str
    sampling: int
    full_image_size:int # this is the upscaled image size used for scanning
    survey_image_size:int # this is the initial survey image size
    # scan timing for ADF subscan - this is just for if only doing HAADF imaging when merlin is off
    scan_dwell_time_us: int = 15
    scan_flyback_time_us: int = 100
    # hardware options
    stage_method:str
    lenses_method:str
    imaging_method:str
    analysis_method: str | None = None # None means no per-scan analysis, otherwise runs after each scan
    # drift options
    drift : DriftSettings = DriftSettings()
    # focus options
    focus: FocusSettings = FocusSettings()
    # 4dstem options
    stem4d: STEM4DSettings | None = None # None means no 4D-STEM acquisition, otherwise will acquire with these settings
    # SI options
    stemsi: STEMSISettings | None = None # None means no SI acquisition, otherwise will acquire with these settings

class AnalysisRequest(BaseModel):
    folder_path: str
    box_indices: list[int]  # batch of one or more scan indices to analyse together

# Update microscope config
class ConfigUpdateRequest(BaseModel):
    preferences: dict
    stem4d_settings: dict | None = None

class CompUcentricCal(BaseModel):
    folder_path:str
    filename:str | None = None
    direction:str
    sign:str
    survey_image_size: int | None = None
    dwell_time_us:int = 15
    flyback_time_us:int = 500
    # hardware options
    stage_method:str
    lenses_method:str
    imaging_method:str
