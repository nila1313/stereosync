from __future__ import annotations

import numpy as np
from calibcamlib import Detections


def load_corners_by_frame(
    detection_file,
    cam_idx: int = 0,
) -> dict[int, dict[int, np.ndarray]]:
    """
    Read a calibcam detection file and return

        video frame number -> {corner id: (x, y)}

    The real video frame number (frame_idxs) is used, not the
    shared detection counter (detection_idxs), because the sync
    search compares left frame t with right frame t + offset.
    The file should therefore be detected without frames_offsets.
    """

    detections = Detections.from_file(detection_file)
    markers = detections.to_array()

    coords = markers["marker_coords"][cam_idx]
    frame_idxs = markers["frame_idxs"][cam_idx]
    marker_ids = markers["marker_ids"]

    corners_by_frame = {}

    for frame_idx, frame_coords in zip(frame_idxs, coords):
        if frame_idx < 0:
            continue

        found = ~np.isnan(frame_coords[:, 0])

        if not np.any(found):
            continue

        corners_by_frame[int(frame_idx)] = {
            int(marker_id): np.asarray(xy, dtype=np.float32).copy()
            for marker_id, xy in zip(marker_ids[found], frame_coords[found])
        }

    return corners_by_frame
