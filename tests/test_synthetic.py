"""
Synthetic test: two pinhole cameras about 3 cm apart watch a moving
6x6 corner board. The right video is shifted by a known number of
frames, and stereosync must find that shift.

Run with:  python -m pytest tests/
"""

import numpy as np
import pytest
import yaml
from calibcamlib import Detections

from stereosync.__main__ import main

K = np.array([[800.0, 0, 960], [0, 800.0, 540], [0, 0, 1]])
WIDTH, HEIGHT = 1920, 1080
N_FRAMES = 600


def rotation(rx, ry, rz):
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    rot_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    rot_y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rot_z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rot_z @ rot_y @ rot_x


# 6x6 inner corners, 3 cm squares, board centred at its origin
grid = np.stack(np.meshgrid(np.arange(6), np.arange(6)), -1).reshape(-1, 2) * 0.03
BOARD = np.c_[grid - grid.mean(0), np.zeros(len(grid))]

# right camera: 3 cm to the side, turned 15 degree
R_RIGHT = rotation(0, np.deg2rad(15), 0)
T_RIGHT = np.array([-0.03, 0.0, 0.0])


def board_points_at(time):
    """World coordinates of the corners at a moment in time (moves smoothly)."""
    rot = rotation(0.4 * np.sin(time / 23), 0.5 * np.sin(time / 31), 0.3 * np.sin(time / 17))
    pos = np.array([0.15 * np.sin(time / 19), 0.08 * np.sin(time / 13), 0.55 + 0.1 * np.sin(time / 29)])
    return BOARD @ rot.T + pos


def project(points, rot, trans, rng):
    cam = points @ rot.T + trans
    uv = cam @ K.T
    uv = uv[:, :2] / uv[:, 2:]
    uv += rng.normal(0, 0.3, uv.shape)
    inside = (cam[:, 2] > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < WIDTH) & (uv[:, 1] >= 0) & (uv[:, 1] < HEIGHT)
    uv[~inside] = np.nan
    return uv


def write_detections(path, corners_per_frame):
    coords = np.array(corners_per_frame, dtype=np.float32)[None]
    Detections({
        "marker_coords": coords,
        "marker_ids": np.arange(coords.shape[2]),
        "detection_idxs": np.arange(coords.shape[1]),
        "frame_idxs": np.arange(coords.shape[1])[None],
    }).to_file([path])


def make_recording(tmp_path, right_time_of_frame):
    """right_time_of_frame(r) = the moment shown in right frame r."""
    rng = np.random.default_rng(0)
    left = [project(board_points_at(t), np.eye(3), np.zeros(3), rng) for t in range(N_FRAMES)]
    right = [project(board_points_at(right_time_of_frame(r)), R_RIGHT, T_RIGHT, rng) for r in range(N_FRAMES)]
    left_path, right_path = tmp_path / "left.yml", tmp_path / "right.yml"
    write_detections(left_path, left)
    write_detections(right_path, right)
    return str(left_path), str(right_path)


def read_segments(out_dir):
    with open(out_dir / "sync_segments.yml") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("true_offset", [0, 1, 7, -6])
def test_constant_offset(tmp_path, true_offset, capsys):
    # right frame = left frame + offset shows the same moment
    left, right = make_recording(tmp_path, lambda r: r - true_offset)
    out = tmp_path / "out"

    assert main(["--detections", left, right, "--offsets", "-10", "10", "--out", str(out)]) == 0

    segments = read_segments(out)
    assert segments, "no section found"
    assert {s["offset"] for s in segments} == {true_offset}
    assert f"--frames_offsets 0 {true_offset}" in capsys.readouterr().out


def test_offset_changes_during_recording(tmp_path):
    # +1 for left frames 0 to 299, then +2 from left frame 300 on
    left, right = make_recording(tmp_path, lambda r: r - 1 if r <= 300 else r - 2)
    out = tmp_path / "out"

    assert main(["--detections", left, right, "--offsets", "-5", "5", "--out", str(out)]) == 0

    segments = read_segments(out)
    assert [s["offset"] for s in segments] == [1, 2]

    with open(out / "frames_list_000.yml") as f:
        left_list = yaml.safe_load(f)["frames_list"]
    with open(out / "frames_list_001.yml") as f:
        right_list = yaml.safe_load(f)["frames_list"]

    pairs = dict(zip(left_list, right_list))
    assert pairs[100] == 101
    assert pairs[400] == 402
