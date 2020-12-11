from __future__ import print_function, absolute_import

import sys, os, glob
import numpy as np

if sys.version_info[0] > 3:
  import ffmpeg, cv2
  import subprocess

def make_video(frames, frames_dir=None, size=None, video_path=None, video_bitrate=8e6):
  if video_path is None:
    video_dir = 'mishatemp'
    os.makedirs(video_dir, exist_ok=True)
    video_path = os.path.join(video_dir, 'video.mp4')

  if os.path.isfile(video_path):
      os.remove(video_path)

  if frames_dir is not None:
    frame_paths = list(sorted(glob.glob(os.path.join(frames_dir, '*.*'))))
    first_frame = cv2.imread(frame_paths[0])
  else:
    if not len(frames):
      print('Frames are missing')
      return
    first_frame = frames[0]

  if not isinstance(first_frame, np.ndarray):
    print('Wrong frames type')
    return

  if size is None:
    size = first_frame.shape[1], first_frame.shape[0]

  process = (
    ffmpeg
    .input('pipe:', format='rawvideo', pix_fmt='rgb24', s='{}x{}'.format(*size))
    .output(video_path, pix_fmt='yuv420p', video_bitrate=video_bitrate)
    .overwrite_output()
    .run_async(pipe_stdin=True)
  )

  if frames_dir is not None:
    for frame_path in frame_paths:
      process.stdin.write(cv2.imread(frame_path).astype(np.uint8).tobytes())
  else:
    for frame in frames:
      process.stdin.write(frame.astype(np.uint8).tobytes())

  process.stdin.close()
  process.wait()

  return video_path