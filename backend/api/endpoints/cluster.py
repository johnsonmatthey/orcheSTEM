from fastapi import APIRouter
from data_models import schemas
from util import data_io, watershed as ws
from skimage.measure import label, regionprops
import numpy as np

router = APIRouter()


def _build_tile_entry(tile_id, y0, x0, y1, x1, segmented, object_centroids_map):
    """Build a single tile output dictionary."""
    box_centroid = ((y0 + y1) / 2.0, (x0 + x1) / 2.0)
    patch_segments = segmented[y0:y1, x0:x1]
    unique_ids = np.unique(patch_segments)
    cluster_ids = [int(i) for i in unique_ids if i > 0]
    obj_centroids = [object_centroids_map[cid] for cid in cluster_ids]
    return {
        "id": tile_id,
        "bbox": (int(y0), int(x0), int(y1), int(x1)),
        "centroid": box_centroid,
        "cluster_ids": cluster_ids,
        "object_centroids": obj_centroids,
        "object_count": len(cluster_ids)
    }


def _place_tiles(mask, segmented, props, object_centroids_map, res):
    """Two-phase tile placement: object-centric then gap-filling.

    Phase 1: Uses connected-component labeling on the binary mask to find
             individual blobs, then centers a tile on each blob centroid.
             When the centered position conflicts with an already-placed tile,
             the tile is nudged to the nearest non-overlapping position that
             still contains the blob. Blobs are processed most-isolated-first.
    Phase 2: Non-overlapping grid fills any remaining mask regions.
    Overlap is only permitted at image boundaries.
    """
    img_h, img_w = mask.shape
    occupied = np.zeros((img_h, img_w), dtype=bool)
    placed_rects = []
    final_output = []
    tile_id = 0

    # Detect individual blobs via connected-component labeling on the mask
    # (independent of watershed, which may merge nearby particles)
    labeled_mask = label(mask)
    blob_props = regionprops(labeled_mask)
    centroid_list = [p.centroid for p in blob_props]

    def _find_position(cy, cx):
        """Return the closest non-overlapping tile origin containing (cy, cx)."""
        y0_ideal = max(0, min(int(round(cy - res / 2)), img_h - res))
        x0_ideal = max(0, min(int(round(cx - res / 2)), img_w - res))

        # Best case: centered position is free
        if not occupied[y0_ideal:y0_ideal + res, x0_ideal:x0_ideal + res].any():
            return y0_ideal, x0_ideal

        # Centroid must remain inside the tile → constrain valid origin range
        cy_i, cx_i = int(cy), int(cx)
        y0_lo = max(0, cy_i - res + 1)
        y0_hi = min(cy_i, img_h - res)
        x0_lo = max(0, cx_i - res + 1)
        x0_hi = min(cx_i, img_w - res)

        # Build nudge candidates: positions adjacent to each blocking tile
        candidates = set()
        for ry0, rx0, ry1, rx1 in placed_rects:
            for ny in (ry1, ry0 - res):          # below / above blocking tile
                for nx in (x0_ideal, rx1, rx0 - res):
                    candidates.add((
                        max(y0_lo, min(ny, y0_hi)),
                        max(x0_lo, min(nx, x0_hi)),
                    ))
            for nx in (rx1, rx0 - res):            # right / left of blocking tile
                for ny in (y0_ideal, ry1, ry0 - res):
                    candidates.add((
                        max(y0_lo, min(ny, y0_hi)),
                        max(x0_lo, min(nx, x0_hi)),
                    ))

        best = None
        best_dist = float('inf')
        for ny, nx in candidates:
            if occupied[ny:ny + res, nx:nx + res].any():
                continue
            dist = abs(ny - y0_ideal) + abs(nx - x0_ideal)
            if dist < best_dist:
                best_dist = dist
                best = (ny, nx)

        return best

    # --- Phase 1: Object-centric placement with nudging ---
    # Sort ascending by local density so isolated objects are placed first,
    # maximising the number of uniquely-centred tiles.
    def _nearby_count(idx):
        cy, cx = centroid_list[idx]
        y0 = max(0, min(int(round(cy - res / 2)), img_h - res))
        x0 = max(0, min(int(round(cx - res / 2)), img_w - res))
        return sum(1 for cy2, cx2 in centroid_list
                   if y0 <= cy2 < y0 + res and x0 <= cx2 < x0 + res)

    sorted_indices = sorted(range(len(centroid_list)), key=_nearby_count)

    for idx in sorted_indices:
        cy, cx = centroid_list[idx]

        # Skip if this centroid pixel is already inside a placed tile
        if occupied[min(int(cy), img_h - 1), min(int(cx), img_w - 1)]:
            continue

        pos = _find_position(cy, cx)
        if pos is None:
            continue

        y0, x0 = pos
        y1, x1 = y0 + res, x0 + res
        mask_patch = mask[y0:y1, x0:x1]
        if np.any(mask_patch) and (mask_patch.sum() / mask_patch.size) > 0.005:
            occupied[y0:y1, x0:x1] = True
            placed_rects.append((y0, x0, y1, x1))
            final_output.append(
                _build_tile_entry(tile_id, y0, x0, y1, x1, segmented, object_centroids_map)
            )
            tile_id += 1

    # --- Phase 2: Fill remaining mask regions with non-overlapping grid ---
    y_grid = list(range(0, max(img_h - res + 1, 1), res))
    x_grid = list(range(0, max(img_w - res + 1, 1), res))
    boundary_ys = set()
    boundary_xs = set()

    y_b = max(0, img_h - res)
    if y_b not in set(y_grid):
        y_grid.append(y_b)
        boundary_ys.add(y_b)
    x_b = max(0, img_w - res)
    if x_b not in set(x_grid):
        x_grid.append(x_b)
        boundary_xs.add(x_b)

    for y0 in y_grid:
        for x0 in x_grid:
            y1, x1 = y0 + res, x0 + res
            tile_occ = occupied[y0:y1, x0:x1]
            is_boundary = y0 in boundary_ys or x0 in boundary_xs

            if tile_occ.any():
                if not is_boundary or tile_occ.all():
                    continue

            mask_patch = mask[y0:y1, x0:x1]
            if np.any(mask_patch) and (mask_patch.sum() / mask_patch.size) > 0.005:
                occupied[y0:y1, x0:x1] = True
                final_output.append(
                    _build_tile_entry(tile_id, y0, x0, y1, x1, segmented, object_centroids_map)
                )
                tile_id += 1

    #reorder tiles to do outermost first to avoid skipping due to backlash
    centre_y, centre_x = img_h / 2.0, img_w / 2.0
    final_output.sort(
        key=lambda t: -((t["centroid"][0] - centre_y) ** 2 + (t["centroid"][1] - centre_x) ** 2)
    )
    for i, tile in enumerate(final_output):
        tile["id"] = i

    return final_output


