from __future__ import print_function, absolute_import

import numpy as np
# from . import base_pb2
from ..utils.text import colored, decorated
from google.protobuf.text_format import MessageToString
from google.protobuf.json_format import MessageToDict

field_descriptions = {
  'PointSet': {
    'P':           {'shape':(-1,3),       'dtype': (np.float32, np.float16)},
    'N':           {'shape':(-1,3),       'dtype': (np.float32, np.float16)},
    'v':           {'shape':(-1,3),       'dtype': (np.float32, np.float16)},
    'T':           {'shape':(-1,3),       'dtype': (np.float32, np.float16)},
    'orient':      {'shape':(-1,4),       'dtype': (np.float32, np.float16)},
    'scale':       {'shape':(-1,3),       'dtype': (np.float32, np.float16)},
    'pscale':      {'shape':(-1,1),       'dtype': (np.float32, np.float16)},
    'Cd':          {'shape':(-1,3),       'dtype': (np.float32, np.uint8)},
    'Alpha':       {'shape':(-1,1),       'dtype': (np.float32, np.uint8)},
    'Cs':          {'shape':(-1,3),       'dtype': (np.float32, np.uint8)},
    'Cr':          {'shape':(-1,3),       'dtype': (np.float32, np.uint8)},
    'Ct':          {'shape':(-1,3),       'dtype': (np.float32, np.uint8)},
    'Ce':          {'shape':(-1,3),       'dtype': (np.float32, np.uint8)},
    'rough':       {'shape':(-1,1),       'dtype': (np.float32, np.uint8)},
    'fresnel':     {'shape':(-1,1),       'dtype': (np.float32, np.uint8)},
    'shadow':      {'shape':(-1,1),       'dtype': (np.float32, np.uint8)},
    'groups':      {'shape':(-1,-1),      'dtype': (np.uint16, np.uint8)},
    'data':        {'shape':(-1),         'dtype': (np.uint8, np.uint8)},
  },
  'PrimitiveSet': {
    'Cd':          {'shape':(-1,-1,3),    'dtype': (np.float32, np.uint8)},
    'Alpha':       {'shape':(-1,-1),      'dtype': (np.float32, np.uint8)},
    'faces':       {'shape':(-1,-1),      'dtype': (np.uint32, np.uint16)},
    'uv':          {'shape':(-1,-1,-1,2), 'dtype': (np.float32, np.float16)},
    'N':           {'shape':(-1,-1,3),    'dtype': (np.float32, np.float16)},
    'groups':      {'shape':(-1,-1),      'dtype': (np.uint16, np.uint8)},
  },
  'Transform': {
    'T':           {'shape':(3,),         'dtype': (np.float32, np.float16)},
    'Q':           {'shape':(4,),         'dtype': (np.float32, np.float16)},
    'scale':       {'shape':(3,),         'dtype': (np.float32, np.float16)}
  },
  'Camera': {
    'intrinsic':   {'shape':(3,3),        'dtype': (np.float32, np.uint8)},
    'distCoeffs':  {'shape':(8,),         'dtype': (np.float32, np.uint8)}
  },
  'Image': {
    'data':        {'shape':(-1),         'dtype': (np.uint8, np.uint8)}
  },
  'ImageRaw': {
    'data':        {'shape':(-1),         'dtype': (np.uint8, np.uint8)}
  },
  'AudioChannelRaw': {
    'data':        {'shape':(-1),         'dtype': (np.uint8, np.uint8)}
  },
  'Object': {
    'data':        {'shape':(-1),         'dtype': (np.uint8, np.uint8)}
  }
}

def get_field_shape(object_name, field_name, shape_modifier=None):
  shape = field_descriptions[object_name][field_name]['shape']
  if shape_modifier is not None:
    shape = list(shape)
    for i in range(len(shape_modifier)):
      shape[i] = shape_modifier[i]
  return tuple(shape)

def get_field_dtype(object_name, field_name, low_precision=False):
  return field_descriptions[object_name][field_name]['dtype'][1 if low_precision else 0]

for item in field_descriptions.values():
  for attrib in item.values():
    attrib['dtype'] = tuple([dt(1).dtype.newbyteorder('<') for dt in attrib['dtype']])

field_descriptions_full_name = {}
for field_name, field in field_descriptions.items():
  for attrib_name, attrib_desc in field.items():
    field_descriptions_full_name[field_name + "." + attrib_name] = attrib_desc

