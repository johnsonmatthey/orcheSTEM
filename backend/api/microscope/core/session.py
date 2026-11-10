import threading
from microscope.core import microscope_config
from microscope.core.instrument import load_instrument
from microscope.methods import METHOD_CLASSES


class MicroscopeSession:
    """
    all live microscope states stored here incl. the shared settings from json and  each hardware method
    with its connections. connect() swaps the setup as needed."""

    def __init__(self, config: dict):
        self.config = config  # shared settings from config.json
        self.methods = {cls.name: cls(config) for cls in METHOD_CLASSES}  # method name -> its live instance, in connection order
        self._lock = threading.Lock() # prevent double trigger as not setup debouncing or disabling for now
        self.instrument = None # The instrument data class containing calibrations etc.
        self.holder = None     # The holder which will be connected to the calibrations/some capabilities
        self.connections = []  # one dict per method the instrument has connected to

    def connect(self, instrument_id, holder, attempts=None) -> list[dict]:
        """
        Based on the active instrument and holder (defaults from pref), setup the connections.
        attempts is passed to each method, which may retry that many times. None means keep retrying if possible.
        """
        instrument = load_instrument(instrument_id)

        if holder not in instrument.holders:
            raise ValueError(f"Holder '{holder}' is not one of {instrument.holders} for {instrument_id}")
        declared = set()
        for category, methods in instrument.hardware.items():
            for name in methods:
                if name not in self.methods:
                    raise ValueError(f"Instrument '{instrument_id}' declares '{name}' but only {sorted(self.methods)} are available")
                if category not in self.methods[name].categories:
                    raise ValueError(f"{self.methods[name].label} does not implement '{category}' (declared by '{instrument_id}'), only {sorted(self.methods[name].categories)}")
                declared.add(name)
        # checks any required instrument settings exist as defined in the given hardware Method.validate, else does nothing
        for name in declared:
            self.methods[name].validate(instrument)

        with self._lock: # lock thread to make sure not triggering in parallel.
            results = []
            for name, method in self.methods.items(): # connect to each defined hardware Method, disconnecting the rest
                if name in declared:
                    results.append(method.connect(instrument, attempts))
                else:
                    method.disconnect()

            self.instrument, self.holder, self.connections = instrument, holder, results
        return results

    def options(self):
        """Build the microscope options dict from the methods the active instrument declares under each category."""
        options = {}
        # grab from the Instrument dataclass all available methods based on the json per catergory
        for category, methods in self.instrument.hardware.items():
            options[category] = [
                {"label": self.methods[method].label, "value": method, "exists": self.methods[method].available(category)}
                for method in methods # iterate over each method per catergory, check if it is available and return 
            ]
        return options

    def save_startup_default(self):
        """Store the active instrument and holder in config.json so the next start connects to them."""
        microscope_config.save_startup_default(self.instrument.instrument_id, self.holder)


SESSION = MicroscopeSession(microscope_config.load_microscope_config())  # the one global: everything else is reached through it
SESSION.connect(SESSION.config["instrument"], SESSION.config["holder"])
