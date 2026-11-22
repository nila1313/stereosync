"""Find the frame offset between two cameras from their ChArUco board detections."""

__version__ = "0.1.0"

from .detections_io import load_corners_by_frame
from .pairing import build_synchronized_pairs
from .segments import build_sync_segments
from .windowed import search_windowed_offsets

__all__ = [
    "__version__",
    "load_corners_by_frame",
    "search_windowed_offsets",
    "build_sync_segments",
    "build_synchronized_pairs",
]
