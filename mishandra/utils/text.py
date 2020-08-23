from __future__ import print_function, absolute_import

import os

is_notebook = "JPY_PARENT_PID" in os.environ

class Colored():
  def __init__(self):
    if not is_notebook:
      self.none = lambda x: x
      self.red = lambda x: x
      self.green = lambda x: x
      self.yellow = lambda x: x
      self.blue = lambda x: x
      self.magenta = lambda x: x
      self.cyan = lambda x: x
      self.gray = lambda x: x
    else:
      self.none = lambda x: x
      self.red = lambda x: "\x1b[31m{}\x1b[0m".format(x)
      self.green = lambda x: "\x1b[32m{}\x1b[0m".format(x)
      self.yellow = lambda x: "\x1b[33m{}\x1b[0m".format(x)
      self.blue = lambda x: "\x1b[34m{}\x1b[0m".format(x)
      self.magenta = lambda x: "\x1b[35m{}\x1b[0m".format(x)
      self.cyan = lambda x: "\x1b[36m{}\x1b[0m".format(x)
      self.gray = lambda x: "\x1b[90m{}\x1b[0m".format(x)

class Decorated():
  def __init__(self):
    if not is_notebook:
      self.bold = lambda x: x
    else:
      self.bold = lambda x: "\u001b[1m{}\u001b[0m".format(x)

colored = Colored()
decorated = Decorated()