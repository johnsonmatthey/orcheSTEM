from microscope.merlin_commands import MERLIN_connection as Merlin
import json
CONFIG_PATH = 'microscope/config.json'

def initialise_pyjem(imaging_mode='ADF1'):
    """
    Initialise PyJEM connection Stage and Detector
    """
    try:
        from PyJEM import TEM3
        from PyJEM import detector
        
        stage = None
        while stage is None:
            try:
                stage = TEM3.Stage3()
                print("Stage connected!")
            except Exception as e:
                print(e)

        print(detector.get_attached_detector(), f"detectors  attached. Using {imaging_mode} detector.")
        det = detector.Detector(imaging_mode)
        return stage, det
    except Exception as e:
        print(f"PyJEM initialization failed: {e}")
        print("Running in Offline mode.")
        return None, None

def initialise_pyjem_column():
    """
    Initialise PyJEM column controllers: Def3, Detector3, EOS3, Lens3, HT3, Scan3, GUN3, Apt3
    """
    try:
        from PyJEM.TEM3 import Def3, Detector3, EOS3, Lens3, HT3, Scan3, GUN3, Apt3
        lens3 = Lens3()
        def3 = Def3()
        detector3 = Detector3()
        eos3 = EOS3()
        ht3 = HT3()
        scan3 = Scan3()
        gun3 = GUN3()
        apt3 = Apt3()
        print("PyJEM column controllers (Def3, Detector3, EOS3, Lens3, HT3, Scan3, GUN3, Apt3) connected.")
        return def3, detector3, eos3, lens3, ht3, scan3, gun3, apt3
    except Exception as e:
        print(f"PyJEM column controller init failed: {e}. Running in Offline mode.")
        return None, None, None, None, None, None, None, None

def initialise_qd_scanengine(full_scan_size=(4096, 4096), enabled_inputs=[3], flyback_time=100e-6, dwell_time=15e-6):
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
    
def initialise_merlin_connection(hostname):
    """
    Initialise Merlin connection
    """
    try:
        merlin_conn = Merlin(hostname=hostname)
        return merlin_conn
    except Exception as e:
        print(f"Merlin initialization failed: {e}")
        print("Running in Offline mode.")
        return None

def load_microscope_config(rel_path=CONFIG_PATH):
    """
    Load microscope configuration from JSON file
    """
    try:
        with open(rel_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Failed to load microscope configuration: {e}")
        return None

# Initialise microscope components based on config
MICROSCOPE_CONFIG = load_microscope_config()

PYJEM_STAGE, PYJEM_DET = initialise_pyjem(
    imaging_mode=MICROSCOPE_CONFIG.get('detector_name', 'ADF1', )
    )

(
    _DEF3_CONTROLLER, _DETECTOR3_CONTROLLER, _EOS3_CONTROLLER,
    _LENS3_CONTROLLER, _HT3_CONTROLLER, _SCAN3_CONTROLLER,
    _GUN3_CONTROLLER, _APT3_CONTROLLER
) = initialise_pyjem_column()

QD_SCAN_ENGINE = initialise_qd_scanengine(
    enabled_inputs=MICROSCOPE_CONFIG.get('qd_enabled_inputs', [3]),
    flyback_time=MICROSCOPE_CONFIG.get('default_settings').get('flyback_time_s', 100e-6),
    dwell_time=MICROSCOPE_CONFIG.get('default_settings').get('dwell_time_s', 15e-6)
)

if PYJEM_DET is None:
    MERLIN_CONN = None # Dont bother initialising Merlin if no PyJEM detector
else:
    MERLIN_CONN = initialise_merlin_connection(
        hostname=MICROSCOPE_CONFIG.get('hostname')
    )

GATAN_K3 = None # Placeholder for future Gatan 4D-STEM connection

def get_microscope_options():
    """
    Build the microscope options dict dynamically.
    Gatan availability is checked live via GMS poll heartbeat rather than a static connection object.
    """
    from microscope.gms_backend import gms_is_connected
    gatan_connected = gms_is_connected()
    return {
        "stage": [
            {"label": "PyJEM", "value": "pyjem", "exists": PYJEM_STAGE is not None},
            {"label": "Gatan", "value": "gatan", "exists": gatan_connected},
        ],
        "lenses": [
            {"label": "PyJEM", "value": "pyjem", "exists": PYJEM_DET is not None},
        ],
        "imaging": [
            {"label": "PyJEM", "value": "pyjem", "exists": PYJEM_DET is not None},
            {"label": "Gatan", "value": "gatan", "exists": gatan_connected},
            {"label": "QD ScanEngine", "value": "qd_scanengine", "exists": QD_SCAN_ENGINE is not None},
        ],
        "4dstem_detector": [
            {"label": "Merlin", "value": "merlin", "exists": MERLIN_CONN is not None},
            {"label": "Gatan K3", "value": "gatan_k3", "exists": GATAN_K3 is not None},
        ],
        "stemsi_detector": [
            {"label": "Gatan", "value": "gatan", "exists": gatan_connected},
        ]
    }
