import os, sys

from .version import __version__
from .mishandra import MishandraSession
from .utils import *

from .houdini import *

if sys.version_info[0] < 3:
  pass
else:
  from .trimesh import *