@router.post("/watershed")
async def apply_clustering(req: schemas.ClusterRequest):  
    # must rescale based on full/survey image sizes to give psuedo real units when 
    # displaying coordinatesto user 
    full_image_size = req.full_image_size
    survey_image_size = req.survey_image_size
    scaling_factor = full_image_size//survey_image_size
    print(f"Clustering with scaling factor: {scaling_factor}")  

    # 1. Load Mask and Run Watershed
    mask = data_io.local_retrieve(req.folder_path, 'threshold', data_type='png')
    mask = mask > 0
    # Segmented contains the unique IDs for each particle/cluster
    segmented = ws.watershed(mask, int(req.s_value))
    
    # 2. Pre-calculate Object Centroids for the entire image
    # This allows us to map IDs to specific locations later
    props = regionprops(segmented)
    object_centroids_map = {p.label: p.centroid for p in props}

    # 3. Tile Placement (object-centric + gap-filling, overlap only at boundaries)
    img_h, img_w = mask.shape
    res = int(req.sampling_res//scaling_factor)
    print(f"Clustering with tile size: {int(res*scaling_factor)}")

    final_output = _place_tiles(mask, segmented, props, object_centroids_map, res)

    # 4. Store and Return
    data_io.local_store(req.folder_path, 'coords', data=final_output, data_type='json')
    
    return {
        "status": "success", 
        "tiles_count": len(final_output), 
        "total_clusters_in_image": len(props)
    }
    
    
@router.post("/watershed-offline")
async def apply_clustering_offline(req: schemas.ClusterRequest):  
    # 1. Load Mask and Run Watershed
    mask = data_io.local_retrieve(req.folder_path, 'threshold', data_type='png')
    mask = mask > 0
    # Segmented contains the unique IDs for each particle/cluster
    segmented = ws.watershed(mask, int(req.s_value))
    
    # 2. Pre-calculate Object Centroids for the entire image
    # This allows us to map IDs to specific locations later
    props = regionprops(segmented)
    object_centroids_map = {p.label: p.centroid for p in props}

    # 3. Tile Placement (object-centric + gap-filling, overlap only at boundaries)
    img_h, img_w = mask.shape
    res = int(req.sampling_res)
    print(f"Clustering with tile size: {int(res)}")

    final_output = _place_tiles(mask, segmented, props, object_centroids_map, res)

    # 4. Store and Return
    data_io.local_store(req.folder_path, 'coords', data=final_output, data_type='json')
    
    return {
        "status": "success", 
        "tiles_count": len(final_output), 
        "total_clusters_in_image": len(props)
    }