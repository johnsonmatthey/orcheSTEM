import threading
import queue
import time
import numpy as np
from rsciio import digitalmicrograph as dm
from scipy.ndimage import binary_dilation

from microscope.controller import ImagingController, STEMSpectroscopy
from microscope.drift_corr import drift_calc

_command_queue = queue.Queue()  # Queue commands without blocking and this is what gms will poll form
_result_store = {} # stores any results posted back from gms for submit_command to retrieve and return it
_result_events = {} #stores threading events for each command id so submit_command can block until the result is posted back by gms
_lock = threading.Lock()
_cmd_counter = 0
_last_poll_time = None  # timestamp of last GMS poll

def _next_id():
    global _cmd_counter
    with _lock:
        _cmd_counter += 1
        return _cmd_counter


def submit_command(command: str, params: dict = None, timeout: float = 120.0) -> dict:
    """
    Queues a command for DM and blocks until the result arrives via threading events
    """
    cmd_id = _next_id()
    event = threading.Event()
    _result_events[cmd_id] = event
    _command_queue.put(
        {
            "id": cmd_id,
            "command": command,
            "params" : params if params else {}
        }
    )
    print(f"Submitted command {command} with params {params} and id {cmd_id}")

    if not event.wait(timeout=timeout):
        _result_events.pop(cmd_id, None)
        _result_store.pop(cmd_id, None)  # clean up in case GMS posted between timeout and here
        return {"ok": False, "id": cmd_id, "error": "timeout"}

    result = _result_store.pop(cmd_id, None)
    _result_events.pop(cmd_id, None)
    return {"ok": True, "id": cmd_id, "result": result}


def poll_next() -> dict:
    """Called by get /gms/poll"""
    global _last_poll_time
    _last_poll_time = time.monotonic()
    try:
        item = _command_queue.get_nowait()
        return {"ok": True, "id": item["id"], "command": item["command"], "params": item.get("params", {})}
    except queue.Empty:
        return {"ok": True, "id": None, "command": None, "params": None}

def post_result(cmd_id: int, result) -> dict:
    """Called by POST /gms/result — wakes up the waiting submit_command."""
    _result_store[cmd_id] = result
    event = _result_events.get(cmd_id)
    if event:
        event.set()  # threading.Event.set() — wakes the blocking .wait() in submit_command
    return {"ok": True}

def gms_is_connected(timeout_s: float = 6000.0) -> bool:
    """True if GMS has polled within the last timeout_s seconds."""
    if _last_poll_time is None:
        print("Checking GMS connection. No poll received yet.")
        return False
    elapsed = time.monotonic() - _last_poll_time
    print(f"Checking GMS connection. Last poll was {elapsed:.2f} seconds ago.")
    return elapsed < timeout_s

def gatan_box_coord(box_coords, rescaled_to_1=False, full_image_size=(512, 512)):
    """
    Convert box coordinates from frontend format (width, height, x0, y0) to Gatan format (t,l,b,r) 
    Either based on full image size or relative if rescaled_to_1 is True
    """
    width, height, x0, y0 = box_coords
    x0=int(x0)
    y0=int(y0)
    width=int(width)
    height=int(height)

    x1 = x0 + width
    y1 = y0 + height
    if rescaled_to_1:
        x0 = x0 / full_image_size[0]
        y0 = y0 / full_image_size[1]
        x1 = x1 / full_image_size[0]
        y1 = y1 / full_image_size[1]
    return [y0, x0, y1, x1] # t,l,b,r for Gatan format

def serpentine_ordering(point_arr):
    """
    Reorders a 2D array of coordinates in a serpentine pattern. Assumes point_arr is of form [[x1, y1], [x2, y2], ...].
    """
    ordered_coords = []
    current_y = point_arr[0][1]  # Start with first y-coordinate
    current_row = []
    reverse = False  # Track whether to reverse the current row

    # Iterate through coordinates
    for coord in point_arr:
        x, y = coord
        
        if y != current_y:
            # When y changes, add current row (reversed if needed) and start new row
            if reverse:
                current_row.reverse()
            ordered_coords.extend(current_row)
            current_row = []
            current_y = y
            reverse = not reverse  # Toggle reverse flag for next row

        current_row.append(coord)

    # add the last row
    if reverse:
        current_row.reverse()
    ordered_coords.extend(current_row)

    return np.array(ordered_coords)

