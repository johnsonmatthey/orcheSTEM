from functools import wraps

# PyJEM controller clearer names for error message
_CONTROLLER_NAMES = {
    "_stage": "Stage",
    "_current_det": "Detector",
    "_def3": "Deflector",
    "_det3": "Detector",
    "_lens3": "Lens",
    "_eos3": "Electron Optical System 3",
    "_ht3": "High Tension",
    "_scan3": "Scan",
    "_gun3": "Gun",
    "_apt3": "Aperture",
    "_stage3": "Stage",
    "_engine": "Scan engine",
}

def requires_controller(controller_attr, unavailable_return=None):
    """
    Decorator for if unavailable, skip func and return unavailable_return. Mainly for offline testing
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if getattr(self, controller_attr, None) is None:
                name = _CONTROLLER_NAMES.get(controller_attr, controller_attr.removeprefix("_").capitalize())
                print(f"{name} controller not available. Skipping {func.__name__}.")
                return unavailable_return
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
