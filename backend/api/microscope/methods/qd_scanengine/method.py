from microscope.core.interfaces import Method
from microscope.methods.qd_scanengine.controllers import QDImaging


def initialise_qd_scanengine(enabled_inputs, flyback_time, dwell_time, full_scan_size=(4096, 4096)):
    """
    Initialise QD pyscanengine
    default full_scan_size is (4096, 4096) and can change as needed later
    """
    try:
        from pyscanengine import ScanEngine
        scan_engine = ScanEngine(1)
        scan_engine.set_image_size(*full_scan_size) # Set image size to 4k x 4k upon initialisation but change as needed later
        scan_engine.set_enabled_inputs(enabled_inputs)  # Channel for QD ADF1 - LOOK LATER NOTE!

        # Ensure no TTL triggers are set
        scan_engine.disable_lines(0b1111111111) # disable all 10 output lines
        for i in range(10): # Repeat for all 10 output indices
            # Disable any connections on output lines
            scan_engine.set_output_line_a(i, 0)  
        
        scan_engine.pixel_time = dwell_time  # default dwell time 15 us
        scan_engine.set_flyback_time(flyback_time)  # default flyback time 100 us

        return scan_engine
    except Exception as e:
        print(f"QD ScanEngine initialization failed: {e}")
        print("Running in Offline mode.")
        return None


class QDScanEngineMethod(Method):
    name = "qd_scanengine"
    label = "QD ScanEngine"
    categories = {"imaging"}

    def __init__(self, config):
        super().__init__(config)
        self.engine = None
        self._enabled_inputs = None  # the inputs the engine is currently set to

    def validate(self, instrument):
        if "enabled_inputs" not in instrument.options("imaging", "qd_scanengine"):
            raise ValueError(f"Instrument '{instrument.instrument_id}' needs enabled_inputs under imaging.qd_scanengine")

    def connect(self, instrument, attempts=None):
        enabled_inputs = instrument.options("imaging", "qd_scanengine")["enabled_inputs"]
        # # only reconnect if None OR if enabled inputs have changed in the scan engine
        if self.engine is None: 
            timings = self.config["default_settings"]
            self.engine = initialise_qd_scanengine(enabled_inputs, timings["flyback_time_s"], timings["dwell_time_s"])
            self._enabled_inputs = enabled_inputs
        elif self._enabled_inputs != enabled_inputs:
            try:
                self.engine.set_enabled_inputs(enabled_inputs)
                self._enabled_inputs = enabled_inputs
            except Exception as e:
                print(f"Could not update QD enabled inputs: {e}")
        connected = self.engine is not None
        return self._result(connected, f"inputs {enabled_inputs}" if connected else "QD scan engine unavailable")

    def available(self, category):
        return self.engine is not None

    def build(self, category, instrument, built, methods):
        if category == "imaging":
            return QDImaging(self.engine, instrument.options("imaging", "qd_scanengine")["enabled_inputs"])
        raise ValueError(f"{self.label} cannot build '{category}'")

    def disconnect(self):
        self.engine = None
        self._enabled_inputs = None
