from abc import ABC, abstractmethod
from contextlib import contextmanager
import numpy as np

# Connection ABC
class Method(ABC):
    """
    One hardware integration, e.g. PyJEM, QD ScanEngine, Merlin or Gatan, that an instrument declares under "hardware" in its json.
    A Method opens and holds its connection handles (the session only asks each declared Method to validate, connect or disconnect)
    and builds the controllers (stage, lenses, imaging, detectors) for the categories it implements.
    """
    name: str   # the key used in the instrument JSON
    label: str  # display label for the UI
    categories: set[str]  # the hardware categories this method implements so far, e.g. {"imaging", "stemsi_detector"}

    def __init__(self, config: dict):
        self.config = config  # defined from the config.json

    def validate(self, instrument):
        """Optionally check if required instrument's settings are not available as defined in the func. 
        Runs at start and raises ValueError if issue. By default, runs nothing"""

    @abstractmethod
    def connect(self, instrument, attempts=None) -> dict:
        """Open the connection, or reuse existing one. Returns self._result()."""

    @abstractmethod
    def disconnect(self):
        """Drop the connection as it is not wanted anymore."""

    @abstractmethod
    def available(self, category: str) -> bool:
        """Is this catergory available in the method? If it is, will display as an option in the frontend."""

    @abstractmethod
    def build(self, category: str, instrument, built: dict, methods: dict):
        """
        Make the controller for the given catergory in this method.
        
        built: the controllers already made that may be needed to create other controllers (stage, lenses, imaging come before 4dstem_detector and stemsi_detector).
        methods: all the session's available methods, for when a controller requires method owned variables e.g. PyJEM's column controllers are needed for merlin currently.
        """

    def _result(self, connected, message):
        """
        Helper func for displaying if the connect() was a success.
        """
        return {"device": self.name, "label": self.label, "connected": connected, "message": message}


# previous controllers for stage, imaging, lenses etc.
class StageController(ABC):
    """
    Abstract class for stage related operations: moving, tilting, getting position etc.
    """
    @abstractmethod
    def get_position(self) -> dict: ...

    @abstractmethod
    def move_absolute(self, value: float, axis: str = 'x'): ...

    @abstractmethod
    def move_relative(self, magnitude: float, axis: str = 'x'): ...
    
    @abstractmethod
    def tilt_relative(self, degrees: float, axis: str = 'x'): ...
    
    @abstractmethod
    def tilt_absolute(self, degrees: float, axis: str = 'x'): ...

class ImagingController(ABC):
    """
    Abstract class for imaging operations
    Default will be ADF but can be extended to other imaging modes in the future
    """
    @abstractmethod
    def set_dwell_time(self, dwell_time_s: float): ...

    @abstractmethod
    def set_flyback_time(self, flyback_time_s: float): ...

    @abstractmethod
    def get_image(self, full_image_size, subscan_region=None, **kwargs) -> np.ndarray: ...

    def drift_correct(self, lenses, survey_size, initial_survey_img, drift_subscan_coords=None,
                      max_shift_pixel=None, window_type='hanning', **kwargs):
        """Returns (shift_px, new_survey_image) comparing a new scan against initial_survey_img."""
        raise NotImplementedError(f"{type(self).__name__} does not support drift correction")

class LensController(ABC):
    """
    Abstract class containing lense related operations:Beam blanking, detector positioning, autofocus etc.
    """

    @abstractmethod
    def beam_blank(self, blank: bool): ...

    @abstractmethod
    @contextmanager
    def beam_unblanked(self): ...

    @abstractmethod
    def set_detector_position(self, inserted: bool): ...

    @abstractmethod
    @contextmanager
    def detector_inserted(self): ...

    @abstractmethod
    @contextmanager
    def detector_removed(self): ...

    @abstractmethod
    def get_px_res(self, imaging, savefolder=None, savefile=None, **kwargs):
        """Pixel size in Angstroms, or None if unavailable."""
        return None

    @abstractmethod
    def get_defocus(self):
        """Return the current OLf value, or None if lens control unavailable."""
        return None
    
    @abstractmethod
    def set_defocus(self, olf_value):
        """Set the OLf (fine objective lens) value. Does nothing if lens control unavailable."""
        pass

    @abstractmethod
    def get_magnification(self):
        """Return the current absolute magnification value, or None if unavailable."""
        return None
    
    @abstractmethod
    def set_magnification(self, target_mag):
        """Go to a target magnification. Return True if reached, False if not or unavailable."""
        return False

    def increment_magnification(self, steps: int) -> bool:
        """Zoom in (+n steps) or out (-n steps) by a number of steps. Return False if it could not. E.g. steps = -5 will zoom out 5 increments"""
        return False

    def autofocus(self, imaging, method="pyjem", focus_region='full', full_image_size=None,
                  survey_image_size=None, subscan_region=None, **kwargs):
        """Focus on the full image or a subscan region. Does nothing if unavailable."""
        pass

class STEM4DDetector(ABC):
    """
    Abstract class for 4D-STEM detector acquisition.
    Will require lens and imaging control for setup and triggering depending on the setup used, 
    but may have additional methods for handling things.
    """

    @abstractmethod
    def acquire(
        self,
        lenses: LensController,
        full_image_size,
        subscan_region=None,
        **kwargs
    ) -> str:
        """
        Execute a full 4D-STEM acquisition — setup, scan, teardown.
        Returns a save path or timestamp identifier.
        """
        ...

class STEMSpectroscopy(ABC):
    """
    Abstract class for STEM SI acquisition.
    Will require lens and imaging control for setup and triggering depending on the setup used, 
    but may have additional methods for handling things.
    """

    @abstractmethod
    def acquire(
        self,
        full_image_size,
        subscan_region=None,
        **kwargs
    ) -> str:
        """
        Does SI imaging
        """
        ...
