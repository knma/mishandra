import sys, os
import numpy as np
import trimesh
from types import SimpleNamespace as SN
from collections.abc import Iterable

from ..mishandra import module, MishandraSession as session
from ..proto import base_pb2
from ..proto.byte_field_descriptions import *
from ..utils import encode_image, decode_image


def make_proto(meshes, name=None, frame=None, description=None, params=None, verbose=False):
  params = SN(
    no_points = False,
    no_faces = False,
    no_colors = False,
    no_normals = False,
    no_uv = False,
    no_image = False,
    image_format = '.jpg',
    jpeg_quality = 95,
    png_compression = 3
  ) if params is None else SN(**params)

  proto = session.make_proto(name=name, frame=frame, description=description)

  if not isinstance(meshes, Iterable) or not len(meshes):
    meshes = [meshes]

  bfd = byte_field_descriptions

  scene = proto.scenes.add()

  for i, mesh in enumerate(meshes):
    obj = scene.objects.add()
    obj.name = f"object_{str(i).zfill(3)}"

    if not params.no_faces:
      obj.mesh.faces = mesh.faces.astype(bfd.Mesh.faces.dtype).tobytes()
    if not params.no_points:
      obj.mesh.pointSet.P = mesh.vertices.astype(bfd.PointSet.P.dtype).tobytes()
    if not params.no_normals:
      obj.mesh.pointSet.N = mesh.vertex_normals.astype(bfd.PointSet.N.dtype).tobytes()
    if not params.no_colors:
      colors = getattr(mesh.visual, 'vertex_colors', None)
      if colors is not None:
        obj.mesh.pointSet.Cd = colors[:,:3].astype(bfd.PointSet.Cd.dtype).tobytes()
        obj.mesh.pointSet.Alpha = colors[:,3:].astype(bfd.PointSet.Alpha.dtype).tobytes()
    if not params.no_uv:
      uv = getattr(mesh.visual, 'uv', None)
      if uv is not None:
        uv = np.concatenate([uv, uv*0], axis=1)
        obj.mesh.pointSet.uv = uv.astype(bfd.PointSet.uv.dtype).tobytes()
    if not params.no_image and hasattr(mesh.visual, 'material'):
      texture = getattr(mesh.visual.material, 'image', None)
      if texture:
        texture = np.array(texture)[...,::-1]
        encoded = encode_image(
          texture,
          params.image_format,
          params.jpeg_quality,
          params.png_compression
        )
        if encoded is not None:
          image = obj.images.add()
          image.format = params.image_format
          image.width = texture.shape[1]
          image.height = texture.shape[0]
          image.channels = texture.shape[2]
          image.jpeg_quality = params.jpeg_quality
          image.png_compression = params.png_compression
          image.data = encoded

  return proto


def from_proto(proto, params=None, verbose=False):
  params = SN(
    process = False,
  ) if params is None else SN(**params)

  bfd = byte_field_descriptions

  meshes = []
  for scene in proto.scenes:
    for obj in scene.objects:

      if not len(obj.mesh.pointSet.P):
        if verbose:
          print(f"Vertices are missing in object {obj.name}")
        continue
      vertices = np.frombuffer(obj.mesh.pointSet.P, dtype=bfd.PointSet.P.dtype)
      vertices = vertices.reshape(bfd.PointSet.P.shape)

      if not len(obj.mesh.faces):
        if verbose:
          print(f"Faces are missing in object {obj.name}")
        continue
      faces = np.frombuffer(obj.mesh.faces, dtype=bfd.Mesh.faces.dtype)
      faces = faces.reshape(bfd.Mesh.faces.shape)

      vertex_normals = None
      if len(obj.mesh.pointSet.N):
        vertex_normals = np.frombuffer(obj.mesh.pointSet.N, dtype=bfd.PointSet.N.dtype)
        vertex_normals = vertex_normals.reshape(bfd.PointSet.N.shape)

      if len(obj.mesh.pointSet.Cd):
        colors = np.frombuffer(obj.mesh.pointSet.Cd, dtype=bfd.PointSet.Cd.dtype)
        colors = colors.reshape(bfd.PointSet.Cd.shape)
        visual = trimesh.visual.ColorVisuals(vertex_colors=colors)
      elif len(obj.mesh.pointSet.uv):
        image = None
        if len(obj.images):
          image = decode_image(obj.images[0].data, type='pil')
        uv = np.frombuffer(obj.mesh.pointSet.uv, dtype=bfd.PointSet.uv.dtype)
        uv = uv.reshape(bfd.PointSet.uv.shape)
        print(uv.shape)
        print(vertices.shape)
        visual = trimesh.visual.TextureVisuals(uv=uv, image=image)

      meshes.append(trimesh.Trimesh(
        vertices=vertices,
        vertex_normals=vertex_normals,
        faces=faces,
        visual=visual,
        process=params.process
      ))

  return meshes