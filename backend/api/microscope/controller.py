from abc import ABC, abstractmethod
from contextlib import contextmanager
import numpy as np

class StageController(ABC):
    """
    Abstract class for stage related operations: moving, tilting, getting position etc.
    """
    @abstractmethod
    def get_position(self) -> dict: ...

    @abstractmethod
    def move_absolute(self, axis:str = 'x'): ...

    @abstractmethod
    def move_relative(self, magnitude: float, axis: str = 'x'): ...

    @abstractmethod
    def tilt_relative(self, degrees: float, axis: str = 'x'): ...


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
    def set_detector_position(self, detector_name: str, inserted: bool): ...

    @abstractmethod
    @contextmanager
    def detector_inserted(self, detector_name: str): ...

    @abstractmethod
    @contextmanager
    def detector_removed(self, detector_name: str): ...

    def get_defocus(self):
        """Return the current objective lens fine (OLf) value, or None if unavailable."""
        return None

    def set_defocus(self, olf_value):
        """Set the OLf (fine objective lens) value. Does nothing if lens control unavailable."""
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

class MicroscopeController:
    """
    Assembled overall controller based on user selected options.
    This is going to be the main class that will be used in the enpoints where it contains the stage, lens and imaging controllers
    """
    def __init__(self, stage, lenses, imaging, stem4d_detector=None, stemsi=None):
        self.stage = stage
        self.lenses = lenses
        self.imaging = imaging
        self.stem4d_detector = stem4d_detector  # Optional[STEM4DDetector]
        self.stemsi = stemsi  # Optional[STEMSpectroscopy]


from microscope.microscope_config import (
    MERLIN_CONN, PYJEM_STAGE, PYJEM_DET, QD_SCAN_ENGINE, MICROSCOPE_CONFIG,
    _DEF3_CONTROLLER, _DETECTOR3_CONTROLLER, _EOS3_CONTROLLER, _LENS3_CONTROLLER,
    _HT3_CONTROLLER, _SCAN3_CONTROLLER, _GUN3_CONTROLLER, _APT3_CONTROLLER
)
from microscope.pyjem_backend import PyJEMStage, PyJEMImaging, PyJEMLenses
from microscope.qd_backend import QDImaging, QDMerlinDetector
from microscope.gms_backend import GatanImaging, GatanSpectroscopy

enabled_inputs = MICROSCOPE_CONFIG.get('qd_enabled_inputs', [3])

def build_controller(stage: str, lenses: str, imaging: str, stem4d: str = None, stemsi: str = None) -> MicroscopeController:
    """Build a MicroscopeController from user dropdown values."""

    stage_map = {
        "pyjem": lambda: PyJEMStage(PYJEM_STAGE),
        # "gatan": lambda: GatanStage(dm_client),
    }
    lens_map = {
        "pyjem": lambda: PyJEMLenses(_DEF3_CONTROLLER, _DETECTOR3_CONTROLLER, _EOS3_CONTROLLER, _LENS3_CONTROLLER),
    }
    imaging_map = {
        "pyjem": lambda: PyJEMImaging(PYJEM_DET),
        "qd_scanengine": lambda: QDImaging(QD_SCAN_ENGINE, enabled_inputs),
        "gatan": lambda: GatanImaging(),
    }
    stage_inst=stage_map[stage]()
    lenses_inst=lens_map[lenses]()
    imaging_inst=imaging_map[imaging]()

    # Optional features that may reuse the above controllers
    stem4d_map = {
        "merlin": lambda: QDMerlinDetector(
            imaging_inst, MERLIN_CONN,
            eos3=_EOS3_CONTROLLER, ht3=_HT3_CONTROLLER, scan3=_SCAN3_CONTROLLER,
            gun3=_GUN3_CONTROLLER, def3=_DEF3_CONTROLLER, lens3=_LENS3_CONTROLLER,
            apt3=_APT3_CONTROLLER, stage3=PYJEM_STAGE,
        ),
    }
    stem4d_inst = stem4d_map[stem4d]() if stem4d is not None else None

    stemsi_map = {
        "gatan": lambda: GatanSpectroscopy(imaging_inst),
    }
    stemsi_inst = stemsi_map[stemsi]() if stemsi is not None else None

    return MicroscopeController(
        stage=stage_inst,
        lenses=lenses_inst,
        imaging=imaging_inst,
        stem4d_detector=stem4d_inst,
        stemsi=stemsi_inst,
    )