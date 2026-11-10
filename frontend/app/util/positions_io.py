import os
import glob
from util import data_io

_POSITIONS_META_FILENAME = "position_scans"  # stored as position_scans.json in the experiment folder

def save_positions_meta(folder_path, meta):
    "for convenience, linked to global name so easier to change later"
    data_io.local_store(folder_path, _POSITIONS_META_FILENAME, data=meta, data_type="json")

def _discover_pos_indices(folder_path):
    """Every pos-X folder index that currently exists on disk, sorted ascending"""
    pos_dirs = glob.glob(os.path.join(folder_path, "pos-*"))
    return sorted(
        int(os.path.basename(d).split("-")[1]) for d in pos_dirs if os.path.isdir(d)
    )

def get_latest_pos_index(folder_path):
    """Find the highest pos-X directory index in folder_path, or 0 if none"""
    if not os.path.isdir(folder_path):
        return 0
    return max(_discover_pos_indices(folder_path), default=0)

def get_position_status(folder_path, pos_index):
    """ready/running/done/not_configured for a single position (states must exist in _STATUS_COLOURS etc.), 
    based on its stored pipeline/acquisition state"""
    pos_path = os.path.join(folder_path, f"pos-{pos_index}")
    pipeline_config = data_io.local_retrieve(pos_path, "pipeline-config", data_type="json")
    acq_state = data_io.local_retrieve(pos_path, "long-acquisition-state", data_type="json")

    if acq_state == "Started":
        return "running"
    if acq_state == "Finished":
        return "done"
    if pipeline_config is not None:
        return "ready"
    return "not_configured"

def load_positions_meta(folder_path):
    """Load position_scans.json (run order + included flag per position), checked against the
    pos-x folders that actually exist on disk. Creates/updates the file on disk if it is not matching."""
    existing_indices = _discover_pos_indices(folder_path)
    stored = data_io.local_retrieve(folder_path, _POSITIONS_META_FILENAME, data_type="json")
    stored_positions = stored.get("positions", []) if stored else []

    #double check if they are actually on disk just in case user messes with things/ new pos made but yet to be stored
    positions = [p for p in stored_positions if p["pos_index"] in existing_indices]
    known_indices = {p["pos_index"] for p in positions}

    # append any newly-discovered positions at the end in ascending order
    for idx in existing_indices:
        if idx not in known_indices:
            positions.append({"pos_index": idx, "included": True})

    meta = {"positions": positions}
    if positions != stored_positions: # if mismatch, update positions json
        save_positions_meta(folder_path, meta)
    return meta

def set_position_included(folder_path, pos_index, included):
    # just for updating whether a pos is included or not in the json
    meta = load_positions_meta(folder_path)
    for p in meta["positions"]:
        if p["pos_index"] == pos_index:
            p["included"] = included
            break
    save_positions_meta(folder_path, meta)
    return meta


def move_position(folder_path, pos_index, direction):
    """direction: -1 moves the position earlier in the run order, +1 moves it later"""
    meta = load_positions_meta(folder_path)
    positions = meta["positions"]
    idx = next((i for i, p in enumerate(positions) if p["pos_index"] == pos_index), None)
    if idx is None:
        return meta
    new_idx = idx + direction
    if 0 <= new_idx < len(positions):
        positions[idx], positions[new_idx] = positions[new_idx], positions[idx]
        save_positions_meta(folder_path, meta)
    return meta
