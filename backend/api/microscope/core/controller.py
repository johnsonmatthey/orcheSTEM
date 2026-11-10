from microscope.core.session import SESSION

class MicroscopeController:
    """
    Assembled overall controller based on user selected options.
    This is the main class used in the enpoints where it contains the stage, lens and imaging controllers
    alongside SI, 4dSTEM and further methods
    """
    def __init__(self, stage, lenses, imaging, stem4d_detector=None, stemsi=None):
        self.stage = stage
        self.lenses = lenses
        self.imaging = imaging
        self.stem4d_detector = stem4d_detector  # Optional[STEM4DDetector]
        self.stemsi = stemsi  # Optional[STEMSpectroscopy]

def _validate_selection(instrument, selection: dict):
    """
    Check selected methods are stated in the instrument json before building. stage, lenses and imaging
    must be set, the remaining are optional where None will skip. 

    Selection is a dict containing the catergort and the associated name as defined in the hardwares method class e.g. 
    GatanMethod.name returns 'gatan' , so a valid example of selection is:
    {"stage": "pyjem", "lenses": "pyjem", "imaging": "qd_scanengine", "4dstem_detector": None, "stemsi_detector": "gatan"}

    """
    for category in ("stage", "lenses", "imaging"): # must have these 3 methods at least
        if selection[category] is None:
            raise ValueError(f"No {category} method selected")
    for category, method in selection.items():
        if method is not None:
            instrument.options(category, method)  # raises a ValueError naming the instrument and what it does declare

def build_controller(stage: str, lenses: str, imaging: str, stem4d: str = None, stemsi: str = None) -> MicroscopeController:
    """
    Build a MicroscopeController from user dropdown values and make their own controller.
    """
    instrument = SESSION.instrument
    # build in this order as 4D-STEM and SI controllers need earlier controllers
    selection = {"stage": stage, "lenses": lenses, "imaging": imaging, "4dstem_detector": stem4d, "stemsi_detector": stemsi}
    # Validation is mainly for either a user not selecting all required options in the dropdown or 
    # for when a controller is built externally in a standalone script 
    _validate_selection(instrument, selection) # make sure names are valid

    # build each controller via its Method, passing the category, the instrument settings,
    # the controllers already built (4D-STEM/SI need the imaging one) and all available Methods (Merlin currently needs for pyjem
    # column setting to get metadata).
    built = {}
    for category, method in selection.items():
        built[category] = None if method is None else SESSION.methods[method].build(category, instrument, built, SESSION.methods)

    # This now groups up all the selected controllers for usage via MicroscopeController.stage.func etc!
    return MicroscopeController(
        stage=built["stage"],
        lenses=built["lenses"],
        imaging=built["imaging"],
        stem4d_detector=built["4dstem_detector"],
        stemsi=built["stemsi_detector"],
    )