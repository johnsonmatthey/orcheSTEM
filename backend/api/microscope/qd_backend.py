import numpy as np
import h5py
from datetime import datetime
from microscope.drift_corr import drift_calc
try:
    from pyscanengine.data import FrameMonitor
except Exception as e:
    print(f"FrameMonitor import failed: {e}. Running in mock mode.")
import time

from microscope.controller import ImagingController, STEM4DDetector
from microscope.merlin_commands import merlin_setup

class QDImaging(ImagingController):
    def __init__(self, scan_engine, enabled_inputs=(3,)):
        self._engine = scan_engine
        self._enabled_inputs = list(enabled_inputs)

    def set_flyback_time(
        self, 
        flyback_time_s = 100e-6
    ):
        """
        Set flyback time for QD ScanEngine
        NOTE the actual flyback time may differ slightly due to hardware constraints
        NOTE the flyback when turning corners is sinusoidal so can be longer/shorter than set here
        Args:
            scan_engine: QD ScanEngine object
            flyback_time_s: Flyback time in seconds
        """
        if self._engine is not None:
            self._engine.set_flyback_time(flyback_time_s)
            print(f"Set flyback time to: {flyback_time_s/1e-6} microseconds, Real flyback time: {self._engine.get_flyback_time()/1e-6} microseconds")
        else:
            print("Scan engine not initialized. Cannot set flyback time.")

    def set_dwell_time(
        self, 
        dwell_time_s = 15e-6
    ):
        """Set dwell time for QD ScanEngine

        Args:
            scan_engine: QD ScanEngine object
            dwell_time_s: Dwell time in seconds
        """
        if self._engine is not None:
            self._engine.pixel_time = dwell_time_s
            print(f"Set dwell time to : {dwell_time_s/1e-6} microseconds")
        else:
            print("Scan engine not initialized. Cannot set dwell time.")

    def get_image(
        self,
        full_image_size=(4096, 4096),
        subscan_region=None,
        arbitrary_scan = False,
        # rescale_uint8 = False,
        enabled_inputs = None,
        # return_arr = True,
        **kwargs,
    ):
        """
        Get image from QD ScanEngine

        Args:
            scan_engine: QD ScanEngine object
            full_image_size: Tuple of (width, height) in pixels
            subscan_region: Tuple of (x, y, width, height) defining a sub-region of the image to scan
            arbitrary_scan: Boolean indicating if arbitrary scan is to be used
        """
        if self._engine is None:
            # NOTE if offline, simulator will return an image if QD_SCAN_ENGINE is initialised
            print("Scan engine not initialised. Returning blank image.")
            return np.zeros(full_image_size)

        if enabled_inputs is None:
            enabled_inputs = self._enabled_inputs

        # enabled_inputs = MICROSCOPE_CONFIG.get('qd_enabled_inputs', [3])  # QD channel
        if arbitrary_scan:
            print("Using arbitrary scan mode.")
            return np.zeros(full_image_size)  # Placeholder for arbitrary scan image retrieval
        
        # sx = start x, sy = start y, ex = end x, ey = end y
        if subscan_region is not None:
            print(f"Performing raster scan on region: {subscan_region} (width, height, x, y)")
            width, height, sx, sy= subscan_region    
            ex = sx + width
            ey = sy + height
        else:
            print(f"Performing full image scan of {full_image_size}.")
            width, height = full_image_size
            sx, sy = 0, 0
            ex, ey = width, height

        # should not be needed
        # scan_engine.set_image_size(*full_image_size) # Set image size
        # scan_engine.set_enabled_inputs(enabled_inputs)

        self._engine.set_image_area(
            sizex = full_image_size[0],
            sizey = full_image_size[1],
            startx = sx,
            starty = sy,
            endx = ex,
            endy = ey
        )        
        #print(scan_engine.get_image_size())
        # Now setup frame monitor
        frame_monitor = FrameMonitor( # NOTE +1 needed for epsic scan engine
            full_image_size[0] + 1, 
            full_image_size[1] + 1, 
            inputs = enabled_inputs,  # QD channel 
            max_queue_size=1,
        )
        frame_monitor.register(self._engine)

        # mode 0 is what was used prior but leads to race conditions for some reason
        self._engine.start_imaging(1) # potentially change the imaging mode here if needed - 1 seems to work without a delay?
        # time.sleep(0.5) # needs a moment to get queue setup
        self._engine.stop_imaging()
        frame_monitor.wait_for_image()
        # frame_monitor.wait_for_image(timeout=self._engine.get_image_time()+1.0)

        # retrieve the frame from the monitor
        frame = frame_monitor.pop().get_input_data(enabled_inputs[0])
        frame = frame[sy:ey, sx:ex]  # Crop to the scanned region

        # if rescale_uint8:
        #     frame = preprocess.bytescale(frame)

        return frame  # Return the scanned region
    
    def drift_correct(self, lenses, survey_size, initial_survey_img, drift_subscan_coords=None,
                      max_shift_pixel=None, window_type='hanning', **kwargs):
        """
        returns (shift_x, shift_y), drift_corrected_image
        NOTE the shift returned is the direction the object has moved. 
        *1 to follow the object, *-1 to counteract the drift

        lenses: LensesController object to control beam blanking etc during drift correction
        survey_size: size of the survey image e.g. (512,512) needed to set scan size for drift correction scan. Assumed to be width,height
        initial_survey_img: initial survey image as reference for comparison
        drift_subscan_coords: (width, height, x1, y1) to define subscan region if used for drift correction, if None, uses full image at resolution of initial survey
        max_shift_pixel: maximum allowed shift in pixels to prevent outliers
        window_type: type of windowing to apply to images before phase correlation, options are 'hanning', 'sobel', 'median'
        """

        if drift_subscan_coords is not None:
            width, height, x1, y1 = drift_subscan_coords
        else:
            width, height, x1,y1 = survey_size[1], survey_size[0], 0, 0

        if max_shift_pixel is None:
            # Max shift is half the full scan size if not specified, to prevent large outliers
            max_shift_pixel = min(width//2, height//2)
        
        with lenses.beam_unblanked():
            scan_result = self.get_image(
                full_image_size = (survey_size[1], survey_size[0]),
                subscan_region = drift_subscan_coords,
            )
        print("scan box:", width, height, x1, y1)
        shift_px, _ = drift_calc(
            initial_survey_img,
            scan_result,
            max_shift_pixel=max_shift_pixel,
            window_type=window_type,
        )

        return shift_px, scan_result



class QDMerlinDetector(STEM4DDetector):
    """
    Merlin 4DSTEM triggered by QD ScanEngine - placeholder
    """
    def __init__(self, qd_imaging:QDImaging, merlin_conn, trigger_channel=6,
                 eos3=None, ht3=None, scan3=None, gun3=None, def3=None, lens3=None,
                 apt3=None, stage3=None, zdf=38942):
        # self._engine = scan_engine # QD Scan engine
        self._imaging = qd_imaging
        self._merlin_conn = merlin_conn
        self._trigger_channel = trigger_channel
        # Raw PyJEM column controllers for metadata export
        self._eos3 = eos3
        self._ht3 = ht3
        self._scan3 = scan3
        self._gun3 = gun3
        self._def3 = def3
        self._lens3 = lens3
        self._apt3 = apt3
        self._stage3 = stage3
        self._zdf = zdf

    def _enable_trigger_line(self):
        line_active = "".join(map(str, map(int, (i == 9 - self._trigger_channel for i in range(10)))))
        self._imaging._engine.enable_lines(int(line_active, 2))
        self._imaging._engine.set_output_line_a(
            self._trigger_channel,
            3,      # mode - Source timed mode ENABLED!
            6,      # source - Rising edge -> if it was 7 then falling edge 
            on_time=1e-5,
            # delay = 0,
            # nb_pulses = ... # count in Max code
        )

    def _disable_trigger_line(self):
        # Finally, disable the line again
        line_active = "".join(map(str, map(int, (i == 9 - self._trigger_channel for i in range(10)))))
        self._imaging._engine.disable_lines(int(line_active, 2))
        self._imaging._engine.set_output_line_a(
            self._trigger_channel,
            0, # DISABLED!
            6, # Rising edge -> if it was 7 then falling edge 
            on_time = 1e-5,
            # delay = 0,
            # nb_pulses = ... # count in Max code
            )      

    def acquire(
        self, lenses, full_image_size, subscan_region, 
        merlin_dwell_time_s, merlin_save_path, merlin_bit_depth
    ) -> str:
        """
        setup Merlin, enable TTL, scan via QD, disable TTL.
        NOTE subscan_region is (width, height, x1, y1) where height has been increased by 1 for QD imaging
            - Will do -1 for merlin height internally to correct this
        Returns timestamp for the saved data.
        """
        def _merlin_scan(
            timestamp,
            full_image_size=(4096, 4096),
            subscan_region=None,
        ):
            try:
                print("******First Try******")
                self._merlin_conn.setValue('FILENAME', f"{timestamp}_data")
            except IndexError:
                print("*****TRY AGAIN!**")
                self._merlin_conn.setValue('FILENAME', f"{timestamp}_data")
            self._merlin_conn.setValue('TRIGGERSTART', 1) 
            self._merlin_conn.setValue('TRIGGERSTOP', 1)
            #time.sleep(1)
            
            with lenses.beam_unblanked():
                self._merlin_conn.MPX_CMD(type_cmd='CMD', cmd='SCANSTARTRECORD')
                time.sleep(1)
                # unblank here instead?
                _ = self._imaging.get_image(
                    full_image_size=full_image_size,
                    subscan_region=subscan_region,
                    enabled_inputs=[self._trigger_channel],
                )
                
                time.sleep(1)
                self._merlin_conn.setValue('TRIGGERSTART', 0)
                self._merlin_conn.setValue('TRIGGERSTOP', 0)
                time.sleep(1)

        # Kept this format as technically could have QD scansize = Merlin scan size
        if subscan_region is not None:
            width, height, x1, y1 = subscan_region
        else:
            width, height = full_image_size
            x1, y1 = 0, 0

        pixels_to_acquire = width * (height - 1)
        # exposure_s = merlin_dwell_time_s
        save_path = merlin_save_path.replace("/", "\\")

        # Setup merlin params
        merlin_setup(
            self._merlin_conn,
            pixels=pixels_to_acquire,
            bit_depth=merlin_bit_depth,
            exposure=merlin_dwell_time_s,
            save_path=save_path,
            px_val_x=width,
            px_val_y=height - 1,
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        params_savepath = f"{save_path}\\{timestamp}.hdf"
        merlin_params = {'set_dwell_time(usec)': merlin_dwell_time_s*1e6, 'set_scan_px': pixels_to_acquire,
                            'set_bit_depth': merlin_bit_depth}
        
        self.export(
            file=params_savepath,
            scan_size=(width, height - 1), # scan size assumed to be the scan size
            full_image_size=full_image_size, # scaled full image size for determining steps size etc.
            
            **merlin_params
        )

        self._enable_trigger_line()

        try:
            _merlin_scan(
                timestamp=timestamp,
                full_image_size=full_image_size,
                subscan_region=subscan_region,
            )
        finally:
            self._disable_trigger_line()

        return timestamp

    @property
    def merlin_camera_length(self):
        ht = self._ht3.GetHtValue()
        cam = int(self._eos3.GetMagValue()[0])
        if ht == 80_000:
            factor = 1.58
        elif ht == 300_000:
            factor = 1.64
        else:
            factor = 1
        return factor * cam

    @property
    def defocus_per_bit(self):
        """
        The per-bit defocus for the microscope based on acceleration voltage.

        Returns
        -------
        float
            The current defocus per bit for the microscope - this is based on the acceleration voltage.
        """
        ht = self._ht3.GetHtValue()
        if ht == 300_000:
            return 0.7622
        elif ht == 200_000:
            return 0.8206
        elif ht == 80_000:
            return 0.75
        elif ht == 60_000:
            return 0.84
        elif ht == 30_000:
            return 0.8
        elif ht == 0:
            return 0.7
        else:
            return 0.75

    @property
    def defocus(self):
        """
        Calculate the absolute defocus based on OLf and the zero_OLfine value.
        """
        return self.defocus_per_bit * (self._lens3.GetOLf() - self._zdf)

    @property
    def convergence(self):
        """
        Calculate the convergence of the system based on the acceleration voltage.

        Returns
        -------
        float
            The convergence semi-angle.
        """
        ht = self._ht3.GetHtValue()
        spot_size = self._apt3.GetExpSize(1) # this is the CL2 aperture size. 0 is CL1
        # Convergence semi-angle map FOR THE E02!
        mapping_300k = {1: 0.0440, 2: 0.0336, 3: 0.0262, 4: 0.0164, 5: 0.0076}
        mapping_200k = {1: 0.0377, 2: 0.0288, 3: 0.0224, 4: 0.0140, 5:0.0064} 
        mapping_80k =  {1: 0.04165, 2: 0.03174, 3: 0.02480, 4: 0.01544,}
        mapping_60k =  {1: 0.0515, 2: 0.0391, 3: 0.0306, 4: 0.0190, 5 : 0.0087}
        mapping_30k =  {1: 0.061, 2: 0.0481, 3: 0.0379, 4: 0.0242,}
        # defaults if ht does not exist in the main mapping dict
        mapping_def =  {1: 0.061, 2: 0.0481, 3: 0.0379, 4: 0.0242,}
        mapping = {
            300_000: mapping_300k,
            200_000: mapping_200k,
            80_000: mapping_80k,
            60_000: mapping_60k,
            30_000: mapping_30k,
        }
        return mapping.get(ht, mapping_def).get(spot_size, 0.0)

    def export(self, file: str, scan_size: int, full_image_size: tuple, **merlin):
        """
        Export the microscope parameters to a hdf5 file.

        Parameters
        ----------
        file: str
            The complete filepath.
        scan_size: tuple
            The size of the scan (width, height) in pixels.
        full_scan_size: tuple
            The size of the full image (width, height) in pixels used in the QD scan for calculating stepsize
        **merlin: 
            The additional merlin parameters.
        """
        with h5py.File(file, "a") as f:
            if self._eos3 is None:
                return
            metadata_group = f.create_group('metadata')

            for key, value in merlin.items():
                metadata_group[key] = value

            local_mag = int(self._eos3.GetMagValue()[0])
            local_fov = 10e-6 * (20000 / local_mag)
            local_ht = self._ht3.GetHtValue()
            
            metadata_group['magnification'] = local_mag
            metadata_group['nominal_scan_rotation'] = self._scan3.GetRotationAngle()
            metadata_group['ht_value(V)'] = local_ht
            metadata_group['nominal_camera_length(m)'] = int(self._eos3.GetStemCamValue()[0]) * 1e-3 # in mm so convert to m
            metadata_group['merlin_camera_length(m)'] = self.merlin_camera_length
            metadata_group['spot_size'] = self._eos3.GetSpotSize()
            if self._apt3 is not None:
                # NOTE this gives the selected aperture size based on the panel. If the smallest is not selected, this is incorrect for determining conv semi-angle
                # e.g. if user has CL1 selected, then CL1-X will be given
                metadata_group['aperture_size'] = self._apt3.GetExpSize(self._apt3.GetExpKind()) 
                metadata_group['aperture_size_CL1'] = self._apt3.GetExpSize(0)
                metadata_group['aperture_size_CL2'] = self._apt3.GetExpSize(1)
            metadata_group['full_scan_size(px)'] = full_image_size # width of the full image used for the QD scan
            metadata_group['scan_size(px)'] = scan_size # width
            metadata_group['field_of_view(m)'] = local_fov
            metadata_group['step_size(m)'] = local_fov / scan_size[0] # assumes square scan
            metadata_group['zero_OLfine'] = self._zdf
            metadata_group['current_OLfine'] = self._lens3.GetOLf()

            metadata_group['A1_value_(kV)'] = self._gun3.GetAnode1CurrentValue()
            metadata_group['A2_value_(kV)'] = self._gun3.GetAnode2CurrentValue()
            metadata_group['emission_current(uA)'] = self._gun3.GetEmissionCurrentValue()

            # Stage positions — GetPos() returns [x, y, z, tx, ty] in nm / degrees
            if self._stage3 is not None:
                stage_pos = self._stage3.GetPos()
                metadata_group['x_pos(m)'] = stage_pos[0] * 1e-9
                metadata_group['y_pos(m)'] = stage_pos[1] * 1e-9
                metadata_group['z_pos(m)'] = stage_pos[2] * 1e-9
                metadata_group['x_tilt(deg)'] = stage_pos[3]
                metadata_group['y_tilt(deg)'] = stage_pos[4]

            # Lens values via raw Lens3 getters
            lens_group = metadata_group.create_group('lens_values')
            lens_getters = {
                'CL1': self._lens3.GetCL1, 'CL2': self._lens3.GetCL2, 'CL3': self._lens3.GetCL3,
                'CM': self._lens3.GetCM,
                'OLc': self._lens3.GetOLc, 'OLf': self._lens3.GetOLf,
                'OM': self._lens3.GetOM, 'OM2': self._lens3.GetOM2,
                'IL1': self._lens3.GetIL1, 'IL2': self._lens3.GetIL2, 'IL3': self._lens3.GetIL3, 'IL4': self._lens3.GetIL4,
                'PL1': self._lens3.GetPL1, 'PL2': self._lens3.GetPL2, 'PL3': self._lens3.GetPL3,
                'FLc': self._lens3.GetFLc, 'FLf': self._lens3.GetFLf, 
                'FLcomp1': self._lens3.GetFLcomp1, 'FLcomp2': self._lens3.GetFLcomp2,
            }
            for name, getter in lens_getters.items():
                try:
                    lens_group[name] = getter()
                except Exception:
                    pass

            defl_group = metadata_group.create_group('deflector_values')
            defl_group['CLA1'] = self._def3.GetCLA1()
            defl_group['CLA2'] = self._def3.GetCLA2()
            defl_group['CLS'] = self._def3.GetCLs()
            defl_group['Correction'] = self._def3.GetCorrection()
            defl_group['GUNA1'] = self._def3.GetGunA1()
            defl_group['GUNA2'] = self._def3.GetGunA2()
            defl_group['ILS'] = self._def3.GetILs()
            defl_group['IS1'] = self._def3.GetIS1()
            defl_group['IS2'] = self._def3.GetIS2()
            defl_group['MAGADJUST'] = self._def3.GetMagAdjust()
            defl_group['OLS'] = self._def3.GetOLs()
            defl_group['OFFSET'] = self._def3.GetOffset()
            defl_group['PLA'] = self._def3.GetPLA()
            defl_group['ROTATION'] = self._def3.GetRotation()
            defl_group['SCAN1'] = self._def3.GetScan1()
            defl_group['SCAN2'] = self._def3.GetScan2()
            defl_group['SHIFBAL'] = self._def3.GetShifBal()
            defl_group['SPOTA'] = self._def3.GetSpotA()
            defl_group['STEMIS'] = self._def3.GetStemIS()
            defl_group['TILTBAL'] = self._def3.GetTiltBal()
            defl_group['ANGBAL'] = self._def3.GetAngBal()

            if int(local_ht) in {200000, 300000, 60000, 80000}:
                metadata_group['defocus(nm)'] = self.defocus
                metadata_group['defocus_per_bit(nm)'] = self.defocus_per_bit
                metadata_group['defocus_offset(nm)'] = 0
                metadata_group['convergence_semi-angle(rad)'] = self.convergence

