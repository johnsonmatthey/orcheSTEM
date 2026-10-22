from fastapi import APIRouter, BackgroundTasks
import os
import json
import threading
import tempfile
from contextlib import contextmanager
from data_models import schemas
import time

router = APIRouter()
ANALYSIS_JSON_NAME = "scan-results.json" # incase changed later
_FIRST_BATCH_SIZE = 5   # minimum boxes before the very first dispatch
_BATCH_SIZE = 10        # minimum boxes for every subsequent dispatch

# Threadlock to prevent race condition when read/writing the analysis log within this python instance, works fine as both pipeline and analysis are 
# sync tasks in same process
_ANALYSIS_LOCK = threading.Lock()

# Need to do atomic writing as the frontend also reads this file to update frontend
@contextmanager
def open_atomic(filepath, *args, fsync=False, **kwargs):
    # https://stackoverflow.com/questions/2333872/how-to-make-file-creation-an-atomic-operation
    """Open a temporary file that is atomically moved to filepath on exit.

    The temp file is created in the same directory as the target so the
    replace stays within the same filesystem. 

    If os.replace fails (PermissionError when frontend is reading), retry with a delay
    """
    dir_path = os.path.dirname(os.path.abspath(filepath))
    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp', dir=dir_path)
    tf.close()
    try:
        with open(tf.name, *args, **kwargs) as f:
            try:
                yield f
            finally:
                if fsync:
                    f.flush()
                    os.fsync(f.fileno())
        # Retry loop for Windows PermissionError (reader holding the file)
        for attempt in range(10):
            try:
                os.replace(tf.name, filepath)
                break
            except PermissionError:
                if attempt < 9:
                    time.sleep(0.05)
                else:
                    raise
    finally:
        try:
            os.remove(tf.name)
        except OSError as e:
            if e.errno != 2:  # ignore "file not found" error as replace worked and temp is gone
                raise


def _append_analysis_log(folder_path: str, entry: dict): # used in pipeline but placed here to keep it all together
    """Append or update entries in scan-results.json under a lock."""
    analysis_log_path = os.path.join(folder_path, ANALYSIS_JSON_NAME)
    with _ANALYSIS_LOCK:
        if os.path.exists(analysis_log_path):
            with open(analysis_log_path) as f:
                data = json.load(f)
        else:
            data = {}
        data.update(entry)
        with open_atomic(analysis_log_path, 'w') as f:
            json.dump(data, f, indent=2)


def _update_box_status(folder_path: str, idx: int, status: str):
    """Read-modify-write a single box status under a lock."""
    analysis_log_path = os.path.join(folder_path, ANALYSIS_JSON_NAME)
    with _ANALYSIS_LOCK:
        with open(analysis_log_path) as f:
            data = json.load(f)
        entry = data.get(str(idx))
        if entry is not None:
            entry["analysis_status"] = status
                # Write atomically via tempfiles to prevent json corruption if frontend and backend write at same time
        with open_atomic(analysis_log_path, 'w') as f:
            json.dump(data, f, indent=2)


def analysis_task_a(folder_path: str, box_indices: list):
    """Run Task A analysis for a batch of boxes.
    On success each box transitions: running-a → pending-b (ready for Task B).
    """
    analysis_log_path = os.path.join(folder_path, ANALYSIS_JSON_NAME)
    with _ANALYSIS_LOCK:
        with open(analysis_log_path) as f:
            data = json.load(f)
        entries = {idx: data[str(idx)] for idx in box_indices if str(idx) in data}

    # Per-box write on completion so the frontend sees live progress
    for idx in box_indices:
        entry = entries.get(idx)
        if entry is None:
            print(f"[analysis_a] box {idx} not found, skipping")
            continue
        try:
            ###############################################add stuff here
            #`entry` has box_index, box_id, bbox, drift_vector, timestamp.
            time.sleep(5)
            # ----------------------------------
            _update_box_status(folder_path, idx, "pending-b")  # ready for Task B
            print(f"task A analysis on box {idx} completed")

        except Exception as e:
            print(f"task A analysis on box {idx} failed: {e}")
            _update_box_status(folder_path, idx, "failed")