def print_fields(obj, repeated_fields_limit=10):
  if obj is None:
    print("Object is None")
    return
  print(decorated.bold(obj.DESCRIPTOR.full_name))
  context = {'bin_fields_size_total': 0}

  is_bytes = lambda v: str(type(v)).find("bytes") != -1

  def walk(obj, context=context, depth=1, index=-1, display=True, stop_display_depth=-1, lowp_fields=[]):
    index_prefix = "{}:".format(colored.blue(str(index))) if index >=0 else ""
    offset = colored.none("|  "*depth)
    if 'lowPrecisionFields'in obj.DESCRIPTOR.fields_by_name.keys():
      lowp_fields = obj.lowPrecisionFields
    for descriptor in obj.DESCRIPTOR.fields:
      value = getattr(obj, descriptor.name)
      if descriptor.type == descriptor.TYPE_MESSAGE:
        if descriptor.label == descriptor.LABEL_REPEATED:
          if display:
            print(offset + "{}{} ({})".format(index_prefix, decorated.bold(descriptor.name), colored.blue(len(value))))
          ending_printed = False
          for i, v in enumerate(value):
            display_further = display and i < repeated_fields_limit
            if not display_further and stop_display_depth < 0:
              stop_display_depth = depth
            walk(v, context, depth=depth+1, index=i, display=display_further, stop_display_depth=stop_display_depth)
            if not display_further and not ending_printed and depth <= stop_display_depth:
              offset_next = colored.none("|  "*(depth+1))
              print(offset_next + " ")
              print(offset_next + "Only first {} elements of {} {} are displayed".format(repeated_fields_limit, len(value), decorated.bold(descriptor.full_name)))
              print(offset_next + " ")
              ending_printed = True
        else:
          if display:
            print(offset + "{}{}".format(index_prefix, decorated.bold(descriptor.name)))
          walk(value, context, depth=depth+1, display=display, stop_display_depth=stop_display_depth)
      elif descriptor.type == descriptor.TYPE_ENUM:
        enum_name = descriptor.enum_type.values[value].name
        if display:
          print(offset + "{} {}".format(decorated.bold(descriptor.name), enum_name))
      else:
        t = type(value)
        if t in (str, bytes):
          t_is_bytes = descriptor.type == 12
          if t is str and not t_is_bytes:
            if display:
              print(offset + "{}{} ".format(index_prefix, decorated.bold(descriptor.name)) + "'" + value + "'")
          if t_is_bytes and len(value):
            size = len(value) / 2**10
            context['bin_fields_size_total'] += size
            desc = field_descriptions_full_name.get(descriptor.full_name, None)
            details = ""
            if desc:
              dtype = desc['dtype'][1 if descriptor.name in lowp_fields else 0]
              size = colored.red("{:.2f}KB".format(size))
              details = "({}) {} {} {}".format(len(value) // dtype.itemsize, size, dtype, desc['shape'])
            if display:
              print(offset + "{}{} {}".format(index_prefix, decorated.bold(colored.red(descriptor.name)), details))
        else:
          if display:
            print(offset + "{}{} {}".format(index_prefix, decorated.bold(descriptor.name), colored.green(value) if 'frame' in descriptor.name else value))

  walk(obj, context=context)
  total_size = colored.red("{:.2f}".format(context['bin_fields_size_total']))
  print("byte fields total: {}KB".format(total_size))

def mark_cached(obj, name, recursive=True, verbose=False, ctx=None):
  if ctx is None:
    ctx = {'n_cached': 0}
  if not hasattr(obj, 'DESCRIPTOR'):
    return
  for descriptor in obj.DESCRIPTOR.fields:
    if descriptor.full_name == name and 'cachedFields' in obj.DESCRIPTOR.fields_by_name.keys():
      if not descriptor.name in obj.cachedFields:
        obj.cachedFields.extend([descriptor.name])
      ctx['n_cached'] += 1
    if recursive:
      value = getattr(obj, descriptor.name)
      if descriptor.label == descriptor.LABEL_REPEATED:
        for i, v in enumerate(value):
          mark_cached(v, name, recursive, ctx=ctx)
      else:
        mark_cached(value, name, recursive, ctx=ctx)
  if verbose:
    print("{}: {} fields marked as cached".format(name, ctx['n_cached']))

