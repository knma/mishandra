import trimesh
import pyrender
from pyrender.constants import RenderFlags
import numpy as np
from types import SimpleNamespace as SN
from collections.abc import Iterable
from scipy.spatial.transform import Rotation


class OffscreenRenderer():
  def __init__(self, size=(512, 512), config=None):
    config = SN(
      ambient_light = (0.25, 0.25, 0.25),
      bg_color = (255, 255, 255)
    ) if config is None else config
    if type(config) is dict:
      config = SN(**config)

    self.renderer = pyrender.OffscreenRenderer(*size)
    self.scene = pyrender.Scene(bg_color=config.bg_color, ambient_light=config.ambient_light)

    camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=size[0] / size[1])
    self.camera_node = self.scene.add(camera, pose=self.make_camera_pose())

    dir_light = pyrender.DirectionalLight(color=np.ones(3), intensity=10.0)
    dir_light_pose = np.eye(4)
    dir_light_pose[:3,:3] = Rotation.from_euler(
      'zyx',
      [0, 10, -30],
      degrees=True
    ).as_matrix()
    self.dir_light_node = self.scene.add(dir_light, pose=dir_light_pose)

    self.persistent = [self.camera_node, self.dir_light_node]

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
        self.scene.add(pyrender.Mesh.from_trimesh(mesh), pose=poses[i])

    except Exception as e:
      print(e)

    return self

  def render(self):
    flags = RenderFlags.SHADOWS_DIRECTIONAL

    color, depth = self.renderer.render(self.scene, flags=flags)
    return color, depth
