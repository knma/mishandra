from __future__ import print_function, absolute_import

import sys, os
import glob
import numpy as np
import collections
collections_abc = getattr(collections, 'abc', collections)

from ..mishandra import MishandraSession
from ..proto import base_pb2
from ..proto.field_descriptions import *
from ..utils.image import encode_image, decode_image

attribute_names = {
  "misha_point_P",
  "misha_point_N",
  "misha_point_v",
  "misha_point_T",
  "misha_point_orient",
  "misha_point_scale",
  "misha_point_pscale",
  "misha_point_Cd",
  "misha_point_Alpha",
  "misha_point_Cs",
  "misha_point_Cr",
  "misha_point_Ct",
  "misha_point_Ce",
  "misha_point_rough",
  "misha_point_fresnel",
  "misha_point_shadow",
  "misha_point_groups",
  "misha_point_groupNames",
  "misha_prim_Cd",
  "misha_prim_Alpha",
  "misha_prim_faces",
  "misha_prim_uv",
  "misha_prim_N",
  "misha_prim_groups",
  "misha_prim_groupNames",
  "misha_obj_name",
  "misha_obj_text",
}

def pack(attributes, id, cfg=None, verbose=False, is_master=False, master_pack=None):
  _cfg = {
    'image_format': '.jpg',
    'jpeg_quality': 95,
    'png_compression': 3,
    'use_raw_image': False,
    'low_precision_fields': [],
    'ignore_fields': [],
  }
  if cfg is not None:
    _cfg.update(cfg)

  if not (
    isinstance(attributes, collections_abc.Iterable)
    and isinstance(attributes[0], collections_abc.Iterable)
    and isinstance(attributes[0][0], collections_abc.Iterable)
  ):
    print("attributes must be a nested list of depth 3 ['''FrameSets'''['''Frames'''['''Objects''']]]")
    print("e.g. [[[attributes, attributes]]] -- 1 frameset of 1 frame of 2 objects")
    print("e.g. [[[attributes], [attributes]]] -- 1 frameset of 2 frames of 1 object")
    print("e.g. [[[attributes]], [[attributes]]] -- 2 framesets of 1 frame of 1 object")

  pack = base_pb2.FrameSet()
  pack.id = id
  pack.version = MishandraSession.version
  pack.is_master = is_master

  use_master = master_pack is not None    
  def not_cached(master_field_parent, field_name):
    return not field_name in master_field_parent.cachedFields

  lowp_fields = _cfg['low_precision_fields']
  def get_field_dtype_with_precision(object_name, field_name):
    is_lowp = "{}.{}".format(object_name, field_name) in lowp_fields
    return get_field_dtype(object_name, field_name, is_lowp)

  def dump_lowp_fields(obj):
    for lowp_field in lowp_fields:
      object_name, field_name = lowp_field.split('.')
      if obj.DESCRIPTOR.full_name == object_name:
        obj.lowPrecisionFields.append(field_name)

  ignored_fields = _cfg['ignore_fields']
  def is_not_ignored(object_name, field_name):
    return not "{}.{}".format(object_name, field_name) in ignored_fields

  for fs_i, frameset_attributes in enumerate(attributes):
    frameset = pack.frameSets.add()
    frameset.id = fs_i
    frameset.version = MishandraSession.version
    frameset.is_master = is_master

    if use_master:
      frameset_master = master_pack.frameSets[fs_i]

    for f_i, frame_attributes in enumerate(frameset_attributes):
      frame = frameset.frames.add()
      frame.id = f_i

      if use_master:
        frame_master = frameset_master.frames[f_i]

      for o_i, obj_attributes in enumerate(frame_attributes):
        obj = frame.objects.add()
        obj.id = o_i
        geo = obj.geometry.add()

        point_attribs = {k.replace("misha_point_", ""): v for k, v in obj_attributes.items() if "misha_point_" in k}
        prim_attribs = {k.replace("misha_prim_", ""): v for k, v in obj_attributes.items() if "misha_prim_" in k}
        obj_attribs = {k.replace("misha_obj_", ""): v for k, v in obj_attributes.items() if "misha_obj_" in k}

        if use_master:
          obj_master = frame_master.objects[o_i]
          geo_master = obj_master.geometry[0]

        # ****** Object ******

        # Name
        name = obj_attribs.get('name', None)
        if name is not None and (not use_master or not_cached(obj_master, 'name')):
          obj.name = name

        # Text
        text = obj_attribs.get('text', None)
        if text is not None and (not use_master or not_cached(obj_master, 'text')):
          obj.text = text

        # ****** PrimitiveSet ******
        if not use_master or not_cached(geo_master, 'primitiveSet'):
          dump_lowp_fields(geo.primitiveSet)
          geo.primitiveSet.type = base_pb2.PrimitiveSet.POLYGON
          geo.primitiveSet.nPV = prim_attribs['nPV'] # n vertices per primitive
          geo.primitiveSet.nUV = 1 # 1 UV set

          # Faces
          faces = prim_attribs.get('faces', None)
          if faces is not None and (not use_master or not_cached(geo_master.primitiveSet, 'faces')):
            geo.primitiveSet.faces = faces.astype(get_field_dtype_with_precision('PrimitiveSet', 'faces')).tobytes()

          # UV
          uv = prim_attribs.get('uv', None)
          if uv is not None and (not use_master or not_cached(geo_master.primitiveSet, 'uv')):
            geo.primitiveSet.uv = uv.astype(get_field_dtype_with_precision('PrimitiveSet', 'uv')).tobytes()

          # Vertex normals
          N = prim_attribs.get('N', None)
          if N is not None and (not use_master or not_cached(geo_master.primitiveSet, 'N')):
            geo.primitiveSet.N = N.astype(get_field_dtype_with_precision('PrimitiveSet', 'N')).tobytes()

          # Vertex colors
          Cd = prim_attribs.get('Cd', None)
          if Cd is not None and (not use_master or not_cached(geo_master.primitiveSet, 'Cd')):
            geo.primitiveSet.Cd = Cd.astype(get_field_dtype_with_precision('PrimitiveSet', 'Cd')).tobytes()

          # Vertex alpha
          Alpha = prim_attribs.get('Alpha', None)
          if Alpha is not None and (not use_master or not_cached(geo_master.primitiveSet, 'Alpha')):
            geo.primitiveSet.Alpha = Alpha.astype(get_field_dtype_with_precision('PrimitiveSet', 'Alpha')).tobytes()

          # GroupNames
          groupNames = prim_attribs.get('groupNames', None)
          if groupNames is not None and (not use_master or not_cached(geo_master.primitiveSet, 'groupNames')):
            geo.primitiveSet.groupNames.extend(groupNames)

          # Groups
          groups = prim_attribs.get('groups', None)
          if groups is not None and (not use_master or not_cached(geo_master.primitiveSet, 'groups')):
            geo.primitiveSet.groups = groups.astype(get_field_dtype_with_precision('PrimitiveSet', 'groups')).tobytes()


        # ****** PointSet ******
        if not use_master or not_cached(geo_master, 'pointSet'):
          dump_lowp_fields(geo.pointSet)

          # Points
          P = point_attribs.get('P', None)
          if P is not None and (not use_master or not_cached(geo_master.pointSet, 'P')):
            geo.pointSet.P = P.astype(get_field_dtype_with_precision('PointSet', 'P')).tobytes()

          # Normals
          N = point_attribs.get('N', None)
          if N is not None and (not use_master or not_cached(geo_master.pointSet, 'N')):
            geo.pointSet.N = N.astype(get_field_dtype_with_precision('PointSet', 'N')).tobytes()

          # Velocity
          v = point_attribs.get('v', None)
          if v is not None and (not use_master or not_cached(geo_master.pointSet, 'v')):
            geo.pointSet.v = v.astype(get_field_dtype_with_precision('PointSet', 'v')).tobytes()

          # Tangent
          T = point_attribs.get('T', None)
          if T is not None and (not use_master or not_cached(geo_master.pointSet, 'T')):
            geo.pointSet.T = T.astype(get_field_dtype_with_precision('PointSet', 'T')).tobytes()

          # Orientation
          orient = point_attribs.get('orient', None)
          if orient is not None and (not use_master or not_cached(geo_master.pointSet, 'orient')):
            geo.pointSet.orient = orient.astype(get_field_dtype_with_precision('PointSet', 'orient')).tobytes()

          # Scale
          scale = point_attribs.get('scale', None)
          if scale is not None and (not use_master or not_cached(geo_master.pointSet, 'scale')):
            geo.pointSet.scale = scale.astype(get_field_dtype_with_precision('PointSet', 'scale')).tobytes()

          # Uniform Scale
          pscale = point_attribs.get('pscale', None)
          if pscale is not None and (not use_master or not_cached(geo_master.pointSet, 'pscale')):
            geo.pointSet.pscale = pscale.astype(get_field_dtype_with_precision('PointSet', 'pscale')).tobytes()

          # Point Color
          Cd = point_attribs.get('Cd', None)
          if Cd is not None and (not use_master or not_cached(geo_master.pointSet, 'Cd')):
            geo.pointSet.Cd = Cd.astype(get_field_dtype_with_precision('PointSet', 'Cd')).tobytes()

          # Alpha
          Alpha = point_attribs.get('Alpha', None)
          if Alpha is not None and (not use_master or not_cached(geo_master.pointSet, 'Alpha')):
            geo.pointSet.Alpha = Alpha.astype(get_field_dtype_with_precision('PointSet', 'Alpha')).tobytes()

          # Specular Color
          Cs = point_attribs.get('Cs', None)
          if Cs is not None and (not use_master or not_cached(geo_master.pointSet, 'Cs')):
            geo.pointSet.Cs = Cs.astype(get_field_dtype_with_precision('PointSet', 'Cs')).tobytes()

          # Reflect Color
          Cr = point_attribs.get('Cr', None)
          if Cr is not None and (not use_master or not_cached(geo_master.pointSet, 'Cr')):
            geo.pointSet.Cr = Cr.astype(get_field_dtype_with_precision('PointSet', 'Cr')).tobytes()

          # Transmit Color
          Ct = point_attribs.get('Ct', None)
          if Ct is not None and (not use_master or not_cached(geo_master.pointSet, 'Ct')):
            geo.pointSet.Ct = Ct.astype(get_field_dtype_with_precision('PointSet', 'Ct')).tobytes()

          # Emissive Color
          Ce = point_attribs.get('Ce', None)
          if Ce is not None and (not use_master or not_cached(geo_master.pointSet, 'Ce')):
            geo.pointSet.Ce = Ce.astype(get_field_dtype_with_precision('PointSet', 'Ce')).tobytes()

          # Roughness
          rough = point_attribs.get('rough', None)
          if rough is not None and (not use_master or not_cached(geo_master.pointSet, 'rough')):
            geo.pointSet.rough = rough.astype(get_field_dtype_with_precision('PointSet', 'rough')).tobytes()

          # Fresnel
          fresnel = point_attribs.get('fresnel', None)
          if fresnel is not None and (not use_master or not_cached(geo_master.pointSet, 'fresnel')):
            geo.pointSet.fresnel = fresnel.astype(get_field_dtype_with_precision('PointSet', 'fresnel')).tobytes()

          # Shadow
          shadow = point_attribs.get('shadow', None)
          if shadow is not None and (not use_master or not_cached(geo_master.pointSet, 'shadow')):
            geo.pointSet.shadow = shadow.astype(get_field_dtype_with_precision('PointSet', 'shadow')).tobytes()

          # GroupNames
          groupNames = point_attribs.get('groupNames', None)
          if groupNames is not None and (not use_master or not_cached(geo_master.pointSet, 'groupNames')):
            geo.pointSet.groupNames.extend(groupNames)

          # Groups
          groups = point_attribs.get('groups', None)
          if groups is not None and (not use_master or not_cached(geo_master.pointSet, 'groups')):
            geo.pointSet.groups = groups.astype(get_field_dtype_with_precision('PointSet', 'groups')).tobytes()

  return pack

