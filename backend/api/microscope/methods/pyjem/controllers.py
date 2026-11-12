from pathlib import Path
import os
import numpy as np
import time 
from contextlib import contextmanager
import time
from microscope.core.interfaces import StageController, ImagingController, LensController
from microscope.methods.gatan.controllers import GatanImaging
from microscope.techniques.drift_corr import drift_calc
from microscope.techniques.focus_loop import _norm_var, _parabolic_fit, plot_coarse_range
from microscope.core.hardware_utils import requires_controller
from util import data_io 
from util.preprocess import bytescale
UNIT_TO_ANGSTROM = {
    "nm": 10.0,
    "um": 1e4, "\u00b5m": 1e4,
}

def corners_to_pyjem(x1,y1, x2,y2):
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    x_top_left = min(x1, x2)
    y_top_left = min(y1, y2)
    return (width, height, x_top_left, y_top_left)


class PyJEMStage(StageController):
    def __init__(self, tem3_stage):
        self._stage = tem3_stage

    @requires_controller("_stage")
    def get_position(self):
        """Looped as retrieval sometimes fails on first try"""
        current_pos = None
        try:
            current_pos = self._stage.GetPos()
            print(f"stage found! {current_pos}")
            # setup as dict
            current_pos = {
                "x": current_pos[0], 
                "y": current_pos[1], 
                "z": current_pos[2],
                'xt': current_pos[3],
                'yt': current_pos[4],
            }

        except Exception as e:
            print(e)
            pass
        # setup as dict
        return current_pos

    @requires_controller("_stage")
    def move_absolute(self, value, axis='x'):
        try:
            axis_funcs = {
                'x': self._stage.SetX,
                'y': self._stage.SetY,
                'z': self._stage.SetZ
            }
            axis_funcs[axis.lower()](value)
            print(f"{axis} moved to {value}!")
        except Exception as e:
            print(e)
            pass
    
    @requires_controller("_stage")
    def move_relative(self, magnitude, axis='x'):
        try:
            axis_funcs = {
                'x': self._stage.SetXRel,
                'y': self._stage.SetYRel,
                'z': self._stage.SetZRel
            }
            axis_funcs[axis.lower()](magnitude)
            print(f"{axis} shifted by {magnitude}!")
        except Exception as e:
            print(e)
            pass

    @requires_controller("_stage")
    def tilt_relative(self, degrees, axis='x'):
        try:
            func = self._stage.SetTYRel if axis == 'y' else self._stage.SetTXRel
            func(degrees)
            print(f"{axis} tilt shifted by {degrees}!")
        except Exception as e:
            print(e)
            pass

    @requires_controller("_stage")
    def tilt_absolute(self, degrees, axis='x'):
        try:
            func = self._stage.SetTiltYAngle if axis == 'y' else self._stage.SetTiltXAngle
            func(degrees)
            print(f"{axis} tilt shifted by {degrees}!")
        except Exception as e:
            print(e)
            pass


