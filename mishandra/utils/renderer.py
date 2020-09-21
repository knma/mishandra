from __future__ import print_function, absolute_import

import sys

import trimesh
import pyrender
from pyrender.constants import RenderFlags
import numpy as np
from collections.abc import Iterable
from scipy.spatial.transform import Rotation


class OffscreenRenderer():
  def __init__(self, size=(512, 512), config=None):
    config = {
      'ambient_light': (0.1, 0.1, 0.1),
      'bg_color': (255, 255, 255),
    } if config is None else config

    self.renderer = pyrender.OffscreenRenderer(*size)
    self.scene = pyrender.Scene(bg_color=config['bg_color'], ambient_light=config['ambient_light'])

    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=size[0] / size[1], znear=0.01, zfar=10)
    self.camera_node = self.scene.add(camera, pose=self.make_camera_pose())

    self.dir_light_nodes = []
    n_lights = 10
    for i in range(n_lights):
      dir_light = pyrender.DirectionalLight(color=np.ones(3), intensity=10.0/n_lights)
      dir_light_pose = np.eye(4)
      dir_light_pose[:3,:3] = Rotation.from_euler(
        'zyx',
        [0, i * 360 / n_lights, -30],
        degrees=True
      ).as_matrix()
      dir_light_node = self.scene.add(dir_light, pose=dir_light_pose)
      self.dir_light_nodes.append(dir_light_node)

    self.persistent = [self.camera_node] + self.dir_light_nodes

  def make_camera_pose(self, euler_angles=[0, 10, 0], translation=[0, -0.3, 3], degrees=True):
    """Make a camera matrix. 

    Rotates first, then translates.

    Args:
      euler_angles: XYZ euler angles.
      translation: XYZ translation.
      degrees: If True, the angles are assumed to be in degrees.

    Returns:
      np.ndarray: 4x4 matrix.

    """
    camera_pose_T, camera_pose_R = np.eye(4), np.eye(4)
    camera_pose_T[:3, 3] = np.array(translation)
    camera_pose_R[:3,:3] = Rotation.from_euler('xyz', euler_angles, degrees=degrees).as_matrix()

    return np.dot(camera_pose_R, camera_pose_T)

  def update_camera_pose(self, pose=None):
    if pose is None:
      raise ValueError("Please specify the camera pose")
    self.scene.set_pose(self.camera_node, pose=pose)
    return self

  def update_scene(self, meshes, poses=None):
    try:
      for node in self.scene.get_nodes():
        if node not in self.persistent:
          self.scene.remove_node(node)

      if not isinstance(meshes, Iterable):
        meshes = [meshes]

      if not all([type(mesh) is trimesh.Trimesh for mesh in meshes]):
        raise Exception("Wrong meshes input. Trimesh instances were expected") 

      if poses is None or not isinstance(poses, Iterable) or len(poses) != len(meshes):
        poses = [np.eye(4)] * len(meshes)

      for i, mesh in enumerate(meshes):
        # material = pyrender.material.MetallicRoughnessMaterial(
        #     # alphaMode='BLEND',
        #     baseColorFactor=[0.3, 0.3, 0.3, 1.0],
        #     metallicFactor=0.2,
        #     roughnessFactor=0.8
        # )
        # material = pyrender.material.MetallicRoughnessMaterial(
        #     # alphaMode='BLEND',
        #     baseColorTexture=mesh.visual.material.image
        # )
        material = None
        pr_mesh = pyrender.Mesh.from_trimesh(mesh, material=material)


        self.scene.add(pr_mesh, pose=poses[i])

    except Exception as e:
      print(e)

    return self

  def render(self):
    flags = RenderFlags.SHADOWS_DIRECTIONAL

    color, depth = self.renderer.render(self.scene, flags=flags)
    return color, depth