def unpack(pack, cfg=None, verbose=False, master_pack=None, flatten=False):
  _cfg = {
    'process': False,
  }
  if cfg is not None:
    _cfg.update(cfg)

  meshes = []

  use_master = master_pack is not None    
  def is_cached(master_field_parent, field_name):
    return field_name in master_field_parent.cachedFields

  framesets_attrib = []
  for fs_i, frameset in enumerate(pack.frameSets):

    if use_master:
      frameset_master = master_pack.frameSets[fs_i]

    frames_attrib = []
    for f_i, frame in enumerate(frameset.frames):

      if use_master:
        frame_master = frameset_master.frames[f_i]

      object_attrib = []
      for o_i, obj in enumerate(frame.objects):

        for g_i, geo in enumerate(obj.geometry):
          if g_i > 0:
            break

          attrib = {}

          if use_master:
            obj_master = frame_master.objects[o_i]
            geo_master = obj_master.geometry[g_i]

          # ****** Object ******
          obj_attrib = {
            'text': obj.text,
            'name': obj.name
          }

          # ****** PrimitiveSet ******
          prim_attrib = {
            'nPV': geo.primitiveSet.nPV,
            'nUV': geo.primitiveSet.nUV,
            'groupNames': []
          }

          if use_master and is_cached(geo_master, 'primitiveSet'):
            geo.primitiveSet.CopyFrom(geo_master.primitiveSet)

          prim_lowp_fields = geo.primitiveSet.lowPrecisionFields

          nUV = geo.primitiveSet.nUV
          nPV = geo.primitiveSet.nPV
          nGroups = len(geo.primitiveSet.groupNames)

          # Faces
          if use_master and is_cached(geo_master.primitiveSet, 'faces'):
            geo.primitiveSet.faces = geo_master.primitiveSet.faces
          if len(geo.primitiveSet.faces):
            faces = np.frombuffer(geo.primitiveSet.faces, dtype=get_field_dtype('PrimitiveSet','faces', 'faces' in prim_lowp_fields))
            prim_attrib['faces'] = faces.reshape(get_field_shape('PrimitiveSet','faces', (-1,nPV)))

          # Vertex Color
          if use_master and is_cached(geo_master.primitiveSet, 'Cd'):
            geo.primitiveSet.Cd = geo_master.primitiveSet.Cd
          if len(geo.primitiveSet.Cd):
            Cd = np.frombuffer(geo.primitiveSet.Cd, dtype=get_field_dtype('PrimitiveSet','Cd', 'Cd' in prim_lowp_fields))
            prim_attrib['Cd'] = Cd.reshape(get_field_shape('PrimitiveSet','Cd', (-1,nPV)))

          # Alpha
          if use_master and is_cached(geo_master.primitiveSet, 'Alpha'):
            geo.primitiveSet.Alpha = geo_master.primitiveSet.Alpha
          if len(geo.primitiveSet.Alpha):
            Alpha = np.frombuffer(geo.primitiveSet.Alpha, dtype=get_field_dtype('PrimitiveSet','Alpha', 'Alpha' in prim_lowp_fields))
            prim_attrib['Alpha'] = Alpha.reshape(get_field_shape('PrimitiveSet','Alpha', (-1,nPV)))

          # UV
          if use_master and is_cached(geo_master.primitiveSet, 'uv'):
            geo.primitiveSet.uv = geo_master.primitiveSet.uv
          if len(geo.primitiveSet.uv):
            uv = np.frombuffer(geo.primitiveSet.uv, dtype=get_field_dtype('PrimitiveSet','uv', 'uv' in prim_lowp_fields))
            prim_attrib['uv'] = uv.reshape(get_field_shape('PrimitiveSet','uv', (nUV,-1,nPV)))

          # Normals
          if use_master and is_cached(geo_master.primitiveSet, 'N'):
            geo.primitiveSet.N = geo_master.primitiveSet.N
          if len(geo.primitiveSet.N):
            N = np.frombuffer(geo.primitiveSet.N, dtype=get_field_dtype('PrimitiveSet','N', 'N' in prim_lowp_fields))
            prim_attrib['N'] = N.reshape(get_field_shape('PrimitiveSet','N', (-1,nPV)))

          # Groups
          if use_master and is_cached(geo_master.primitiveSet, 'groups'):
            geo.primitiveSet.groups = geo_master.primitiveSet.groups
          if len(geo.primitiveSet.groups):
            groups = np.frombuffer(geo.primitiveSet.groups, dtype=get_field_dtype('PrimitiveSet','groups', 'groups' in prim_lowp_fields))
            prim_attrib['groups'] = groups.reshape(get_field_shape('PrimitiveSet','groups', (-1,nGroups)))

          # GroupsNames
          if use_master and is_cached(geo_master.primitiveSet, 'groupNames'):
            geo.primitiveSet.groupNames = geo_master.primitiveSet.groupNames
          if len(geo.primitiveSet.groupNames):
            groupNames = geo.primitiveSet.groupNames
            prim_attrib['groupNames'].extend(groupNames)

          # ****** PointSet ******
          point_attrib = {
            'groupNames': []
          }

          nGroups = len(geo.pointSet.groupNames)

          if use_master and is_cached(geo_master, 'pointSet'):
            geo.pointSet.CopyFrom(geo_master.pointSet)

          point_lowp_fields = geo.pointSet.lowPrecisionFields

          # Positions
          if use_master and is_cached(geo_master.pointSet, 'P'):
            geo.pointSet.P = geo_master.pointSet.P
          if len(geo.pointSet.P):
            P = np.frombuffer(geo.pointSet.P, dtype=get_field_dtype('PointSet','P', 'P' in point_lowp_fields))
            point_attrib['P'] = P.reshape(get_field_shape('PointSet','P'))

          # Normals
          if use_master and is_cached(geo_master.pointSet, 'N'):
            geo.pointSet.N = geo_master.pointSet.N
          if len(geo.pointSet.N):
            N = np.frombuffer(geo.pointSet.N, dtype=get_field_dtype('PointSet','N', 'N' in point_lowp_fields))
            point_attrib['N'] = N.reshape(get_field_shape('PointSet','N'))

          # velocity
          if use_master and is_cached(geo_master.pointSet, 'v'):
            geo.pointSet.v = geo_master.pointSet.v
          if len(geo.pointSet.v):
            v = np.frombuffer(geo.pointSet.v, dtype=get_field_dtype('PointSet','v', 'v' in point_lowp_fields))
            point_attrib['v'] = v.reshape(get_field_shape('PointSet','v'))

          # Tangent
          if use_master and is_cached(geo_master.pointSet, 'T'):
            geo.pointSet.T = geo_master.pointSet.T
          if len(geo.pointSet.T):
            T = np.frombuffer(geo.pointSet.T, dtype=get_field_dtype('PointSet','T', 'T' in point_lowp_fields))
            point_attrib['T'] = T.reshape(get_field_shape('PointSet','T'))

          # Orientation
          if use_master and is_cached(geo_master.pointSet, 'orient'):
            geo.pointSet.orient = geo_master.pointSet.orient
          if len(geo.pointSet.orient):
            orient = np.frombuffer(geo.pointSet.orient, dtype=get_field_dtype('PointSet','orient', 'orient' in point_lowp_fields))
            point_attrib['orient'] = orient.reshape(get_field_shape('PointSet','orient'))

          # Scale
          if use_master and is_cached(geo_master.pointSet, 'scale'):
            geo.pointSet.scale = geo_master.pointSet.scale
          if len(geo.pointSet.scale):
            scale = np.frombuffer(geo.pointSet.scale, dtype=get_field_dtype('PointSet','scale', 'scale' in point_lowp_fields))
            point_attrib['scale'] = scale.reshape(get_field_shape('PointSet','scale'))

          # Uniform scale
          if use_master and is_cached(geo_master.pointSet, 'pscale'):
            geo.pointSet.pscale = geo_master.pointSet.pscale
          if len(geo.pointSet.pscale):
            pscale = np.frombuffer(geo.pointSet.pscale, dtype=get_field_dtype('PointSet','pscale', 'pscale' in point_lowp_fields))
            point_attrib['pscale'] = pscale.reshape(get_field_shape('PointSet','pscale'))

          # Point Color
          if use_master and is_cached(geo_master.pointSet, 'Cd'):
            geo.pointSet.Cd = geo_master.pointSet.Cd
          if len(geo.pointSet.Cd):
            Cd = np.frombuffer(geo.pointSet.Cd, dtype=get_field_dtype('PointSet','Cd', 'Cd' in point_lowp_fields))
            point_attrib['Cd'] = Cd.reshape(get_field_shape('PointSet','Cd'))

          # Alpha
          if use_master and is_cached(geo_master.pointSet, 'Alpha'):
            geo.pointSet.Alpha = geo_master.pointSet.Alpha
          if len(geo.pointSet.Alpha):
            Alpha = np.frombuffer(geo.pointSet.Alpha, dtype=get_field_dtype('PointSet','Alpha', 'Alpha' in point_lowp_fields))
            point_attrib['Alpha'] = Alpha.reshape(get_field_shape('PointSet','Alpha'))

          # Specular Color
          if use_master and is_cached(geo_master.pointSet, 'Cs'):
            geo.pointSet.Cs = geo_master.pointSet.Cs
          if len(geo.pointSet.Cs):
            Cs = np.frombuffer(geo.pointSet.Cs, dtype=get_field_dtype('PointSet','Cs', 'Cs' in point_lowp_fields))
            point_attrib['Cs'] = Cs.reshape(get_field_shape('PointSet','Cs'))

          # Reflect Color
          if use_master and is_cached(geo_master.pointSet, 'Cr'):
            geo.pointSet.Cr = geo_master.pointSet.Cr
          if len(geo.pointSet.Cr):
            Cr = np.frombuffer(geo.pointSet.Cr, dtype=get_field_dtype('PointSet','Cr', 'Cr' in point_lowp_fields))
            point_attrib['Cr'] = Cr.reshape(get_field_shape('PointSet','Cr'))

          # Transmit Color
          if use_master and is_cached(geo_master.pointSet, 'Ct'):
            geo.pointSet.Ct = geo_master.pointSet.Ct
          if len(geo.pointSet.Ct):
            Ct = np.frombuffer(geo.pointSet.Ct, dtype=get_field_dtype('PointSet','Ct', 'Ct' in point_lowp_fields))
            point_attrib['Ct'] = Ct.reshape(get_field_shape('PointSet','Ct'))

          # Emissive Color
          if use_master and is_cached(geo_master.pointSet, 'Ce'):
            geo.pointSet.Ce = geo_master.pointSet.Ce
          if len(geo.pointSet.Ce):
            Ce = np.frombuffer(geo.pointSet.Ce, dtype=get_field_dtype('PointSet','Ce', 'Ce' in point_lowp_fields))
            point_attrib['Ce'] = Ce.reshape(get_field_shape('PointSet','Ce'))

          # Roughness
          if use_master and is_cached(geo_master.pointSet, 'rough'):
            geo.pointSet.rough = geo_master.pointSet.rough
          if len(geo.pointSet.rough):
            rough = np.frombuffer(geo.pointSet.rough, dtype=get_field_dtype('PointSet','rough', 'rough' in point_lowp_fields))
            point_attrib['rough'] = rough.reshape(get_field_shape('PointSet','rough'))

          # Fresnel
          if use_master and is_cached(geo_master.pointSet, 'fresnel'):
            geo.pointSet.fresnel = geo_master.pointSet.fresnel
          if len(geo.pointSet.fresnel):
            fresnel = np.frombuffer(geo.pointSet.fresnel, dtype=get_field_dtype('PointSet','fresnel', 'fresnel' in point_lowp_fields))
            point_attrib['fresnel'] = fresnel.reshape(get_field_shape('PointSet','fresnel'))

          # Shadow
          if use_master and is_cached(geo_master.pointSet, 'shadow'):
            geo.pointSet.shadow = geo_master.pointSet.shadow
          if len(geo.pointSet.shadow):
            shadow = np.frombuffer(geo.pointSet.shadow, dtype=get_field_dtype('PointSet','shadow', 'shadow' in point_lowp_fields))
            point_attrib['shadow'] = shadow.reshape(get_field_shape('PointSet','shadow'))

          # Groups
          if use_master and is_cached(geo_master.pointSet, 'groups'):
            geo.pointSet.groups = geo_master.pointSet.groups
          if len(geo.pointSet.groups):
            groups = np.frombuffer(geo.pointSet.groups, dtype=get_field_dtype('PointSet','groups', 'groups' in point_lowp_fields))
            point_attrib['groups'] = groups.reshape(get_field_shape('PointSet','groups', (-1,nGroups)))

          attrib = {
            'obj': obj_attrib,
            'point': point_attrib,
            'prim': prim_attrib
          }

          object_attrib.append(attrib)

      frames_attrib.append(object_attrib)

    framesets_attrib.append(frames_attrib)

  if flatten:
    _flatten = lambda l: sum(map(_flatten,l),[]) if isinstance(l,list) else [l]
    framesets_attrib = _flatten(framesets_attrib)

  return framesets_attrib