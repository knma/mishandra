from __future__ import print_function, absolute_import

import sys, os
import glob
import numpy as np
import trimesh, cv2

import collections
collections_abc = getattr(collections, 'abc', collections)

from ..mishandra import MishandraSession
from ..proto import base_pb2
from ..proto.field_descriptions import *
from ..utils.image import encode_image, decode_image

def pack(meshes, id, cfg=None, verbose=False, is_master=False, master_pack=None):
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
    isinstance(meshes, collections_abc.Iterable)
    and isinstance(meshes[0], collections_abc.Iterable)
    and isinstance(meshes[0][0], collections_abc.Iterable)
  ):
    print("meshes must be a nested list of depth 3 ['''FrameSets'''['''Frames'''['''Objects''']]]")
    print("e.g. [[[mesh, mesh]]] -- 1 frameset of 1 frame of 2 objects")
    print("e.g. [[[mesh], [mesh]]] -- 1 frameset of 2 frames of 1 object")
    print("e.g. [[[mesh]], [[mesh]]] -- 2 framesets of 1 frame of 1 object")

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

  for fs_i, frameset_meshes in enumerate(meshes):
    frameset = pack.frameSets.add()
    frameset.id = fs_i
    frameset.version = MishandraSession.version
    frameset.is_master = is_master

    if use_master:
      frameset_master = master_pack.frameSets[fs_i]

    for f_i, frame_meshes in enumerate(frameset_meshes):
      frame = frameset.frames.add()
      frame.id = f_i

      if use_master:
        frame_master = frameset_master.frames[f_i]

      for o_i, obj_mesh in enumerate(frame_meshes):
        if type(obj_mesh) is not trimesh.Trimesh:
          raise Exception("Wrong meshes input. Trimesh instances were expected") 
        obj = frame.objects.add()
        obj.id = o_i
        geo = obj.geometry.add()

        if use_master:
          obj_master = frame_master.objects[o_i]
          geo_master = obj_master.geometry[0]

        points, indices, inverse_point_indices = np.unique(obj_mesh.vertices, axis=0, return_inverse=True, return_index=True)
        tri_faces_flat = obj_mesh.faces.flatten()

        # ****** PrimitiveSet ******
        if not use_master or not_cached(geo_master, 'primitiveSet'):
          # Faces
          dump_lowp_fields(geo.primitiveSet)
          geo.primitiveSet.type = base_pb2.PrimitiveSet.POLYGON
          geo.primitiveSet.nPV = 3 # 3 vertices per primitive
          geo.primitiveSet.nUV = 1 # 1 UV set
          if not use_master or not_cached(geo_master.primitiveSet, 'faces'):
            faces_flat = inverse_point_indices[tri_faces_flat]
            geo.primitiveSet.faces = faces_flat.astype(get_field_dtype_with_precision('PrimitiveSet','faces')).tobytes()

          # UV
          if not use_master or not_cached(geo_master.primitiveSet, 'uv'):
            uv = getattr(obj_mesh.visual, 'uv', None)
            if uv is not None:
              uv = uv[tri_faces_flat]
              geo.primitiveSet.uv = uv.astype(get_field_dtype_with_precision('PrimitiveSet', 'uv')).tobytes()

          # Vertex normals
          if not use_master or not_cached(geo_master.primitiveSet, 'N'):
            vertex_normals = obj_mesh.vertex_normals[tri_faces_flat]
            geo.primitiveSet.N = vertex_normals.astype(get_field_dtype_with_precision('PrimitiveSet', 'N')).tobytes()

          # Vertex colors
          colors = getattr(obj_mesh.visual, 'vertex_colors', None)
          if colors is not None:
            colors = colors[tri_faces_flat]
            if not use_master or not_cached(geo_master.primitiveSet, 'Cd'):
              geo.primitiveSet.Cd = colors[:,:3].astype(get_field_dtype_with_precision('PrimitiveSet', 'Cd')).tobytes()
            if not use_master or not_cached(geo_master.primitiveSet, 'Alpha'):
              geo.primitiveSet.Alpha = colors[:,3:4].astype(get_field_dtype_with_precision('PrimitiveSet', 'Alpha')).tobytes()

        # ****** PointSet ******
        if not use_master or not_cached(geo_master, 'pointSet'):
          # Points
          dump_lowp_fields(geo.pointSet)
          if not use_master or not_cached(geo_master.pointSet, 'P'):
            geo.pointSet.P = points.astype(get_field_dtype_with_precision('PointSet', 'P')).tobytes()

        # ****** Image ******
        if hasattr(obj_mesh.visual, 'material') and hasattr(obj_mesh.visual.material, 'image'):
          texture = obj_mesh.visual.material.image
          if _cfg['use_raw_image'] and is_not_ignored('Object', 'imagesRaw'):
            if not use_master or not_cached(obj_master, 'imagesRaw'):
              texture = np.array(texture)
              texture = cv2.cvtColor(texture, cv2.COLOR_RGBA2BGRA if texture.shape[2] > 3 else cv2.COLOR_RGB2BGR)
              image = obj.imagesRaw.add()
              image.dtype = str(texture.dtype)
              image.width = texture.shape[1]
              image.height = texture.shape[0]
              image.channels = texture.shape[2]
              image.data = texture.astype(get_field_dtype_with_precision('ImageRaw', 'data')).tobytes()
          elif is_not_ignored('Object', 'images'):
            if not use_master or not_cached(obj_master, 'images'):
              texture = np.array(texture)
              texture = cv2.cvtColor(texture, cv2.COLOR_RGBA2BGRA if texture.shape[2] > 3 else cv2.COLOR_RGB2BGR)
              encoded = encode_image(
                texture,
                _cfg['image_format'],
                _cfg['jpeg_quality'],
                _cfg['png_compression']
              )
              if encoded is not None:
                image = obj.images.add()
                image.format = 1 if 'jpg' in _cfg['image_format'] else 0
                image.width = texture.shape[1]
                image.height = texture.shape[0]
                image.channels = texture.shape[2]
                image.jpeg_quality = _cfg['jpeg_quality']
                image.png_compression = _cfg['png_compression']
                image.data = encoded

  return pack

