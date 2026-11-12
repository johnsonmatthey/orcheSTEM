from microscope.core.interfaces import Method
from microscope.methods.gatan.channel import GMSChannel

class GatanMethod(Method):
    """
    Wrapper for GMSChannel. Backend code queues commands on the channel, and DigitalMicrograph fetches them by polling
    GET /gms/poll (FastAPI router in endpoints/gms.py) and posts results to POST /gms/result.
    """
    name = "gatan"
    label = "Gatan"
    categories = {"imaging", "stemsi_detector"}  # stage and 4D-STEM control through GMS are not implemented yet

    def __init__(self, config):
        super().__init__(config)
        self.channel = GMSChannel()  # DigitalMicrograph polls this over the /gms endpoints

    def connect(self, instrument, attempts=None):
        # Just check if DigitalMicrograph polls
        connected, elapsed = self.channel.is_connected()
        message = f"DigitalMicrograph last polled {elapsed:.2f} s ago" if connected else "no poll from DigitalMicrograph"
        return self._result(connected, message)

    def available(self, category):
        return self.channel.is_connected()[0]  # checked live as DigitalMicrograph can start or stop polling at any time

    def build(self, category, instrument, built, methods):
        from microscope.methods.gatan.controllers import GatanImaging, GatanSpectroscopy
        if category == "imaging":
            return GatanImaging(self.channel, signals=instrument.options("imaging", "gatan").get("signals"))
        if category == "stemsi_detector":
            return GatanSpectroscopy(built["imaging"])
        raise ValueError(f"{self.label} cannot build '{category}'")

    def disconnect(self):
        pass
