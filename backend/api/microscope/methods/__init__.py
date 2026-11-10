from microscope.methods.pyjem.method import PyJEMMethod
from microscope.methods.qd_scanengine.method import QDScanEngineMethod
from microscope.methods.merlin.method import MerlinMethod
from microscope.methods.gatan.method import GatanMethod

#define hardware methods in order of attempted connection here after importing 
METHOD_CLASSES = (PyJEMMethod, QDScanEngineMethod, MerlinMethod, GatanMethod)
