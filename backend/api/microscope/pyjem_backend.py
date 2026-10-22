from pathlib import Path
import os
import numpy as np
import time 
from contextlib import contextmanager

from microscope.controller import StageController, ImagingController, LensController
from microscope.drift_corr import drift_calc
from microscope.focus_loop import _norm_var, _parabolic_fit, plot_coarse_range
from util import data_io 
from util.preprocess import bytescale
DETECTOR_MAPPING = {
    "HAADF" : 10, # THIS NEEDS TO BE TAKE FROM THE CONFIG OR HAVE PRESETS PER MICROSCOPE! HAADF for GrandARM
    "ADF1" : 10 # THIS NEEDS TO BE TAKE FROM THE CONFIG OR HAVE PRESETS PER MICROSCOPE! HAADF for GrandARM

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

    def move_absolute(self, value, axis='x'):
        try:
            func = self._stage.SetY if axis == 'y' else self._stage.SetX
            func(value)
            print(f"{axis} moved to {value}!")
        except Exception as e:
            print(e)
            pass
    
    def move_relative(self, magnitude, axis='x'):
        try:
            func = self._stage.SetYRel if axis == 'y' else self._stage.SetXRel
            func(magnitude)
            print(f"{axis} shifted by {magnitude}!")
        except Exception as e:
            print(e)
            pass

    def tilt_relative(self, degrees, axis='x'):
        try:
            func = self._stage.SetTYRel if axis == 'y' else self._stage.SetTXRel
            func(degrees)
            print(f"{axis} tilt shifted by {degrees}!")
        except Exception as e:
            print(e)
            pass


class PyJEMImaging(ImagingController):
    def __init__(self, detector):
        self._current_det = detector # This refers to the detector instance created by detector.Detector(), not the Detector3() controller

    def set_dwell_time(self, dwell_time_s):
        pass  # PyJEM doesn't have explicit dwell control

    def set_flyback_time(self, flyback_time_s):
        pass

    def get_image(self, full_image_size, subscan_region=None, verbose = False, **kwargs):
        if subscan_region:
            return self._subscan(box_coords=subscan_region)
        return self._full_image(Height=full_image_size[1], Width=full_image_size[0])

    def _full_image(self, Height = None, Width = None):
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

        print("imaging!")
        print("image dim:", Height, Width)
        buffer = self._current_det.snapshot_rawdata()
        array = np.frombuffer(buffer, dtype = np.uint16)
        array = np.frombuffer(array, dtype = '<i2')
        array = array.reshape((Height,Width)).astype(np.int16)
        # array = bytescale(array) # scaling to 0-255 error when from np.int16 to uint8
        return array

    def _subscan(
        self, box_coords
    ):
        """
        box_coords = (width, height, x, y), (x,y)= top left
        """
        self._current_det.set_scanmode(3)
        width, height, x1,y1 = box_coords
        self._current_det.set_areamode_imagingarea(
            width,
            height,
            x1,
            y1
        )
        arr = self._full_image(
            Height = height,
            Width = width
        )
        # get_image_path(
        #     mydet = mydet,
        #     savepath = f"image-{num}"
        # )
        self._current_det.set_scanmode(0)  # back to full scan
        time.sleep(1)

        return arr
    
    def drift_correct(self, lenses:LensController, survey_size, initial_survey_img, drift_subscan_coords=None,
                      max_shift_pixel=None, window_type='hanning', **kwargs):
        """
        This could be in the ABC ...
        lenses: LensController object to control beam blanking etc during drift correction
        survey_size: size of the survey image e.g. (512,512) needed to set scan size for drift correction scan. Assumed to be width,height
        initial_survey_img: initial survey image as reference
        drift_subscan_coords: (width, height, x1, y1) to define subscan region if used for drift correction, if None, uses full image at resolution of initial survey
        max_shift_pixel: maximum allowed shift in pixels to prevent outliers
        window_type: type of windowing to apply to images before phase correlation, options are 'hanning', 'sobel', 'median'
        """
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
    def __init__(self, def3_controller, det3_controller, eos3_controller, lens3_controller):
        self._def3 = def3_controller # Deflectors via the Def3()
        self._det3 = det3_controller # Detector3(), not the actual detector, which is accessed via self._det3.Detector()
        self._eos3 = eos3_controller # EOS3()
        self._lens3 = lens3_controller # Lens3()

    def beam_blank(self, blank=True, delay=1.5):
        """
        Toggle beam blanking and wait a delay to ensure blanking is applied
        """
        if self._def3 is None:
            print("Beam blanking controller not available. Skipping.")
            return False
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


    def set_detector_position(self, detector_name:str = "ADF1", inserted = False, delay = 4.0):
        """
        detector:
            10 = ADF1 or 10 = HAADF on ACE
        change:
            False = Remove
            True = Insert
        """
        # return True
        detector_int = DETECTOR_MAPPING[detector_name]

        if self._det3 is not None:
            self._det3.SetPosition(int(detector_int), int(inserted))
            if delay > 0:
                time.sleep(delay) # wait for the change to stabilise
            return True
        else:
            print("Detector position controller not available. Skipping.")
            return False
        
    @contextmanager
    def detector_inserted(self, detector_name="ADF1", delay=4.0):
        self.set_detector_position(detector_name, True, delay=delay)
        try:
            yield
        finally:
            self.set_detector_position(detector_name, False, delay=delay)  

    @contextmanager
    def detector_removed(self, detector_name="ADF1", delay=4.0):
        self.set_detector_position(detector_name, False, delay=delay)
        try:
            yield
        finally:
            self.set_detector_position(detector_name, True, delay=delay)

    def get_defocus(self):
        """Return the current OLf value, or None if lens control unavailable."""
        if self._lens3 is None:
            return None
        try:
            return self._lens3.GetOLf()
        except Exception as e:
            print(f"get_defocus failed: {e}")
            return None

    def set_defocus(self, olf_value):
        """Set the OLf value. Does nothing if lens control unavailable."""
        if self._lens3 is None or olf_value is None:
            return
        try:
            self._lens3.SetOLf(int(olf_value))
            print(f"Defocus set to OLf={olf_value}")
        except Exception as e:
            print(f"set_defocus failed: {e}")

    def get_px_res(self, pyjem_imaging: PyJEMImaging):
        """
        Given detector, will retrieve the magnification and output the resolution
        Returns in Angstroms
        """
        magnification = self._eos3.GetMagValue()[0]
        #Get the pixels per meter value
        detectorData = pyjem_imaging._current_det.get_detectorsetting()
        ppmh = detectorData['OutputImageInformation']['PixelsPerMeter']['Horizontal']
        pixel_size = 1 / (ppmh * magnification)
        pixel_size *= 10**(10) # convert m to angstroms
        return pixel_size
    
    def autofocus(self, imaging: ImagingController, method = "pyjem", focus_region = 'full', full_image_size = None, survey_image_size = None, subscan_region = None,  **kwargs):
        # autofocus
        if method == "pyjem" and isinstance(imaging, PyJEMImaging):
            if focus_region == 'box' and subscan_region is not None:
                print("Running PyJEM autofocus on subscan region...")
                imaging._current_det.set_scanmode(3)
                width, height, x1,y1 = subscan_region
                imaging._current_det.set_areamode_imagingarea(
                    width,
                    height,
                    x1,
                    y1
                )
                imaging._current_det.AutoFocus() # inbuilt PyJEM autofocus on subscan region
                imaging._current_det.set_scanmode(0)  # back to full scan
            else:
                print("Running PyJEM autofocus on full image...")
                imaging._current_det.AutoFocus() # inbuilt PyJEM autofocus on full image
            time.sleep(1)

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

        final_offset_bits = int(final_offset/0.75) # 0.75nm per bit
        self._lens3.SetOLf(int(ideal_OLf + final_offset_bits))
        print(f"Applied final offset of {final_offset} nm, for final defocus of {ideal_OLf + final_offset_bits:04X}")
        _, _ = _scan_and_measure(acquisition_counter) # final used scan
