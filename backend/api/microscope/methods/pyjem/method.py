from microscope.core.interfaces import Method
from microscope.methods.pyjem.controllers import PyJEMStage, PyJEMImaging, PyJEMLenses


def initialise_pyjem_detector(imaging_mode):
    """
    Initialise the PyJEM detector used for imaging.
    """
    try:
        from PyJEM import detector
        print(detector.get_attached_detector(), f"detectors  attached. Using {imaging_mode} detector.")
        return detector.Detector(imaging_mode)
    except Exception as e:
        print(f"PyJEM detector initialization failed: {e}")
        return None

def initialise_pyjem(imaging_mode, attempts=3):
    """
    Initialise PyJEM connection Stage and Detector. attempts=None keeps retrying the stage until it connects.
    """
    try:
        # detector is separated out as non issue where may want to change the detector later
        from PyJEM import TEM3
        from PyJEM import detector
        stage = None
        tries = 0
        while stage is None:
            try:
                stage = TEM3.Stage3()
                print("Stage connected!")
            except Exception as e:
                print(e)
                tries += 1
                if attempts is not None and tries >= attempts:
                    raise

        return stage, initialise_pyjem_detector(imaging_mode)
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


class PyJEMMethod(Method):
    name = "pyjem"
    label = "PyJEM"
    categories = {"stage", "lenses", "imaging"}

    def __init__(self, config):
        super().__init__(config)
        self.stage = self.det = None
        self.column = (None,) * 8  # def3, detector3, eos3, lens3, ht3, scan3, gun3, apt3
        self._detector_name = None  # the detector the current connection was opened with

    def validate(self, instrument):
        # NEed to know what detector to use and the relevant indexing, where
        # raises a ValueError if the instrument has no pyjem imaging settings (Instrument.options)
        instrument.options("imaging", "pyjem")  

    def connect(self, instrument, attempts=None):
        """Func to setup pyjem connections where relevant. Also can set the detector connection to different connector if needed"""
        detector_name = instrument.options("imaging", "pyjem")["detector_name"]

        def pyjem_connected():
            """ Helper to check if connections are done correct. Returns True or False"""
            return self.stage is not None and self.det is not None and self.column[0] is not None

        # if already connected, only the detector may need swapping
        if pyjem_connected():
            if self._detector_name != detector_name: # if not, reset the detector connections
                self.det = initialise_pyjem_detector(detector_name)  # stage and column stay open
        else:
            # otherwise, connect to pyjem from scratch 
            self.stage, self.det = initialise_pyjem(imaging_mode=detector_name, attempts=attempts)
            self.column = initialise_pyjem_column()

        self._detector_name = detector_name #stored detector name for future ref and checking
        # recheck as the attempts above may have failed
        connected = pyjem_connected()

        parts = {"stage": self.stage, f"{detector_name} detector": self.det, "column controllers": self.column[0]}
        failed = [name for name, handle in parts.items() if handle is None]
        return self._result(connected, "connected" if connected else f"failed to connect: {', '.join(failed)}")

    def available(self, category):
        return (self.stage if category == "stage" else self.det) is not None

    def build(self, category, instrument, built, methods):
        if category == "stage":
            return PyJEMStage(self.stage)
        if category == "lenses":
            settings = instrument.options("imaging", "pyjem")
            def3, detector3, eos3, lens3 = self.column[:4] # def3, detector3, eos3, lens3, ht3, scan3, gun3, apt3
            return PyJEMLenses(
                def3, detector3, eos3, lens3,
                detector_name=settings["detector_name"],
                detector_mapping=settings["detector_mapping"],
                imaging_detector=self.det,
            )
        if category == "imaging":
            return PyJEMImaging(self.det)
        raise ValueError(f"{self.label} cannot build '{category}'")

    def disconnect(self):
        self.stage = self.det = None
        self.column = (None,) * 8
        self._detector_name = None