def customscan_list(custom_mask, save_path, pad_mask=True):
        if pad_mask:
            custom_mask = binary_dilation(custom_mask, structure=np.ones((3,3)))

        # bbox_region = mask[padded_top:padded_bottom, padded_left:padded_right]
        bbox_region_particle_coords = np.argwhere(custom_mask == 1).astype(int) #NOTE THIS IS NOW TRANSPOSED!!!!
        # [Y1,X1], [Y2,X2] etc
        # Must sort based on first column
        bbox_region_particle_coords = np.array(sorted(bbox_region_particle_coords, key=lambda x: (x[0], x[1])))
        #bbox_region_particle_coords[:,[1,0]] = bbox_region_particle_coords[:,[0,1]]
        
        #img = DM.CreateImage(bbox_region.astype(int))
        #img.ShowImage()
        
        bbox_coords_ordered = serpentine_ordering(bbox_region_particle_coords)
        #reverse ordering as first element added will be last element in taglist
        bbox_coords_ordered = bbox_coords_ordered[::-1] 
        np.save(save_path, bbox_coords_ordered) 

        # for y_coord, x_coord in bbox_coords_ordered:
        #     # NOTE swapped as inverted axis in GMS compared to here
        #     #Place the data point before the 0 index. This will fill it up backwards
        #     tg_scan.InsertTagAsShortPoint(0, x_coord, y_coord) #Place the data point before the 0 index.
            
        # #Save taglist to file
        # # fullpath = filepath_scan + outfilename_scan + str(counter_found)
        # # print(fullpath)
        # tg_scan.SaveToFile(save_path)