def analysis_task_b(folder_path: str, box_indices: list):
    """Run Task B analysis for boxes that completed Task A (status: pending-b).
    On success each box transitions: running-b → complete.
    """
    analysis_log_path = os.path.join(folder_path, ANALYSIS_JSON_NAME)
    with _ANALYSIS_LOCK:
        with open(analysis_log_path) as f:
            data = json.load(f)
        entries = {idx: data[str(idx)] for idx in box_indices if str(idx) in data}

    # Per-box write on completion so the frontend sees live progress
    for idx in box_indices:
        entry = entries.get(idx)
        if entry is None:
            print(f"[analysis_b] box {idx} not found, skipping")
            continue
        try:
            ###############################################add stuff here
            #`entry` has box_index, box_id, bbox, drift_vector, timestamp, and analysis_status from Task A.
            time.sleep(10)
            # ----------------------------------
            _update_box_status(folder_path, idx, "complete")
            print(f"task B analysis on box {idx} completed")

        except Exception as e:
            print(f"task B analysis on box {idx} failed: {e}")
            _update_box_status(folder_path, idx, "failed")


@router.post("/run-analysis")
async def run_analysis(req: schemas.AnalysisRequest, background_tasks: BackgroundTasks):
    analysis_log_path = os.path.join(req.folder_path, ANALYSIS_JSON_NAME)
    pending_a = []
    pending_b = []
    analysis_type = ""

    with _ANALYSIS_LOCK:
        # this all done in lock as can still have race conditions if not claimed immediately
        with open(analysis_log_path) as f:
            data = json.load(f)
        analysis_type = data.get("analysis_type", "")

        if analysis_type == "autoptych":
            pipeline_complete = data.get("pipeline_complete", False)

            # Batching A logic
            all_pending_a = [idx for idx in req.box_indices if data.get(str(idx), {}).get("analysis_status") == "pending-a"]
            num_dispatched_a = data.get("analysis_a_dispatched_count", 0) # number of a processing runs
            threshold_a = _FIRST_BATCH_SIZE if num_dispatched_a == 0 else _BATCH_SIZE
            if len(all_pending_a) >= threshold_a:
                pending_a = all_pending_a[:threshold_a]
            elif pipeline_complete and all_pending_a:
                #final batch that is smaller than thresh given pipeline done
                pending_a = all_pending_a

            # Now B
            all_pending_b = [idx for idx in req.box_indices if data.get(str(idx), {}).get("analysis_status") == "pending-b"]
            num_dispatched_b = data.get("analysis_b_dispatched_count", 0) # number of b processing runs
            threshold_b = _FIRST_BATCH_SIZE if num_dispatched_b == 0 else _BATCH_SIZE
            if len(all_pending_b) >= threshold_b:
                pending_b = all_pending_b[:threshold_b]
            elif pipeline_complete and all_pending_b:
                #final batch that is smaller than thresh given pipeline done
                pending_b = all_pending_b

            # write updated tags to show it is running
            for idx in pending_a:
                data[str(idx)]["analysis_status"] = "running-a"
            for idx in pending_b:
                data[str(idx)]["analysis_status"] = "running-b"

            if pending_a:
                data["analysis_a_dispatched_count"] = num_dispatched_a + len(pending_a)
            if pending_b:
                data["analysis_b_dispatched_count"] = num_dispatched_b + len(pending_b)
            if pending_a or pending_b:
                with open_atomic(analysis_log_path, 'w') as f:
                    json.dump(data, f, indent=2)

        if analysis_type == "manual":
            # For manual, we just mark the boxes as complete immediately
            for idx in req.box_indices:
                if str(idx) in data:
                    data[str(idx)]["analysis_status"] = "complete"
            with open_atomic(analysis_log_path, 'w') as f:
                json.dump(data, f, indent=2)
            return {"status": "manual analysis marked complete", "box_indices": req.box_indices}
        
    if analysis_type == "autoptych":
        if pending_a:
            background_tasks.add_task(analysis_task_a, req.folder_path, pending_a)
        if pending_b:
            background_tasks.add_task(analysis_task_b, req.folder_path, pending_b)
        return {"status": "analysis queued", "pending_a": pending_a, "pending_b": pending_b}

    #other methods

    return {"status": "no analysis dispatched", "analysis_type": analysis_type}
