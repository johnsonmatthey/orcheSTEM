from fastapi import FastAPI, HTTPException 
import uvicorn
from endpoints import survey, segmentation, cluster, pipeline, gms, analysis
from pathlib import Path
from data_models import schemas
from microscope.core.instrument import list_instruments, load_instrument
from microscope.core.session import SESSION
import json
import logging
from util.logging_setup import set_experiment_log_target

app = FastAPI()

@app.post("/create-experiment")
async def create_experiment(data: schemas.ExperimentRequest): # Change this to use the model
    print(f"this is the folder path {data.folder_path}")
    Path(data.folder_path).mkdir(parents=True, exist_ok=True)
    # Path(data.folder_path, "drift_survey").mkdir(parents=True, exist_ok=True)
    # Path(data.folder_path, "logs").mkdir(parents=True, exist_ok=True) # log actions and scan conditions
    set_experiment_log_target(data.folder_path)
    return {"status": "success"}

# Maps each dropdown category to its possible options.
# Each option has a label, value, and the runtime object to check.
@app.get("/microscope/status")
async def get_microscope_status():
    result = {}
    for category, options in SESSION.options().items():
        available = [
            {"label": opt["label"], "value": opt["value"]}
            for opt in options if opt["exists"]
        ]
        preferred = SESSION.instrument.preferences.get("control", {}).get(category)
        # Only use the preferred value if it's actually available
        default = preferred if any(option["value"] == preferred for option in available) else None
        result[category] = {"options": available, "default": default}
    return result

@app.post("/microscope/config")
async def update_microscope_config(data: schemas.ConfigUpdateRequest):
    """Update the configs given formatting should match the schemas"""
    SESSION.save_startup_default()
    SESSION.instrument.save_preferences(
        data.preferences,
        data.stem4d_settings.model_dump() if data.stem4d_settings else None,
        data.stemsi_settings.model_dump() if data.stemsi_settings else None,
    )
    return {"status": "success"}

def _session_info():
    """
    Possible instrument setup and holders based on the jsons alongside connection results so far
    """
    instruments = []
    for instrument_id in list_instruments():
        try:
            instrument = load_instrument(instrument_id)
        except Exception as e:
            print(f"Skipping instrument '{instrument_id}': {e}")
            continue
        instruments.append({"value": instrument.instrument_id, "label": instrument.display_name, "holders": instrument.holders})
    return {
        "instruments": instruments, # other valid options
        # current settings
        "instrument": SESSION.instrument.instrument_id,
        "holder": SESSION.holder,
        "connections": SESSION.connections,
    }

@app.get("/microscope/session")
async def get_microscope_session():
    return _session_info()

@app.post("/microscope/connect")
def connect_microscope(data: schemas.ConnectRequest):
    """
    Connect to the selected instrument and holder and setup the connections as defined in the json - return what succeeded.
    """
    try:
        SESSION.connect(data.instrument_id, data.holder, attempts=3)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) # for catching errors with incorrect holder and instrument configs due to user error
    return _session_info()

app.include_router(survey.router, prefix="/survey", tags=["Scanning"])
app.include_router(segmentation.router, prefix="/segmentation", tags=["Scanning"])
app.include_router(cluster.router, prefix="/cluster", tags=["Scanning"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["Scanning"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
app.include_router(gms.router, prefix="/gms", tags=["GMS"])
#Filter out polling logs from terminal
class PollFilter(logging.Filter):
    def filter(self, record):
        return "/gms/poll" not in record.getMessage()

if __name__ == "__main__":
    from util.logging_setup import setup_print_logging
    log_path = setup_print_logging(Path(__file__).resolve().parent / "logs")
    print(f"Logging to {log_path}")
    logging.getLogger("uvicorn.access").addFilter(PollFilter())
    uvicorn.run(app, host="0.0.0.0", port=8001, use_colors=False)