class GatanImaging(ImagingController):
    """
    Imaging controller that sends commands to DigitalMicrograph (GMS) via the
    poll/result command queue.  GMS scans and outputs .dm4 which is returned as array.

    Three GMS commands:
        EM_survey     — full survey scan
        EM_subsurvey  — subscan of a box region
        EM_SI         — spectrum imaging (spectroscopy) acquisition
    """
    def __init__(self):
        # Some defaulrs
        self._dwell_time_s = 50e-6
        self._flyback_time_s = 1000e-6

    def set_dwell_time(self, dwell_time_s):
        self._dwell_time_s = dwell_time_s

    def set_flyback_time(self, flyback_time_s):
        self._flyback_time_s = flyback_time_s

    @staticmethod
    def _read_dm4(savefolder, savefile):
        """Read a .dm4 file saved by GMS and return as numpy array."""
        filepath = f"{savefolder}/{savefile}.dm4"
        return dm.file_reader(filepath)[0]['data']

    # Main methods as seen in other imaging controllers
    def get_image(self, full_image_size, subscan_region=None,
                  savefolder=None, savefile="scan", close_image=False, survey_image_size=None):
        """
        Acquire a survey or subscan image via GMS. NOTE there are extra args as we save the dm4.
        Could change to directly send the array but this keeps the metadata
        Args:
            full_image_size: (width, height) in pixels for the full survey area
            subscan_region: (width, height, x0, y0) defining a sub-region. Coords are in full_image_size space.
            savefolder: folder path for GMS to save the .dm4 file - MUST be absolute path with / slashes to work in DM 
            savefile: filename without extension
            close_image: whether GMS should close the image window after saving
            survey_image_size: (width, height) actual scan resolution. If provided, subscan_region is rescaled from full to survey res.
        Returns:
            np.ndarray of the acquired image
        """
        # Rescale coords from full res to survey res if survey_image_size is provided
        if survey_image_size is not None and subscan_region is not None:
            scale = survey_image_size[0] / full_image_size[0]
            w, h, x0, y0 = subscan_region
            # Rescale all coords from full res to survey res
            subscan_region = (int(round(w * scale)), int(round(h * scale)), int(round(x0 * scale)), int(round(y0 * scale)))
            full_image_size = survey_image_size
        elif survey_image_size is not None:
            full_image_size = survey_image_size

        if subscan_region is not None:
            return self._subscan(full_image_size, subscan_region, savefolder, savefile, close_image)
        return self._full_survey(full_image_size, savefolder, savefile)

    def _full_survey(self, full_image_size, savefolder, savefile):
        """Send EM_survey command to GMS for a full image scan."""
        width, height = full_image_size
        params = {
            "savefolder": savefolder,
            "savefile": savefile,
            "dwell_time": self._dwell_time_s,
            "flyback_time": self._flyback_time_s,
            "size": [width, height],
        }
        print(f"Performing GMS full survey scan of {full_image_size}")
        result = submit_command("EM_survey", params, timeout=600.0)
        if not result.get("ok"):
            raise RuntimeError(f"GMS EM_survey failed: {result.get('error', 'unknown')}")
        return self._read_dm4(savefolder, savefile)

    def _subscan(self, full_image_size, subscan_region, savefolder, savefile, close_image):
        """Send EM_subsurvey command to GMS for a subscan."""
        width, height, x0, y0 = subscan_region
        gatan_coords = gatan_box_coord(subscan_region)
        params = {
            "savefolder": savefolder,
            "savefile": savefile,
            "dwell_time": self._dwell_time_s,
            "flyback_time": self._flyback_time_s,
            "box_coords": gatan_coords,
            "box_width": width,
            "box_height": height,
            "close_image": close_image,
        }
        print(f"Performing GMS sub-survey scan on region: {subscan_region} (width, height, x, y)")
        result = submit_command("EM_subsurvey", params, timeout=600.0)
        if not result.get("ok"):
            raise RuntimeError(f"GMS EM_subsurvey failed: {result.get('error', 'unknown')}")
        return self._read_dm4(savefolder, savefile)

    def drift_correct(self, lenses, survey_size, initial_survey_img,
                      drift_subscan_coords=None, max_shift_pixel=None, window_type='hanning',
                      savefolder=None, savefile="drift_scan"):
        """
        returns (shift_x, shift_y), drift_corrected_image
        NOTE the shift returned is the direction the object has moved. 
        *1 to follow the object, *-1 to counteract the drift

        Args:
            lenses: LensesController object to control beam blanking etc during drift correction
            survey_size: size of the survey image e.g. (512,512) needed to set scan size for drift correction scan. Assumed to be width,height
            initial_survey_img: initial survey image as reference for comparison
            drift_subscan_coords: (width, height, x1, y1) to define subscan region if used for drift correction, if None, uses full image at resolution of initial survey
            max_shift_pixel: maximum allowed shift in pixels to prevent outliers
            window_type: type of windowing to apply to images before phase correlation, options are 'hanning', 'sobel', 'median'
            savefolder: folder path for GMS to save the drift scan .dm4
            savefile: filename without extension
        """
        if drift_subscan_coords is not None:
            width, height, x1, y1 = drift_subscan_coords
        else:
            width, height, x1, y1 = survey_size[1], survey_size[0], 0, 0

        if max_shift_pixel is None:
            max_shift_pixel = min(width // 2, height // 2)

        with lenses.beam_unblanked():
            scan_result = self.get_image(
                full_image_size=(survey_size[1], survey_size[0]),
                subscan_region=drift_subscan_coords,
                savefolder=savefolder,
                savefile=savefile,
            )

        print("scan box:", width, height, x1, y1)
        shift_px, _ = drift_calc(
            initial_survey_img,
            scan_result,
            max_shift_pixel=max_shift_pixel,
            window_type=window_type,
        )

        return shift_px, scan_result

class GatanSpectroscopy(STEMSpectroscopy):
    """
    STEM Spectrum Imaging via DigitalMicrograph (GMS).
    Sends EM_SI commands through the poll/result command queue.
    """

    def __init__(self, imaging: GatanImaging):
        self._imaging = imaging

    def acquire(
        self,
        subscan_region,
        savefolder,
        savefile,
        survey_size=512,
        acquire_eds=True,
        acquire_eels=True,
        drift_region = [0.1, 0.1, 0.9, 0.9],
        subscan_size=8,
        passes=1,
        custom_scan_mask = None,
        **kwargs,
    ) -> str:
        """
        Send EM_SI (spectrum imaging) command to GMS.

        Args:
            full_image_size: (width, height) of the full scan area
            subscan_region: (width, height, x0, y0) defining the SI region
            savefolder: folder path for GMS to save the output
            savefile: filename without extension
            survey_size: survey image size (used for FOV normalisation to 0-1)
            acquire_eds: whether to acquire EDS
            acquire_eels: whether to acquire EELS
            subscan_size: size multiplier for the subscan
            passes: number of SI passes
        Returns:
            savefile identifier
        """
        width, height, x0, y0 = subscan_region
        gatan_coords = gatan_box_coord(
            subscan_region, rescaled_to_1=True, full_image_size=(survey_size, survey_size)
        )
        if custom_scan_mask is not None:
            customscan_list(
                custom_scan_mask, save_path=f"{savefolder}/{savefile}_customscan.npy"
            )

        if drift_region is not None:
            gatan_drift_coords = gatan_box_coord(
                drift_region, rescaled_to_1=True, full_image_size=(survey_size, survey_size)
            )
        else:
            gatan_drift_coords = [0.1, 0.1, 0.9, 0.9]
        params = {
            "savefolder": savefolder,
            "savefile": savefile,
            "dwell_time": self._imaging._dwell_time_s,
            "FOV": gatan_coords,  # t,l,b,r between 0 and 1
            "survey_size": survey_size,
            "size": [width, height],
            "acquire_eds": acquire_eds,
            "acquire_eels": acquire_eels,
            "acquire_customscan": custom_scan_mask is not None,
            "drift_region": gatan_drift_coords,
            "num_passes": passes,
            "subscan_size": subscan_size,

            # "subscan_size": subscan_size,
            # "passes": passes,
        }
        print(f"Performing GMS spectrum imaging on region: {subscan_region}")
        result = submit_command("EM_SI", params, timeout=600.0)
        if not result.get("ok"):
            raise RuntimeError(f"GMS EM_SI failed: {result.get('error', 'unknown')}")
        return savefile