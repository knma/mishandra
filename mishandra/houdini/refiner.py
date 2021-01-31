import requests
import numpy as np
from StringIO import StringIO

from ..body_client import BodyClient

class BodyRefiner(object):
  def __init__(self, hou, node, module_node):
    super(BodyRefiner, self).__init__()

    geo = node.geometry()
    self.hou = hou
    self.node = node
    self.module_node = module_node

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
      module_node_pos = node.parent().position()
      subnet.setPosition((module_node_pos[0], module_node_pos[1]+1))

      module_node.setInput(0, subnet)
      return subnet
    
    subnet = make_subnet()
    print('BodyRefiner created')

  def make_request(self):
    url = self.module_node.evalParm("body_refiner_url")
    timeout = self.module_node.evalParm("timeout")
    if url is None or len(url) < 1:
      return
    try:
      data = np.random.randn(2, 4)
      buf = StringIO()
      # with open("c:\\aaa.mp4", "rb") as infile:
      #   data = infile.read()
      np.savez_compressed(buf, a=data)
      buf.seek(0)
      res = requests.post(url=url,   
                          data=buf,
                          headers={'Content-Type': 'application/octet-stream'},
                          timeout=timeout)
      print(res.__dict__)
      
    except Exception as e:
      print(e)