def unpack(pack, cfg=None, verbose=False, master_pack=None, flatten=False):
  _cfg = {
    'process': False,
    'fix_inversion': False,
    'fix_winding': False
  }
  if cfg is not None:
    _cfg.update(cfg)

  meshes = []

  use_master = master_pack is not None    
  def is_cached(master_field_parent, field_name):
    return field_name in master_field_parent.cachedFields

  pack_meshes = []
  for fs_i, frameset in enumerate(pack.frameSets):

    if use_master:
      frameset_master = master_pack.frameSets[fs_i]

    frameset_meshes = []
    for f_i, frame in enumerate(frameset.frames):

      if use_master:
        frame_master = frameset_master.frames[f_i]

      frame_meshes = []
      for o_i, obj in enumerate(frame.objects):

        for g_i, geo in enumerate(obj.geometry):
          if g_i > 0:
            break

          uv = None
          visual = None
          image = None

          vertex_normals = None
          vertex_colors = None

          if use_master:
            obj_master = frame_master.objects[o_i]
            geo_master = obj_master.geometry[g_i]

          # ****** PrimitiveSet ******
          if use_master and is_cached(geo_master, 'primitiveSet'):
            geo.primitiveSet.CopyFrom(geo_master.primitiveSet)

          prim_lowp_fields = geo.primitiveSet.lowPrecisionFields

          # Faces
          if use_master and is_cached(geo_master.primitiveSet, 'faces'):
            geo.primitiveSet.faces = geo_master.primitiveSet.faces
          faces = np.frombuffer(geo.primitiveSet.faces, dtype=get_field_dtype('PrimitiveSet','faces', 'faces' in prim_lowp_fields))
          faces = faces.reshape(get_field_shape('PrimitiveSet','faces', (-1,3)))
          tri_faces = np.arange(faces.size).reshape((-1,3))

          # UV
          if use_master and is_cached(geo_master.primitiveSet, 'uv'):
            geo.primitiveSet.uv = geo_master.primitiveSet.uv
          if len(geo.primitiveSet.uv):
            uv = np.frombuffer(geo.primitiveSet.uv, dtype=get_field_dtype('PrimitiveSet','uv', 'uv' in prim_lowp_fields))
            uv = uv.reshape(get_field_shape('PrimitiveSet','uv', (1,-1,3)))
            uv = uv.reshape((-1,2))

          # Vertex normals
          if use_master and is_cached(geo_master.primitiveSet, 'N'):
            geo.primitiveSet.N = geo_master.primitiveSet.N
          if len(geo.primitiveSet.N):
            vertex_normals = np.frombuffer(geo.primitiveSet.N, dtype=get_field_dtype('PrimitiveSet','N', 'N' in prim_lowp_fields))
            vertex_normals = vertex_normals.reshape(get_field_shape('PrimitiveSet','N', (-1,3)))

          # Vertex colors
          if use_master and is_cached(geo_master.primitiveSet, 'Cd'):
            geo.primitiveSet.Cd = geo_master.primitiveSet.Cd
          if len(geo.primitiveSet.Cd):
            vertex_colors = np.frombuffer(geo.primitiveSet.Cd, dtype=get_field_dtype('PrimitiveSet', 'Cd', 'Cd' in prim_lowp_fields))
            vertex_colors = vertex_colors.reshape(get_field_shape('PrimitiveSet','Cd', (-1,3)))

          # ****** PointSet ******
          if use_master and is_cached(geo_master, 'PointSet'):
            geo.pointSet.CopyFrom(geo_master.pointSet)

          points_lowp_fields = geo.pointSet.lowPrecisionFields

          # Points
          if use_master and is_cached(geo_master.pointSet, 'P'):
            geo.pointSet.P = geo_master.pointSet.P
          points = np.frombuffer(geo.pointSet.P, dtype=get_field_dtype('PointSet', 'P', 'P' in points_lowp_fields))
          points = points.reshape(get_field_shape('PointSet','P'))
          vertices = points[faces.flatten()]

          # Image
          if use_master and is_cached(obj_master, 'images'):
            obj.images.extend(obj_master.images)
          if len(obj.images):
            image = decode_image(obj.images[0].data, type='pil')
          if use_master and is_cached(obj_master, 'imagesRaw'):
            obj.imagesRaw.extend(obj_master.imagesRaw)
          if len(obj.imagesRaw):
            from PIL import Image
            texture = np.frombuffer(obj.imagesRaw[0].data, dtype=get_field_dtype('ImageRaw', 'data'))
            texture = texture.reshape((obj.imagesRaw[0].height, obj.imagesRaw[0].width, obj.imagesRaw[0].channels))
            texture = cv2.cvtColor(texture, cv2.COLOR_RGBA2BGRA if obj.imagesRaw[0].channels > 3 else cv2.COLOR_RGB2BGR)
            image = Image.fromarray(texture)

          if uv is not None and image is not None:
            visual = trimesh.visual.TextureVisuals(uv=uv, image=image)

          mesh = trimesh.Trimesh(
            vertices=vertices,
            vertex_normals=vertex_normals,
            vertex_colors=vertex_colors,
            faces=tri_faces,
            visual=visual,
            process=_cfg['process']
          )
          if _cfg['fix_winding']:
            trimesh.repair.fix_winding(mesh)
          if _cfg['fix_inversion']:
            trimesh.repair.fix_inversion(mesh)
          frame_meshes.append(mesh)

      frameset_meshes.append(frame_meshes)

    pack_meshes.append(frameset_meshes)

  if flatten:
    def _flatten(val):
      for item in val:
        if isinstance(item, collections_abc.Iterable) and not isinstance(item, str):
          yield from _flatten(item)
        else:
          yield item
    pack_meshes = list(_flatten(pack_meshes))

  return pack_meshes

def from_directory(directory, cfg=None, verbose=False):
  cfg = {
    'mesh_format': '.obj',
    'files_number_limit': sys.maxsize
  } if cfg is None else cfg

  pattern = os.path.join(directory, "*.{}".format(cfg['mesh_format']))
  mesh_paths = sorted(glob.glob(os.path.join(directory, "*{}".format(cfg['mesh_format']))))

  meshes = []
  for i, mesh_path in enumerate(list(mesh_paths)):
    if i >= cfg['files_number_limit']:
      break
    mesh = trimesh.load(mesh_path, process=False)
    if mesh is not None:
      meshes.append(mesh)

  if verbose:
    print("{} meshes loaded ({}..{})".format(len(meshes), os.path.basename(mesh_paths[0]), os.path.basename(mesh_paths[-1])))

  return meshes
