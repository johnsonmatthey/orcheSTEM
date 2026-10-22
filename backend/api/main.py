from fastapi import FastAPI
import uvicorn
from endpoints import survey, segmentation, cluster, pipeline, gms, analysis
from pathlib import Path
from data_models import schemas
from microscope.microscope_config import MICROSCOPE_CONFIG, CONFIG_PATH, get_microscope_options
import json
import logging

app = FastAPI()

@app.post("/create-experiment")
async def create_experiment(data: schemas.ExperimentRequest): # Change this to use the model
    print(f"this is the folder path {data.folder_path}")
    Path(data.folder_path).mkdir(parents=True, exist_ok=True)
    # Path(data.folder_path, "drift_survey").mkdir(parents=True, exist_ok=True)
    # Path(data.folder_path, "logs").mkdir(parents=True, exist_ok=True) # log actions and scan conditions
    return {"status": "success"}

# Maps each dropdown category to its possible options.
# Each option has a label, value, and the runtime object to check.
@app.get("/microscope/status")
async def get_microscope_status():
    result = {}
    for category, options in get_microscope_options().items():
        available = [
            {"label": opt["label"], "value": opt["value"]}
            for opt in options if opt["exists"]
        ]
        preferred = MICROSCOPE_CONFIG.get("preferences", {}).get("control", {}).get(category)
        # Only use the preferred value if it's actually available
        default = preferred if any(option["value"] == preferred for option in available) else None
        result[category] = {"options": available, "default": default}
    return result

@app.post("/microscope/config")
async def update_microscope_config(data: schemas.ConfigUpdateRequest):
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    # ensure preferences and control keys exist before updating to new preferences
    config.setdefault("preferences", {})["control"] = data.preferences
    if data.stem4d_settings is not None:
        # If stem4d_settings is provided, do the same
        config.setdefault("preferences", {}).setdefault("4dstem", {}).update(data.stem4d_settings)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    return {"status": "success"}

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
    logging.getLogger("uvicorn.access").addFilter(PollFilter())
    uvicorn.run(app, host="0.0.0.0", port=8001)