class PyJEMImaging(ImagingController):
    def __init__(self, detector):
        self._current_det = detector # This refers to the detector instance created by detector.Detector(), not the Detector3() controller

    def set_dwell_time(self, dwell_time_s):
        pass  # TODO add dwell time control

    def set_flyback_time(self, flyback_time_s):
        pass  # TODO add flyback time control

    @requires_controller("_current_det")
    def get_image(self, full_image_size, subscan_region=None, survey_image_size = None, verbose = False, restore_imaging_area=True, **kwargs):
        if subscan_region:
            return self._subscan(
                box_coords=subscan_region,
                full_image_size=full_image_size,
                survey_image_size=survey_image_size,
                restore_imaging_area=restore_imaging_area,
            )
        return self._full_image(Height=full_image_size[1], Width=full_image_size[0], subscanning = False,survey_image_size=survey_image_size)

    def _full_image(self, Height = None, Width = None, subscanning = True, survey_image_size=None):
        """
        Get image from buffer
        """
        if Height is None or Width is None:
            print("Height or Width not provided, retrieving from detector settings.")
            detectorData = self._current_det.get_detectorsetting()
            ImageSize= detectorData['OutputImageInformation']
            ImageSize = ImageSize['ImageSize']
            if Height is None:
                Height=ImageSize['Height']
            if Width is None:
                Width=ImageSize['Width']
        if not subscanning:
            self._current_det.set_scanmode(0)  # back to full scan

            self._current_det.set_imaging_area(Height, Width)
            
        print("image dim:", Height, Width)
        buffer = self._current_det.snapshot_rawdata()

        if not subscanning:
            restore_size = survey_image_size if survey_image_size is not None else (Width, Height)
            if restore_size is not None:
                self._current_det.set_imaging_area(restore_size[0], restore_size[1])
                time.sleep(1)

        # array = np.frombuffer(buffer, dtype = np.uint16)
        # array = np.frombuffer(array, dtype = '<i2')
        # array = array.reshape((Height,Width)).astype(np.int16)

        # FOR ACE!
        array = np.frombuffer(buffer, dtype = np.uint16)
        array = np.frombuffer(array, dtype = '<u2')
        array = array.reshape((Height,Width))

        # array = bytescale(array) # scaling to 0-255 error when from np.int16 to uint8
        return array

    def _subscan(
        self, box_coords, full_image_size, survey_image_size=None, restore_imaging_area=True
    ):
        """
        box_coords = (width, height, x, y), (x,y)= top left, relative to full_image_size
        full_image_size = (width, height) of the resolution that box_coords' x1,y1 are defined in (e.g. 4096x4096).
        survey_image_size = (width, height) to reset the imaging area to afterwards (e.g. survey resolution).
        """
        arr = None
        try:
            self._current_det.set_scanmode(3)
            self._current_det.set_imaging_area(full_image_size[0], full_image_size[1])
            width, height, x1,y1 = box_coords
            self._current_det.set_areamode_imagingarea(
                width,
                height,
                x1,
                y1
            )
            # time.sleep(2)
            arr = self._full_image(
                Height = height,
                Width = width
            )
            # get_image_path(
            #     mydet = mydet,
            #     savepath = f"image-{num}"
            # )
        except Exception as e:
            print("pyjem subscan failed:", e)
        finally:
            self._current_det.set_scanmode(0)  # back to full scan
            if restore_imaging_area:
                restore_size = survey_image_size if survey_image_size is not None else full_image_size
                if restore_size is not None:
                    self._current_det.set_imaging_area(restore_size[0], restore_size[1])
            # time.sleep(1)

        return arr    
    def drift_correct(self, lenses:LensController, survey_size, initial_survey_img, drift_subscan_coords=None,
                      max_shift_pixel=None, window_type='hanning', **kwargs):
        """
        lenses: LensController object to control beam blanking etc during drift correction
        survey_size: size of the survey image e.g. (512,512) needed to set scan size for drift correction scan. Assumed to be width,height
        initial_survey_img: initial survey image as reference
        drift_subscan_coords: (width, height, x1, y1) to define subscan region if used for drift correction, if None, uses full image at resolution of initial survey
        max_shift_pixel: maximum allowed shift in pixels to prevent outliers
        window_type: type of windowing to apply to images before phase correlation, options are 'hanning', 'sobel', 'median'
        """
        # This could be in the ABC ...?
        if drift_subscan_coords is None:
            x1, y1 = 0, 0
            width, height = survey_size[1], survey_size[0]
        else:
            width, height, x1, y1 = drift_subscan_coords

        if max_shift_pixel is None:
            # Max shift is half the full scan size if not specified, to prevent large outliers
            max_shift_pixel = min(width//2 , height//2)

        with lenses.beam_unblanked():
            scan_result = self.get_image(
                full_image_size = (survey_size[1], survey_size[0]),
                subscan_region = drift_subscan_coords
            )

        print("scan box:", width, height, x1, y1)
        shift_px, _ = drift_calc(
            initial_survey_img,
            scan_result,
            max_shift_pixel=max_shift_pixel,
            window_type=window_type,
        )
        return shift_px, scan_result


class PyJEMLenses(LensController):
    """Wraps the existing Def3/Detector3 beam/detector functions."""
    def __init__(self, def3_controller, det3_controller, eos3_controller, lens3_controller, detector_name: str, detector_mapping: dict, imaging_detector=None):
        if detector_name not in detector_mapping:
            raise ValueError(f"Detector '{detector_name}' is not in the instrument's pyjem detector_mapping {list(detector_mapping)}")
        self._imaging_detector = imaging_detector # detector.Detector of the PyJEM method, used for pixel size when imaging with the QD ScanEngine
        self._detector_id = detector_mapping[detector_name] # PyJEM id of the instrument's imaging detector needed for insertion/removal
        self._def3 = def3_controller # Deflectors via the Def3()
        self._det3 = det3_controller # Detector3(), not the actual detector, which is accessed via self._det3.Detector()
        self._eos3 = eos3_controller # EOS3()
        self._lens3 = lens3_controller # Lens3()

    @requires_controller("_def3", unavailable_return=False)
    def beam_blank(self, blank=True, delay=1.5):
        """
        Toggle beam blanking and wait a delay to ensure blanking is applied
        """
        try:
            self._def3.SetBeamBlank(int(blank))
            time.sleep(delay)
            print(f"Beam {'blanked' if blank else 'unblanked'}")
            return True
        except Exception as e:
            print(f"Beam blanking failed: {e}")
            return False

    @contextmanager
    def beam_unblanked(self, delay=1.5):
        self.beam_blank(blank=False, delay=delay)
        try:
            yield
        finally:
            self.beam_blank(blank=True, delay=delay)


    @requires_controller("_det3", unavailable_return=False)
    def set_detector_position(self, inserted: bool = False, delay: float = 4.0):
        """
        Insert or remove the instrument's imaging detector
        inserted:
            False = Remove
            True = Insert
        """
        self._det3.SetPosition(int(self._detector_id), int(inserted))
        if delay > 0:
            time.sleep(delay) # wait for the change to stabilise
        return True
        
    @contextmanager
    def detector_inserted(self, delay: float = 4.0):
        self.set_detector_position(True, delay=delay)
        try:
            yield
        finally:
            self.set_detector_position(False, delay=delay)  

    @contextmanager
    def detector_removed(self, delay: float = 4.0):
        self.set_detector_position(False, delay=delay)
        try:
            yield
        finally:
            self.set_detector_position(True, delay=delay)

    @requires_controller("_lens3")
    def get_defocus(self):
        """Return the current OLf value, or None if lens control unavailable."""
        try:
            return self._lens3.GetOLf()
        except Exception as e:
            print(f"get_defocus failed: {e}")
            return None

    @requires_controller("_lens3")
    def set_defocus(self, olf_value):
        """Set the OLf value. Does nothing if lens control unavailable."""
        if olf_value is None:
            return
        try:
            self._lens3.SetOLf(int(olf_value))
            print(f"Defocus set to OLf={olf_value}")
        except Exception as e:
            print(f"set_defocus failed: {e}")

    @requires_controller("_eos3")
    def get_magnification(self):
        """Return the current absolute magnification value, or None if unavailable."""
        try:
            return int(self._eos3.GetMagValue()[0])
        except Exception as e:
            print(f"get_magnification failed: {e}")
            return None

    @requires_controller("_eos3", unavailable_return=False)
    def set_magnification(self, target_mag, max_steps=20):
        """Go to target mag by stepping through up/down until matches or max steps. Returns True only if target_mag was reached"""
        if target_mag is None:
            print("No target mag defined. Skipping set mag.")
            return False
        print('attempting to reach mag:', target_mag)
        current_mag = self.get_magnification()
        # loop through mags
        steps = 0
        while current_mag is not None and current_mag != target_mag and steps < max_steps:
            was_below = current_mag < target_mag
            try:
                self._eos3.UpSelector() if was_below else self._eos3.DownSelector()
                current_mag = self.get_magnification()
                time.sleep(0.1)
            except Exception as e:
                print(f"Failed while stepping magnification: {e}. Aborting.")
                return False
            steps += 1
            # moved past the desired mag so must not be a valid increment
            if current_mag is not None and current_mag != target_mag and (current_mag < target_mag) != was_below:
                print(f"Target magnification {target_mag} is not a valid step (passed it, now at {current_mag}).")
                return False
        if current_mag != target_mag:
            print(f"Could not reach target magnification {target_mag} after {steps} steps (ended at {current_mag}).")
            return False
        print(f"Magnification set to {target_mag} in {steps} steps.")
        return True

    @requires_controller("_eos3", unavailable_return=False)
    def increment_magnification(self, steps:int):
        """Adjust magnification by relative selector steps"""
        try:
            selector = self._eos3.UpSelector if steps > 0 else self._eos3.DownSelector
            for _ in range(abs(steps)):
                selector()
                time.sleep(0.1) # short delay 
            return True
        except Exception as e:
            print(f"Magnification adjustment failed: {e}")
            return False

    def get_px_res(self, pyjem_imaging, savefolder=None, savefile=None, **kwargs):
        """
        Given detector, will retrieve the magnification and output the resolution if pyjem imaging
        Else get via dm4 for gatan else get directly from detector if qd_scanengine
        Returns in Angstroms
        """
        if isinstance(pyjem_imaging, GatanImaging):
            if savefolder is None or savefile is None:
                print("Gatan pixel resolution requires a saved image (savefolder/savefile). Skipping.")
                return None
            from rsciio import digitalmicrograph as dm
            try:
                dm_dataset = dm.file_reader(f"{savefolder}/{savefile}.dm4")[0]
                dm_image_cal = dm_dataset['original_metadata']['ImageList']['TagGroup0']['ImageData']['Calibrations']['Dimension']['TagGroup0']
                scale = float(dm_image_cal['Scale'])
                units = str(dm_image_cal['Units'])
                print(scale, units)
            except Exception as e:
                print(f"Failed to read Gatan pixel calibration from {savefolder}/{savefile}: {e}")
                return None
            unit_factor = UNIT_TO_ANGSTROM.get(units)
            if unit_factor is None:
                print(f"Unrecognised Gatan pixel calibration units '{units}'. Skipping.")
                return None
            return scale * unit_factor

        magnification = self._eos3.GetMagValue()[0]
        # QD ScanEngine has no detector object so use the PyJEM method's detector
        current_det = getattr(pyjem_imaging, "_current_det", None) or self._imaging_detector
        if current_det is None:
            print("No PyJEM detector available for pixel resolution lookup. Skipping.")
            return None
        detectorData = current_det.get_detectorsetting()
        ppmh = detectorData['OutputImageInformation']['PixelsPerMeter']['Horizontal']
        pixel_size = 1 / (ppmh * magnification)
        pixel_size *= 10**(10) # convert m to angstroms
        return pixel_size
    
    def autofocus(self, imaging: ImagingController, method = "pyjem", focus_region = 'full', full_image_size = None, survey_image_size = None, subscan_region = None,  **kwargs):
        # autofocus
        print("running autofocus: ", method)
        if method == "pyjem" and isinstance(imaging, PyJEMImaging):
            if focus_region == 'box' and subscan_region is not None:
                print("Running PyJEM autofocus on subscan region...")
                try:
                    imaging._current_det.set_scanmode(3)
                    width, height, x1,y1 = subscan_region
                    imaging._current_det.set_areamode_imagingarea(
                        width,
                        height,
                        x1,
                        y1
                    )
                    imaging._current_det.AutoFocus() # inbuilt PyJEM autofocus on subscan region
                except Exception as e:
                    print("Failed to do autofocus: ", e)
                finally:
                    imaging._current_det.set_scanmode(0)  # back to full scan
            else:
                print("Running PyJEM autofocus on full image...")
                imaging._current_det.AutoFocus() # inbuilt PyJEM autofocus on full image
            time.sleep(1)
            return None

        elif self._lens3 is not None:
            # Run custom method here
            self._focus_loop(imaging, subscan_region=subscan_region, full_image_size=full_image_size, survey_image_size=survey_image_size, **kwargs)
        else:
            print("No autofocus method available. Skipping.")
            
    
    def _focus_loop(self, imaging: ImagingController,
        subscan_region: tuple[int, int, int, int], # (width, height, x1, y1) for subscan region to use in autofocus loop, if None uses full image
        full_image_size:tuple[int, int], 
        survey_image_size:tuple[int, int] = None,
        # coarse_step,
        fine_step = int('0010'),
        limit_val = int('0300'), # this is the limit that should be for ptych and is 100 nm '0083'
        save_path = "",
        region_loop_num = 0,
        final_offset = 30, #offset by 30 nm for ptycho at end
    ):
        """
        Custom autofcous method that does imaging etc.
        0.75 nm per bit so 131 is 100 nm for e02 @ 300 kV
        """
        def _scan_and_measure(acquisition_counter):
            """
            Helper for measuring and getting variance
            """
            with self.beam_unblanked():
                scan_result = imaging.get_image(
                    full_image_size = full_image_size,
                    survey_image_size=survey_image_size,
                    subscan_region=subscan_region, 
                    restore_imaging_area=False,
                    savefolder = Path(full_save_path).resolve().as_posix(), 
                    savefile = f"focus-{str(acquisition_counter)}"
                )
                
            data_io.local_store(full_save_path, f"focus-{str(acquisition_counter)}", bytescale(scan_result), data_type='png')
            scan_result = scan_result.astype(np.float64)
            var_measure = _norm_var(scan_result)
            return var_measure, scan_result


        full_save_path = os.path.join(save_path, f"focus-{region_loop_num}")
        Path(full_save_path).mkdir(parents=True, exist_ok=True)
        acquisition_counter = 0
        coarse_step = max(fine_step * 2, int(limit_val / 4))
        fine_window = coarse_step * 2

        all_ds = []
        all_vs = []

        # starting conditions
        starting_OLf = self._lens3.GetOLf()
        start_var, start_img = _scan_and_measure(acquisition_counter)
        acquisition_counter += 1

        # --- 1. Coarse Scan ---
        coarse_range = range(-limit_val, limit_val + 1, coarse_step)
        coarse_vs = []
        coarse_ds = []

        for offset in coarse_range:
            current_Olf = int(starting_OLf + offset)
            if current_Olf == starting_OLf:
                norm_var = start_var
            else:
                self._lens3.SetOLf(int(current_Olf))
                norm_var, _ = _scan_and_measure(acquisition_counter)
                acquisition_counter += 1

            coarse_ds.append(current_Olf)
            coarse_vs.append(norm_var)
            all_ds.append(current_Olf)  
            all_vs.append(norm_var)       
            print(f"Coarse OLf: {current_Olf:04X}, Var: {norm_var:.5f}")

        best_coarse_idx = np.argmax(coarse_vs)
        best_coarse_OLf = coarse_ds[best_coarse_idx]
        print(f"Best coarse OLf: {best_coarse_OLf:04X}")


        # --- 2. Fine Scan ---
        if fine_step * 5 > fine_window:
            fine_window = fine_step * 6
        fine_range = range(-fine_window // 2, fine_window // 2 + 1, fine_step)

        fine_vs = []
        fine_ds = []

        for offset in fine_range:
            current_Olf = int(best_coarse_OLf + offset)
            if current_Olf in all_ds:
                norm_var = all_vs[all_ds.index(current_Olf)]
            else:
                self._lens3.SetOLf(int(current_Olf))
                norm_var, _ = _scan_and_measure(acquisition_counter)
                acquisition_counter += 1

            fine_ds.append(current_Olf)
            fine_vs.append(norm_var)
            print(f"Fine OLf: {current_Olf:04X}, Var: {norm_var:.5f}")

        if not fine_vs:
            print("Fine scan failed.")
            self._lens3.SetOLf(starting_OLf)
            return

        # --- 3. Parabolic Refinement ---
        sorted_indices = np.argsort(fine_vs)[-5:]
        top_x = np.array(fine_ds)[sorted_indices]
        top_y = np.array(fine_vs)[sorted_indices]
        ideal_OLf_float, ideal_var = _parabolic_fit(top_x, top_y)
        ideal_OLf = int(ideal_OLf_float)

        # --- 4. Validation & Rollback ---
        best_discrete_idx = np.argmax(fine_vs)
        discrete_best_OLf = fine_ds[best_discrete_idx]
        discrete_best_var = fine_vs[best_discrete_idx]

        if abs(ideal_OLf - discrete_best_OLf) > fine_window:
            ideal_OLf = discrete_best_OLf
            ideal_var = discrete_best_var

        output_fig = plot_coarse_range(
            coarse_ds, coarse_vs, fine_ds, fine_vs,
            (ideal_OLf, ideal_var),
        )

        if ideal_var < start_var * 1.01:
            print(f"Improvement negligible. Rolling back to {starting_OLf:04X}")
            ideal_OLf = starting_OLf
            output_fig.suptitle(f"ROLLBACK to: {ideal_OLf:04X}", fontweight='bold')
        else:
            print(f"Confirmed. Moving to {ideal_OLf:04X}")
            output_fig.suptitle(f"New lens: {ideal_OLf:04X}", fontweight='bold')

        output_fig.savefig(
            os.path.join(full_save_path, f"overall-focus-{region_loop_num}.png"),
            dpi=300, bbox_inches='tight',
        )

        self._lens3.SetOLf(int(ideal_OLf))

        # final_offset_bits = int(final_offset/0.75) # 0.75nm per bit
        # self._lens3.SetOLf(int(ideal_OLf + final_offset_bits))
        # print(f"Applied final offset of {final_offset} nm, for final defocus of {ideal_OLf + final_offset_bits:04X}")
        # _, _ = _scan_and_measure(acquisition_counter) # final used scan
