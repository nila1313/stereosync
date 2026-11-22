# stereosync

Finds the frame offset between a left and a right camera from their ChArUco detections.
It works with detections from any detector, as long as they are saved as calibcam detection files.

Offset convention: **right frame = left frame + offset**, the same direction as calibcam's `--frames_offsets 0 <offset>`.

## Install

```
pip install -e path/to/stereosync
```

Needs Python 3.10 or newer, pyyaml and bbo-calibcamlib, plus numpy and OpenCV 4.7 or newer.
numpy and OpenCV are not listed in `pyproject.toml` on purpose, so pip keeps the versions
(and the OpenCV variant, for example opencv-contrib-python-headless) already in your environment.

## Input

Two calibcam detection files (yml or npy), one per camera:

- detected **without** `--frames_offsets`, so the frame numbers are the real video frames
- ideally on **every frame** (frame step 1), because offset +1 needs right frame t+1 next to left frame t

## Run

```
python -m stereosync --detections left.yml right.yml --offsets -10 10 --out results/
```

The tool tries every offset in the range, in windows of 100 frames. For each window it checks
how well the corners seen by both cameras fit one epipolar geometry (fundamental matrix with RANSAC).
Windows with the same offset are joined into sections.

## Output

In the `--out` folder:

- `sync_window_results.yml`: best and second best offset for every window
- `sync_segments.yml`: the stable sections with their offset
- `sync_pairs.yml`: every left frame / right frame pair in a trusted window
- `frames_list_000.yml`, `frames_list_001.yml`: the same pairs as calibcam frames lists

If one offset fits the whole recording, the tool prints the calibcam argument, for example
`--frames_offsets 0 7`. If the offset changes during the recording, use the frames lists in a
calibcam options file:

```
frames_lists:
  - results/frames_list_000.yml
  - results/frames_list_001.yml
```

## Test

```
python -m pytest tests/
```

The tests build two fake cameras about 3 cm apart, shift the right video by a known number of
frames (0, +1, +7, -6, and +1 changing to +2) and check that the tool finds it.

## Origin

The sync code (`epipolar.py`, `windowed.py`, `segments.py`, `pairing.py`, `reporting.py`) comes from
the NanoDeepChArUco branch `pipeline/wide-angle-two-stage-autosync`.
