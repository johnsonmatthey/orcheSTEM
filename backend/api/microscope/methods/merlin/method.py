from microscope.core.interfaces import Method
from microscope.methods.merlin.commands import MERLIN_connection
from microscope.methods.qd_scanengine.controllers import QDMerlinDetector


def initialise_merlin_connection(hostname):
    """
    Initialise Merlin connection
    """
    try:
        merlin_conn = MERLIN_connection(hostname=hostname)
        return merlin_conn
    except Exception as e:
        print(f"Merlin initialization failed: {e}")
        print("Running in Offline mode.")
        return None


class MerlinMethod(Method):
    name = "merlin"
    label = "Merlin"
    categories = {"4dstem_detector"}

    def __init__(self, config):
        super().__init__(config)
        self.connection = None
        self._hostname = None  # the hostname the current connection was opened with

    def connect(self, instrument, attempts=None):
        hostname = instrument.connections.get("merlin", {}).get("hostname")
        if not hostname:
            self.disconnect()
            return self._result(False, "no hostname in the instrument's connections")
        if self.connection is None or self._hostname != hostname:
            self.connection = initialise_merlin_connection(hostname=hostname)  # the old connection closes when it is dropped
            self._hostname = hostname
        connected = self.connection is not None
        return self._result(connected, hostname if connected else f"could not reach {hostname}")

    def available(self, category):
        return self.connection is not None

    def build(self, category, instrument, built, methods):
        if category == "4dstem_detector":
            pyjem = methods["pyjem"]  # the 4D-STEM metadata export reads PyJEM's column controllers
            def3, detector3, eos3, lens3, ht3, scan3, gun3, apt3 = pyjem.column
            return QDMerlinDetector(
                built["imaging"], self.connection,
                eos3=eos3, ht3=ht3, scan3=scan3,
                gun3=gun3, def3=def3, lens3=lens3,
                apt3=apt3, stage3=pyjem.stage,
            )
        raise ValueError(f"{self.label} cannot build '{category}'")

    def disconnect(self):
        self.connection = None
        self._hostname = None
