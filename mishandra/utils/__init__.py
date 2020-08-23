import sys

from .image import encode_image, decode_image
from .video import make_video
from .text import colored

if sys.version_info[0] < 3:
  pass
  # print("mishandra: OffscreenRenderer is not available in current python environment.")
else:
  from .renderer import OffscreenRenderer

pack_file_ext = ".mi"
masterpack_file_ext = ".master.mi"
megapack_file_name = "mega.mi"

def id_to_fname(id, is_master=False, is_mega=False):
  ext = pack_file_ext if not is_master else masterpack_file_ext
  return "{}{}".format(str(int(id)).zfill(8), ext)

def fname_to_id(fname):
  for ext in [masterpack_file_ext, pack_file_ext]:
    if fname.endswith(ext):
      fname = fname[:-len(ext)]
  return int(fname)