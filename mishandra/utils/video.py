import sys, os
import numpy as np
import ffmpeg
import subprocess


def make_video(frames, size=None, video_path=None, video_bitrate=8e6):
  if video_path is None:
    video_dir = 'mishatemp'
    os.makedirs(video_dir, exist_ok=True)
    video_path = os.path.join(video_dir, 'video.mp4')

  if os.path.isfile(video_path):
      os.remove(video_path)

  if not len(frames):
    print('Frames are missing')
    return

  if not isinstance(frames[0], np.ndarray):
    print('Wrong frames type')
    return

  if size is None:
    size = frames[0].shape[1], frames[0].shape[0]

  process = (
    ffmpeg
    .input('pipe:', format='rawvideo', pix_fmt='rgb24', s='{}x{}'.format(*size))
    .output(video_path, pix_fmt='yuv420p', video_bitrate=video_bitrate)
    .overwrite_output()
    .run_async(pipe_stdin=True)
  )

  for frame in frames:
    process.stdin.write(frame.astype(np.uint8).tobytes())

  process.stdin.close()
  process.wait()

  return video_path