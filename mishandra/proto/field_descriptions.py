import numpy as np
from types import SimpleNamespace as SN
from . import base_pb2
from ..utils.text import colored, decorated
from google.protobuf.text_format import MessageToString
from google.protobuf.json_format import MessageToDict

field_descriptions = SN(
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

bin_fields_dict = {}
for field_name, field in vars(field_descriptions).items():
  for attrib_name, attrib_desc in vars(field).items():
    bin_fields_dict[attrib_name] = attrib_desc

for item in vars(field_descriptions).values():
  for attrib in vars(item).values():
    attrib.dtype = attrib.dtype(1).dtype.newbyteorder('<')

def print_fields(message, repeated_fields_limit=10):
  print(f"{decorated.bold(message.DESCRIPTOR.full_name)}")
  context = SN(bin_fields_size_total = 0)

  def walk(obj, context=context, depth=1, index=-1, display=True):
    index_prefix = f"{colored.blue(str(index))}:" if index >=0 else ""
    offset = colored.none("|  "*depth)
    for descriptor in obj.DESCRIPTOR.fields:
      value = getattr(obj, descriptor.name)
      if descriptor.type == descriptor.TYPE_MESSAGE:
        if descriptor.label == descriptor.LABEL_REPEATED:
          if display:
            print(offset + f"{index_prefix}{decorated.bold(descriptor.name)} ({colored.blue(len(value))})")
          ending_printed = False
          for i, v in enumerate(value):
            display_further = display and i < repeated_fields_limit
            walk(v, context, depth=depth+1, index=i, display=display_further)
            if not display_further and not ending_printed:
              offset_next = colored.none("|  "*(depth+1))
              print(offset_next + " ")
              print(offset_next + f"Only first {repeated_fields_limit} elements of {decorated.bold(descriptor.full_name)} are displayed")
              print(offset_next + " ")
              ending_printed = True
        else:
          if display:
            print(offset + f"{index_prefix}{decorated.bold(descriptor.name)}")
          walk(value, context, depth=depth+1, display=display)
      elif descriptor.type == descriptor.TYPE_ENUM:
        enum_name = descriptor.enum_type.values[value].name
        if display:
          print(offset + f"{decorated.bold(descriptor.name)} {enum_name}")
      else:
        t = type(value)
        if t in (str, bytes):
          if t is str:
            if display:
              print(offset + f"{index_prefix}{decorated.bold(descriptor.name)} " + "'" + value + "'")
          if t is bytes and len(value):
            size = len(value) / 2**10
            context.bin_fields_size_total += size
            desc = bin_fields_dict.get(descriptor.name, None)
            details = ""
            if desc:
              size = colored.red(f"{size:.2f}KB")
              details = f"({len(value) // desc.dtype.itemsize}) {size} {desc.dtype} {desc.shape}"
            if display:
              print(offset + f"{index_prefix}{decorated.bold(colored.red(descriptor.name))} {details}")
        else:
          if display:
            print(offset + f"{index_prefix}{decorated.bold(descriptor.name)} {colored.green(value) if 'frame' in descriptor.name else value}")

  walk(message, context=context)
  total_size = colored.red(f"{context.bin_fields_size_total:.2f}")
  print(f"byte fields total: {total_size}KB")
