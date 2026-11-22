# stereosync

[![tests](https://github.com/nila1313/stereosync/actions/workflows/tests.yml/badge.svg)](https://github.com/nila1313/stereosync/actions/workflows/tests.yml)

stereosync finds the frame offset between two cameras from their ChArUco board detections.

When two cameras are started by hand, the videos do not start at the same moment. For stereo calibration the left
and right frames have to show the same moment, so I wrote this tool to find the offset automatically instead of by hand.

The offset means: **right frame = left frame + offset**, the same as calibcam's `--frames_offsets 0 <offset>`.

## Install

```
git clone https://github.com/nila1313/stereosync
pip install -e stereosync
```

You also need numpy and OpenCV 4.7 or newer. They are not listed in `pyproject.toml` on purpose, so pip does not
replace the versions you already have.

## How to use it

1. Detect the board on every frame of both videos with calibcam (without `--frames_offsets`):

   ```
   python -m calibcam --videos left.MP4 right.MP4 --board board.npy --detection --frames_step 1 --data_path detections/
   ```

2. Run stereosync on the two detection files:

   ```
   stereosync --detections detections/detection_000.yml detections/detection_001.yml --offsets -15 15 --out sync/
   ```

3. Use the result in calibcam. If one offset fits the whole video, stereosync prints it, for example
   `--frames_offsets 0 7`. If the offset changes during the video, it writes two frames lists instead, which you put
   in a calibcam options file:

   ```
   frames_lists:
     - sync/frames_list_000.yml
     - sync/frames_list_001.yml
   ```

Run `stereosync --help` to see all options.

## How it works

The video is split into windows of 100 frames. In each window the tool tries every offset and checks how well the
corners of both cameras fit one stereo geometry. The best offset wins if it is clearly better than the second best.
Windows with the same offset are joined into sections, and windows where it cannot decide are skipped.

The board has to move in the video, otherwise every offset looks the same.

If the video is overexposed or blurry and many windows are skipped, try `--ransac_threshold 3`.

## Tests

```
python -m pytest tests/
```

The tests use two fake cameras with known offsets. I also checked the tool on six of our real recordings, and it
agreed with our stereo calibrations on every one.

## Author

Nila Maitra Chaity ([@nila1313](https://github.com/nila1313))

The sync code first started in [NanoDeepChArUco](https://github.com/nila1313/NanoDeepChArUco).

## License

There is no license yet.
