import requests, os, sys
import numpy as np
from StringIO import StringIO
import pickle
from pyquaternion import Quaternion

from ..body_client import BodyClient


class BodyRefiner(object):
  def __init__(self, hou, node, module_node):
    super(BodyRefiner, self).__init__()

    geo = node.geometry()
    self.hou = hou
    self.node = node
    self.module_node = module_node
    
    module = sys.modules[__name__]
    joints_current = getattr(module, 'joints_current', None)
    if joints_current is None:
      joints_current = {}
      setattr(module, 'joints_current', joints_current)
    self.joints_current = joints_current

    def make_subnet():
      container = node.parent().parent()
      adj_nodes = container.children()
      subnet = None
      for adj_node in adj_nodes:
        if adj_node.type().name() == "subnet" and "alc_geo" in adj_node.name():
          subnet = adj_node
          break
      if subnet is None:
        subnet = container.createNode("subnet", "alc_geo")
        # subnet.createNode("")

      module_node_pos = node.parent().position()
      subnet.setPosition((module_node_pos[0], module_node_pos[1]+1))

      # module_node.setInput(0, subnet)
      return subnet
    
    # self.subnet = make_subnet()
    print('BodyRefiner created')

  def set_joints(self, joints):
    joint_nodes = self.module_node.parent().parent().glob("joint*")
    if len(joints.shape) > 2:
      joints = joints[0]
    joints_scene = self.transform_points(joints)
    for joint_node in joint_nodes:
      i = int(joint_node.name()[5:])
      joint = joints_scene[i]
      key_x = self.hou.Keyframe()
      key_x.setFrame(self.frame)
      key_x.setValue(joint[0].item())
      joint_node.parm('tx').setKeyframe(key_x)
      key_y = self.hou.Keyframe()
      key_y.setFrame(self.frame)
      key_y.setValue(joint[1].item())
      joint_node.parm('ty').setKeyframe(key_y)
      key_z = self.hou.Keyframe()
      key_z.setFrame(self.frame)
      key_z.setValue(joint[2].item())
      joint_node.parm('tz').setKeyframe(key_z)
      key_s = self.hou.Keyframe()
      key_s.setFrame(self.frame)
      key_s.setValue(0.5)
      joint_node.parm('scale').setKeyframe(key_s)
    self.module_node.parent().parent().node('opt').setCurrent(False, clear_all_selected=True)
    self.module_node.parent().parent().node('opt').setSelected(False, clear_all_selected=True)

  def get_joints(self):
    # if self.frame in self.joints_current:
    #   return  

    joint_nodes = self.module_node.parent().parent().glob("joint*")
    joints_scene = np.zeros((127, 4), dtype=np.float32)
    for joint_node in joint_nodes:
      i = int(joint_node.name()[5:])
      # if i < 10:
      #   print(i, joint_node.parm('tx').eval())

      joints_scene[i, 0] = joint_node.parm('tx').eval()
      joints_scene[i, 1] = joint_node.parm('ty').eval()
      joints_scene[i, 2] = joint_node.parm('tz').eval()
      joints_scene[i, 3] = joint_node.parm('scale').eval()

    joints = self.transform_points(joints_scene[...,:3], inv=True)
    scales = joints_scene[...,3:4]
    return joints, scales

  def transform_points(self, points, inv=False):
    homo_coord = np.ones((points.shape[0], 1), dtype=np.float32)
    points = np.concatenate([points, homo_coord], axis=1)

    shift = np.array([self.cx, self.cy, 0], dtype=np.float32)

    m_x180 = Quaternion(axis=[1, 0, 0], angle=np.pi).transformation_matrix
    m = m_x180
    m[:3, 3] = shift
    if inv:
      m = np.linalg.inv(m)

    points = np.dot(points, m.T)[...,:3]
    return points

  def update(self):
    self.frame = int(self.hou.frame())
    self.url = self.module_node.evalParm("body_refiner_url")
    self.target_dir = self.module_node.evalParm("ref_seq_dir")
    self.timeout = self.module_node.evalParm("timeout")
    self.seq_name = self.module_node.evalParm("source_params")
    self.optimize = self.module_node.evalParm("optimize")
    self.update_joints = self.module_node.evalParm("update_joints")
    self.make_request = self.module_node.evalParm("make_request")
    self.rate = self.module_node.evalParm("rate")
    self.rate_hands = self.module_node.evalParm("rate_hands")
    self.num_iters = self.module_node.evalParm("num_iters")
    self.num_iters_hands = self.module_node.evalParm("num_iters_hands")
    self.lambda_verts = self.module_node.evalParm("lambda_verts")
    self.lambda_zero_prior_hands = self.module_node.evalParm("lambda_zero_prior_hands")
    self.cx = self.module_node.parent().node('opt').evalParm("cx")
    self.cy = self.module_node.parent().node('opt').evalParm("cy")

    joint_nodes = self.module_node.parent().parent().glob("joint*")
    if self.make_request:
      self.request()
    
    for joint_node in joint_nodes:
      scale = joint_node.parm('scale').eval()
      dcolor = (0,0,1) if scale < 0.5001 else (0,1,0)
      joint_node.parm('dcolorr').set(dcolor[0])
      joint_node.parm('dcolorg').set(dcolor[1])
      joint_node.parm('dcolorb').set(dcolor[2])

  def request(self):
    if self.url is None or len(self.url) < 1:
      return
      
    try:
      data = np.random.randn(2, 4)

      joints = 0
      scales = 0
      if self.optimize:
        joints, scales = self.get_joints()
        # scales[scales<0.5001] = 0

      buf = StringIO()
      np.savez_compressed(
        buf,
        data=data,
        frame=self.frame,
        seq_name=self.seq_name,
        optimize=self.optimize,
        joints=joints,
        scales=scales,
        rate=self.rate,
        rate_hands=self.rate_hands,
        num_iters=self.num_iters,
        num_iters_hands=self.num_iters_hands,
        lambda_verts=self.lambda_verts,
        lambda_zero_prior_hands=self.lambda_zero_prior_hands
      )
      buf.seek(0)
      res = requests.post(url=self.url,   
                          data=buf,
                          headers={'Content-Type': 'application/octet-stream'},
                          timeout=self.timeout)
      if not os.path.isdir(self.target_dir):
        os.mkdir(self.target_dir)

      fname = str(self.frame).zfill(8) + '.mi'
      fpath = os.path.join(self.target_dir, fname)

      buf_all = StringIO(res.content)
      buf_all.seek(0)
      res_all = pickle.load(buf_all)

      if self.update_joints:
        self.set_joints(res_all['joints'])

      with open(fpath, 'wb') as f:
          f.write(res_all['geo'].getvalue())
      
    except Exception as e:
      print(e)

  # def make_joint_nodes(self):
  #   control_nodes = self.subnet.children()
  #   for control_node in control_nodes:
  #     if control_node.type().name() == "subnet" and "alc_geo" in adj_node.name():
  #       subnet = adj_node
  #       break
  #   if subnet is None:
  #     subnet = container.createNode("subnet", "alc_geo")
