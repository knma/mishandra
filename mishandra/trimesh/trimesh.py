import sys, os
import glob
import numpy as np
import trimesh
from types import SimpleNamespace as SN
from collections.abc import Iterable

from ..mishandra import module, MishandraSession as session
from ..proto import base_pb2
from ..proto.field_descriptions import *
from ..utils.image import encode_image, decode_image


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
  ) if params is None else params
  if type(params) is dict:
    params = SN(**params)

  proto = session.make_proto(name=name, frame=frame, description=description)

  if not isinstance(meshes, Iterable):
    meshes = [meshes]

  if not all([type(mesh) is trimesh.Trimesh for mesh in meshes]):
    raise Exception("Wrong meshes input. Trimesh instances were expected") 

  fd = field_descriptions

  scene = proto.scenes.add()

  for i, mesh in enumerate(meshes):
    obj = scene.objects.add()
    obj.name = f"object_from_timesh_{str(i).zfill(3)}"

    if not params.no_faces:
      obj.mesh.faces = mesh.faces.astype(fd.Mesh.faces.dtype).tobytes()
    if not params.no_points:
      obj.mesh.pointSet.P = mesh.vertices.astype(fd.PointSet.P.dtype).tobytes()
    if not params.no_normals:
      obj.mesh.pointSet.N = mesh.vertex_normals.astype(fd.PointSet.N.dtype).tobytes()
    if not params.no_colors:
      colors = getattr(mesh.visual, 'vertex_colors', None)
      if colors is not None:
        obj.mesh.pointSet.Cd = colors[:,:3].astype(fd.PointSet.Cd.dtype).tobytes()
        obj.mesh.pointSet.Alpha = colors[:,3:].astype(fd.PointSet.Alpha.dtype).tobytes()
    if not params.no_uv:
      uv = getattr(mesh.visual, 'uv', None)
      if uv is not None:
        uv = np.concatenate([uv, uv*0], axis=1)
        obj.mesh.pointSet.uv = uv.astype(fd.PointSet.uv.dtype).tobytes()
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
  ) if params is None else params
  if type(params) is dict:
    params = SN(**params)

  fd = field_descriptions

  meshes = []
  for scene in proto.scenes:
    for obj in scene.objects:

      if not len(obj.mesh.pointSet.P):
        if verbose:
          print(f"Vertices are missing in object {obj.name}")
        continue
      vertices = np.frombuffer(obj.mesh.pointSet.P, dtype=fd.PointSet.P.dtype)
      vertices = vertices.reshape(fd.PointSet.P.shape)

      # print(obj.mesh.pointSet.DESCRIPTOR.fields_by_name.items())
      if not len(obj.mesh.faces):
        if verbose:
          print(f"Faces are missing in object {obj.name}")
        continue
      faces = np.frombuffer(obj.mesh.faces, dtype=fd.Mesh.faces.dtype)
      faces = faces.reshape(fd.Mesh.faces.shape)

      vertex_normals = None
      if len(obj.mesh.pointSet.N):
        vertex_normals = np.frombuffer(obj.mesh.pointSet.N, dtype=fd.PointSet.N.dtype)
        vertex_normals = vertex_normals.reshape(fd.PointSet.N.shape)

      if len(obj.mesh.pointSet.Cd):
        colors = np.frombuffer(obj.mesh.pointSet.Cd, dtype=fd.PointSet.Cd.dtype)
        colors = colors.reshape(fd.PointSet.Cd.shape)
        visual = trimesh.visual.ColorVisuals(vertex_colors=colors)
      elif len(obj.mesh.pointSet.uv):
        image = None
        if len(obj.images):
          image = decode_image(obj.images[0].data, type='pil')
        uv = np.frombuffer(obj.mesh.pointSet.uv, dtype=fd.PointSet.uv.dtype)
        uv = uv.reshape(fd.PointSet.uv.shape)
        visual = trimesh.visual.TextureVisuals(uv=uv, image=image)

      meshes.append(trimesh.Trimesh(
        vertices=vertices,
        vertex_normals=vertex_normals,
        faces=faces,
        visual=visual,
        process=params.process
      ))

  return meshes

def from_directory(directory, params=None, verbose=False):
  params = SN(
    mesh_format = '.obj',
    files_number_limit = sys.maxsize
  ) if params is None else params
  if type(params) is dict:
    params = SN(**params)

  pattern = os.path.join(directory, f"*.{params.mesh_format}")
  mesh_paths = sorted(glob.glob(os.path.join(directory, f"*{params.mesh_format}")))

  meshes = []
  for i, mesh_path in enumerate(list(mesh_paths)):
    if i >= params.files_number_limit:
      break
    mesh = trimesh.load(mesh_path, process=False)
    if mesh is not None:
      meshes.append(mesh)

  if verbose:
    print(f"{len(meshes)} meshes loaded ({os.path.basename(mesh_paths[0])}..{os.path.basename(mesh_paths[-1])})")

  return meshes


