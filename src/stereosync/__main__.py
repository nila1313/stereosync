"""
Find the frame offset between a left and a right camera from their
calibcam detection files.

Example:
    python -m stereosync --detections left.yml right.yml --offsets -10 10 --out results/

Offset convention: right frame = left frame + offset.
This is the same direction as calibcam's --frames_offsets 0 <offset>.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .detections_io import load_corners_by_frame
from .pairing import build_synchronized_pairs
from .reporting import save_sync_reports
from .segments import build_sync_segments
from .windowed import search_windowed_offsets


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="stereosync",
        description=(
            "Find the frame offset between two cameras from their "
            "ChArUco detections. Right frame = left frame + offset."
        ),
    )
    parser.add_argument(
        "--detections", nargs=2, required=True, metavar=("LEFT", "RIGHT"),
        help="calibcam detection files (yml or npy), detected without frames_offsets, "
             "ideally on every frame.",
    )
    parser.add_argument(
        "--offsets", nargs=2, type=int, default=[-10, 10], metavar=("MIN", "MAX"),
        help="Range of offsets to try, both ends included. Default: -10 10.",
    )
    parser.add_argument("--out", required=True, help="Output folder.")
    parser.add_argument("--window_size", type=int, default=100,
                        help="Frames per window. Default: 100.")
    parser.add_argument("--window_step", type=int, default=None,
                        help="Step between windows. Default: same as window_size.")
    parser.add_argument("--min_inlier_ratio", type=float, default=0.20,
                        help="Minimum epipolar inlier ratio for a trusted window. Default: 0.20.")
    parser.add_argument("--min_ratio_gap", type=float, default=0.05,
                        help="Minimum lead of the best offset over the second best. Default: 0.05.")
    parser.add_argument("--min_persistence", type=int, default=2,
                        help="Minimum trusted windows per section. Default: 2.")
    parser.add_argument("--max_gap_frames", type=int, default=400,
                        help="Largest gap without evidence inside one section. Default: 400.")
    parser.add_argument("--min_shared", type=int, default=6,
                        help="Minimum corners both cameras must see in a frame. Default: 6.")
    parser.add_argument("--ransac_threshold", type=float, default=1.5,
                        help="RANSAC threshold in pixel for the fundamental matrix. Default: 1.5.")
    parser.add_argument("--min_frame_pairs", type=int, default=4,
                        help="Minimum frame pairs per window and offset. Default: 4.")
    parser.add_argument("--list_step", type=int, default=1,
                        help="Use every n-th left frame in the frames_list output. Default: 1.")

    args = parser.parse_args(argv)

    if args.offsets[0] > args.offsets[1]:
        parser.error("--offsets MIN must not be larger than MAX")
    for name in ("window_size", "min_persistence", "list_step"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be greater than zero")
    if args.window_step is not None and args.window_step <= 0:
        parser.error("--window_step must be greater than zero")

    return args


def write_frames_lists(out_dir: Path, pairs) -> list[Path]:
    """
    Write one calibcam frames_list file per camera. Position i in the
    left list and position i in the right list show the same moment.
    """
    lists = [
        [int(pair.left_frame) for pair in pairs],
        [int(pair.right_frame) for pair in pairs],
    ]
    paths = []
    for cam_idx, frames in enumerate(lists):
        path = out_dir / f"frames_list_{cam_idx:03d}.yml"
        with open(path, "w") as f:
            yaml.safe_dump({"frames_list": frames}, f)
        paths.append(path)
    return paths


def main(argv=None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    offsets = list(range(args.offsets[0], args.offsets[1] + 1))

    left = load_corners_by_frame(args.detections[0])
    right = load_corners_by_frame(args.detections[1])

    print(f"left  : {len(left)} frames with corners ({args.detections[0]})")
    print(f"right : {len(right)} frames with corners ({args.detections[1]})")
    print(f"offsets tried: {offsets[0]} to {offsets[-1]}")

    if not left or not right:
        print("No detections in one of the files.", file=sys.stderr)
        return 1

    window_results = search_windowed_offsets(
        left_by_frame=left,
        right_by_frame=right,
        offsets=offsets,
        window_size=args.window_size,
        window_step=args.window_step,
        min_shared_per_frame=args.min_shared,
        ransac_threshold_px=args.ransac_threshold,
        min_frame_pairs=args.min_frame_pairs,
    )

    print()
    print("Windows")
    for result in window_results:
        frames = f"{result.start_frame}-{result.end_frame - 1}"
        if result.best_score is None:
            print(f"  {frames}: no result")
            continue
        print(
            f"  {frames}: offset {result.best_offset:+d}, "
            f"inlier ratio {result.best_score.inlier_ratio:.3f}, "
            f"lead {result.inlier_ratio_gap:.3f}, "
            f"frame pairs {result.best_score.n_frame_pairs}"
        )

    segments = build_sync_segments(
        window_results,
        min_inlier_ratio=args.min_inlier_ratio,
        min_ratio_gap=args.min_ratio_gap,
        min_persistence=args.min_persistence,
        max_gap_frames=args.max_gap_frames,
    )

    print()
    print("Sections")
    if not segments:
        save_sync_reports(out_dir, window_results, [], [])
        print("  No stable section found. Reports written to", out_dir, file=sys.stderr)
        return 1

    for segment in segments:
        print(
            f"  {segment.start_frame}-{segment.end_frame - 1}: "
            f"offset {segment.offset:+d} "
            f"({segment.n_support_windows} windows, "
            f"mean inlier ratio {segment.mean_inlier_ratio:.3f})"
        )

    first_frame = min(left)
    last_frame = max(left)
    left_frames = list(range(first_frame, last_frame + 1, args.list_step))

    pairs = build_synchronized_pairs(
        left_frames=left_frames,
        right_frames=sorted(right),
        segments=segments,
        require_right_available=False,
        window_results=window_results,
        min_inlier_ratio=args.min_inlier_ratio,
        min_ratio_gap=args.min_ratio_gap,
    )

    save_sync_reports(out_dir, window_results, segments, pairs)
    list_paths = write_frames_lists(out_dir, pairs)

    print()
    print(f"Reports and frames lists written to {out_dir}")
    print(f"  {len(pairs)} frame pairs in trusted windows")

    distinct = sorted({segment.offset for segment in segments})
    print()
    if len(distinct) == 1:
        print("One offset for the whole recording. For calibcam use:")
        print(f"  --frames_offsets 0 {distinct[0]}")
    else:
        print("The offset changes during the recording. For calibcam, put this in an options file:")
        print("  frames_lists:")
        for path in list_paths:
            print(f"    - {path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
