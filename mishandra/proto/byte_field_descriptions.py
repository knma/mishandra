import numpy as np
from types import SimpleNamespace as SN
from . import base_pb2

byte_field_descriptions = SN(
  PointSet = SN(
    P =           SN(shape=(-1,3), dtype=np.float32),
    N =           SN(shape=(-1,3), dtype=np.float32),
    v =           SN(shape=(-1,3), dtype=np.float32),
    scale =       SN(shape=(-1,3), dtype=np.float32),
    Cd =          SN(shape=(-1,3), dtype=np.float32),
    Alpha =       SN(shape=(-1,1), dtype=np.float32),
    Cs =          SN(shape=(-1,3), dtype=np.float32),
    Cr =          SN(shape=(-1,3), dtype=np.float32),
    Ct =          SN(shape=(-1,3), dtype=np.float32),
    Ce =          SN(shape=(-1,3), dtype=np.float32),
    rough =       SN(shape=(-1,1), dtype=np.float32),
    fresnel =     SN(shape=(-1,1), dtype=np.float32),
    shadow =      SN(shape=(-1,1), dtype=np.float32),
    uv =          SN(shape=(-1,4), dtype=np.float32),
    group =       SN(shape=(-1,1), dtype=np.uint16)
  ),
  Transform = SN(
    T =           SN(shape=(3,), dtype=np.float32),
    Q =           SN(shape=(4,), dtype=np.float32)
  ),
  Camera = SN(
    intrinsic =   SN(shape=(3,3), dtype=np.float32),
    distCoeffs =  SN(shape=(8,), dtype=np.float32)
  ),
  Mesh = SN(
    faces =       SN(shape=(-1,3), dtype=np.float32)
  ),
)

for item in vars(byte_field_descriptions).values():
  for attrib in vars(item).values():
    print(attrib.dtype)
    attrib.dtype = attrib.dtype(1).dtype.newbyteorder('<')
