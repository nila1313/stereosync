# stereosync

[![tests](https://github.com/nila1313/stereosync/actions/workflows/tests.yml/badge.svg)](https://github.com/nila1313/stereosync/actions/workflows/tests.yml)

stereosync finds the frame offset between two cameras from their ChArUco board detections.

When two cameras are started by hand, the videos do not start at the same moment. For example, left frame 100 can
show the same moment as right frame 107. For stereo calibration we need frames that show the same moment, otherwise
a moving board is in a different place in the two images and the calibration gets worse. I wrote this tool so that
this offset does not have to be found by hand anymore.

It works with detections from any detector, as long as they are saved as calibcam detection files. It also notices
when the offset changes during a video (for example when one camera drops frames), and it skips parts of the video
where it cannot decide, instead of guessing.

The offset always means: **right frame = left frame + offset**. This is the same direction as calibcam's
`--frames_offsets 0 <offset>`.

## Install

```
git clone https://github.com/nila1313/stereosync
pip install -e stereosync
```

You need Python 3.10 or newer, numpy and OpenCV 4.7 or newer.

I did not list numpy and OpenCV in `pyproject.toml` on purpose. If they are listed, pip can replace the versions you
already have (for example `opencv-contrib-python-headless`) and break other packages in the same environment.
If you start with an empty environment, install them first:

```
pip install "numpy<2" opencv-contrib-python-headless
```

## How to use it

First, detect the board on every frame of both videos. calibcam can do only the detection, without calibrating:

```
python -m calibcam --videos left.MP4 right.MP4 --board board.npy --detection --frames_step 1 --data_path detections/
```

Please do not use `--frames_offsets` here, so the frame numbers in the files are the real video frames. Every frame
is best, because to test offset +1 the tool needs right frame t+1 next to left frame t. For long videos you can use
`--frames_start` and `--frames_end` to detect only a part where both cameras see the board.

Then run stereosync on the two detection files:

```
stereosync --detections detections/detection_000.yml detections/detection_001.yml --offsets -15 15 --out sync/
```

`python -m stereosync` works the same way.

This is the output for one of our recordings:

```
left  : 1324 frames with corners (detection_000.yml)
right : 898 frames with corners (detection_001.yml)
offsets tried: -15 to 15

Windows
  255-354: no result
  355-454: offset +7, inlier ratio 0.724, lead 0.135, frame pairs 10
  455-554: offset +7, inlier ratio 0.768, lead 0.107, frame pairs 29
  ...
  1955-2054: offset +7, inlier ratio 0.455, lead 0.190, frame pairs 74
  2055-2154: offset -7, inlier ratio 0.452, lead 0.000, frame pairs 4

Sections
  355-2054: offset +7 (15 windows, mean inlier ratio 0.512)

Reports and frames lists written to sync
  1500 frame pairs in trusted windows

One offset for the whole recording. For calibcam use:
  --frames_offsets 0 7
```

The last window has only 4 frame pairs and no lead over the second best offset, so the tool does not trust it.

If one offset fits the whole video, you can give it to calibcam as printed, for example `--frames_offsets 0 7`.

If the offset changes during the video, stereosync tells you and writes one frames list per camera. Position i in the
left list and position i in the right list show the same moment. calibcam reads these only from an options file:

```
frames_lists:
  - sync/frames_list_000.yml
  - sync/frames_list_001.yml
```

## How it works

1. It reads the corners of both cameras for every video frame (with calibcamlib `Detections`).
2. It splits the video into windows of 100 frames.
3. In each window and for each offset, it pairs left frame t with right frame t + offset and takes the corners both
   cameras see (at least 6 per frame). Then it fits one fundamental matrix with RANSAC. With the right offset, all
   corners fit one stereo geometry. With a wrong offset, the moving board does not fit. The score is the share of
   corners that fit (inlier ratio).
4. A window is trusted when the best offset has an inlier ratio of at least 0.2 and is at least 0.05 ahead of the
   second best.
5. Trusted windows next to each other with the same offset are joined into sections. A section needs at least 2
   windows and cannot have a gap of more than 400 frames.

The board has to move for this to work. If the board is still, every offset looks the same. Windows like that, or
windows with too few frame pairs, show `no result` or are not trusted.

## Output files

Everything is written to the `--out` folder:

| File | What is inside |
|---|---|
| `sync_window_results.yml` | best and second best offset, scores and number of frame pairs for every window |
| `sync_segments.yml` | the sections: start frame, end frame (not included), offset, number of windows, mean inlier ratio |
| `sync_pairs.yml` | every left frame and right frame pair in a trusted window |
| `frames_list_000.yml`, `frames_list_001.yml` | the same pairs as calibcam frames lists |

## Options

| Option | Default | Meaning |
|---|---|---|
| `--detections LEFT RIGHT` | needed | calibcam detection files (yml or npy) |
| `--offsets MIN MAX` | `-10 10` | offsets to try, both ends included |
| `--out` | needed | output folder |
| `--window_size` | `100` | frames per window |
| `--window_step` | same as window size | step between windows |
| `--min_inlier_ratio` | `0.20` | lowest inlier ratio for a trusted window |
| `--min_ratio_gap` | `0.05` | how far the best offset must be ahead of the second best |
| `--min_persistence` | `2` | fewest trusted windows in a section |
| `--max_gap_frames` | `400` | largest gap inside one section |
| `--min_shared` | `6` | fewest corners both cameras must see in a frame |
| `--ransac_threshold` | `1.5` | RANSAC threshold in pixel |
| `--min_frame_pairs` | `4` | fewest frame pairs per window and offset |
| `--list_step` | `1` | use every n-th left frame in the frames lists |

## Using it from Python

```python
from stereosync import (
    load_corners_by_frame,
    search_windowed_offsets,
    build_sync_segments,
)

left = load_corners_by_frame("detection_000.yml")
right = load_corners_by_frame("detection_001.yml")

windows = search_windowed_offsets(left, right, offsets=list(range(-15, 16)), window_size=100)
for section in build_sync_segments(windows):
    print(section.start_frame, section.end_frame - 1, section.offset)
```

`section.end_frame` is not included, so the last frame of a section is `end_frame - 1`.
`load_corners_by_frame` gives `{video frame: {corner id: (x, y)}}`, so you can also pass in corners from somewhere
else in the same form.

## Things I noticed

- Our cameras have wide angle fisheye lenses. The fundamental matrix expects straight epipolar lines, but the tool
  still found the right offsets on these videos. The inlier ratios are just lower than with normal lenses.
- Overexposed or blurry corners also make the inlier ratios lower. If many windows are not trusted, you can try
  `--ransac_threshold 3`.
- The tool only finds whole frames. If the cameras are also shifted by part of a frame, the second best offset is
  usually the neighbouring frame on that side.

## Testing

`tests/test_synthetic.py` makes two fake cameras about 3 cm apart that watch a moving board. The right video is
shifted by a known number of frames (0, +1, +7, -6, and +1 that changes to +2 in the middle), and the test checks that
stereosync finds it.

I also ran it on six of our real stereo recordings. On every one, the offset agreed with a separate check that uses a
known stereo calibration of the cameras and does not fit anything.

To run the tests:

```
pip install pytest
python -m pytest tests/
```

## Background

I first wrote this sync code inside [NanoDeepChArUco](https://github.com/nila1313/NanoDeepChArUco)
(branch `pipeline/wide-angle-two-stage-autosync`). I moved it here as its own small tool, so it can be used with any
detector.

## Author

Nila Maitra Chaity ([@nila1313](https://github.com/nila1313))

## License

There is no license yet. Until I add one, all rights are reserved.
