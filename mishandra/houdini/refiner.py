import requests, os, sys, time
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
    refiner_state = getattr(module, 'refiner_state', None)
    if refiner_state is None:
      refiner_state = {}
      setattr(module, 'refiner_state', refiner_state)
    self.refiner_state = refiner_state

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

  def set_joints(self, joints, joint_nodes, namelen=5):
    if len(joints.shape) > 2:
      joints = joints[0]
    joints_scene = self.transform_points(joints)

    for joint_node in joint_nodes:
      i = int(joint_node.name()[namelen:])
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
      key_s.setValue(0.4)
      joint_node.parm('scale').setKeyframe(key_s)

  def get_joints(self):
    joints_scene = np.zeros((76, 4), dtype=np.float32)
    for joint_node in self.joint_nodes:
      i = int(joint_node.name()[5:])
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
    obj_opt = self.module_node.parent().parent().node('opt')

    self.frame = int(self.hou.frame())
    self.update_joints = self.module_node.evalParm("update_joints")
    if self.update_joints:
      obj_opt = self.module_node.parent().parent().node('opt')
      for part in ['body', 'rhand', 'lhand', 'lleg', 'rleg']:
        key = self.hou.Keyframe()
        key.setFrame(self.frame)
        key.setValue(1)
        obj_opt.parm(part + '_verts').setKeyframe(key)
    
    self.url = self.module_node.evalParm("body_refiner_url")
    self.target_dir = self.module_node.evalParm("ref_seq_dir")
    self.timeout = self.module_node.evalParm("timeout")
    self.source_sequence = self.module_node.evalParm("source_params")
    self.ref_sequence = self.module_node.parent().node('opt').geometry().stringAttribValue("ref_sequence")
    self.optimize = self.module_node.evalParm("optimize")
    self.optimize_hands = self.module_node.evalParm("optimize_hands")
    self.make_request = self.module_node.evalParm("make_request")
    self.rate = self.module_node.evalParm("rate")
    self.rate_hands = self.module_node.evalParm("rate_hands")
    self.num_iters = self.module_node.evalParm("num_iters")
    self.num_iters_hands = self.module_node.evalParm("num_iters_hands")
    self.lambda_verts = self.module_node.evalParm("lambda_verts")
    self.lambda_zero_prior_hands = self.module_node.evalParm("lambda_zero_prior_hands")
    self.cx = self.module_node.parent().node('opt').evalParm("cx")
    self.cy = self.module_node.parent().node('opt').evalParm("cy")
    self.set_frame_range = obj_opt.evalParm("set_frame_range")
    self.show_status_dialog = obj_opt.evalParm("show_status_dialog")
    self.save_refined_sequence = obj_opt.evalParm("save_refined_sequence")
    self.fetch_image = obj_opt.evalParm("fetch_image")
    self.offline_after_request = obj_opt.evalParm("offline_after_request")
    self.lhand_verts = obj_opt.evalParm("lhand_verts")
    self.rhand_verts = obj_opt.evalParm("rhand_verts")
    self.lleg_verts = obj_opt.evalParm("lleg_verts")
    self.rleg_verts = obj_opt.evalParm("rleg_verts")
    self.body_verts = obj_opt.evalParm("body_verts")

    self.operation = self.hou.InterruptableOperation("...", long_operation_name="...", open_interrupt_dialog=self.show_status_dialog)
    self.operation.__enter__()

    self.joint_nodes = self.module_node.parent().parent().glob("joint*")
    self.joint_nodes_current = self.module_node.parent().parent().node("jc").glob("jcurrent*")
    self.joint_nodes_source = self.module_node.parent().parent().node("js").glob("jsource*")

    if self.make_request:
      self.request()
      if self.offline_after_request:
        self.go_offline()

    colors_are_set = self.refiner_state.get('colors_are_set', False)
    if not colors_are_set:
      self.refiner_state['colors_are_set'] = True

      for joint_node in self.joint_nodes:
        scale = joint_node.parm('scale').eval()
        dcolor = (0,0,1) if scale < 0.4001 else (0,0,1)
        joint_node.parm('dcolorr').set(dcolor[0])
        joint_node.parm('dcolorg').set(dcolor[1])
        joint_node.parm('dcolorb').set(dcolor[2])

      for joint_node in self.joint_nodes_current:
        scale = joint_node.parm('scale').eval()
        dcolor = (1,1,1)
        joint_node.parm('dcolorr').set(dcolor[0])
        joint_node.parm('dcolorg').set(dcolor[1])
        joint_node.parm('dcolorb').set(dcolor[2])

      for joint_node in self.joint_nodes_source:
        scale = joint_node.parm('scale').eval()
        dcolor = (1,0.5,0.5)
        joint_node.parm('dcolorr').set(dcolor[0])
        joint_node.parm('dcolorg').set(dcolor[1])
        joint_node.parm('dcolorb').set(dcolor[2])

    # self.module_node.parent().parent().node('geo1').setCurrent(True, clear_all_selected=True)
    # self.module_node.parent().parent().node('geo1').setSelected(True, clear_all_selected=True)
    # self.module_node.parent().parent().node('opt').setCurrent(True, clear_all_selected=True)
    # self.module_node.parent().parent().node('opt').setSelected(True, clear_all_selected=True)

    self.operation.__exit__(None, None, None)

  def go_offline(self):
    self.module_node.parent().parent().node('opt').parm('make_request').set(0)
    self.module_node.parent().parent().node('opt').parm('reset_joints').set(0)
    self.module_node.parent().parent().node('opt').parm('optimize').set(0)

  def request(self):
    if self.url is None or len(self.url) < 1:
      return
      
    try:
      joints = 0
      scales = 0
      if self.optimize:
        joints, scales = self.get_joints()

      buf = StringIO()
      np.savez_compressed(
        buf,
        frame=self.frame,
        source_sequence=self.source_sequence,
        ref_sequence=self.ref_sequence,
        optimize=self.optimize,
        optimize_hands=self.optimize_hands,
        save_refined_sequence = self.save_refined_sequence,
        fetch_image = self.fetch_image,
        joints=joints,
        scales=scales,
        rate=self.rate,
        rate_hands=self.rate_hands,
        num_iters=self.num_iters,
        num_iters_hands=self.num_iters_hands,
        lambda_verts=self.lambda_verts,
        lambda_zero_prior_hands=self.lambda_zero_prior_hands,
        lhand_vert_mult = self.lhand_verts,
        rhand_vert_mult = self.rhand_verts,
        lleg_vert_mult = self.lleg_verts,
        rleg_vert_mult = self.rleg_verts,
        body_vert_mult = self.body_verts
      )
      buf.seek(0)
      self.operation.updateLongProgress(0.1, "Waiting for the Server...")
      res = requests.post(url=self.url,   
                          data=buf,
                          headers={'Content-Type': 'application/octet-stream'},
                          timeout=self.timeout)
      if not os.path.isdir(self.target_dir):
        os.mkdir(self.target_dir)

      fname = str(self.frame).zfill(8) + '.mi'
      fpath = os.path.join(self.target_dir, fname)

      if res.status_code is not 200:
        print('Server error')
        return

      buf_all = StringIO(res.content)
      buf_all.seek(0)
      res_all = pickle.load(buf_all)

      if self.set_frame_range:
        num_frames = res_all['num_frames']
        self.hou.playbar.setFrameRange(0, num_frames-1)

      self.operation.updateLongProgress(0.5, "Updating KeyFrames...")

      if self.update_joints:
        self.set_joints(res_all['joints'], self.joint_nodes)
      if not self.optimize:
        if self.module_node.parent().parent().node("js").isDisplayFlagSet():
          self.set_joints(res_all['joints'], self.joint_nodes_source, namelen=7)

      if self.module_node.parent().parent().node("jc").isDisplayFlagSet():
        self.set_joints(res_all['joints'], self.joint_nodes_current, namelen=8)

      self.operation.updateLongProgress(0.8, "Writing geometry...")
      with open(fpath, 'wb') as f:
          f.write(res_all['geo'].getvalue())

      if res_all.get('image', None) is not None:
        self.operation.updateLongProgress(0.8, "Saving image...")
        im_dir = self.module_node.parent().node('opt').geometry().stringAttribValue("ref_im_dir")
        if not os.path.exists(im_dir):
          os.makedirs(im_dir)
        fpath = os.path.join(im_dir, str(self.frame).zfill(8) + '.jpg')
        with open(fpath, 'wb') as f:
            f.write(res_all['image'].getvalue())
      
    except Exception as e:
      print(e)



