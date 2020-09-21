from __future__ import print_function, absolute_import

import sys, os, io
import numpy as np
import cv2

uint8_dt = np.uint8(1).dtype.newbyteorder('<')

def encode_image(image, format='.jpg', jpeg_quality=95, png_compresion=3):
  """Encodes a raw image to JPEG/PNG. Expects BGR/BGRA
  """
  params = []
  if 'jpg' in format:
    params += [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
  if 'png' in format:
    params += [int(cv2.IMWRITE_PNG_COMPRESSION), png_compresion]
  is_success, data = cv2.imencode(format, image, params)
  if not is_success:
    return None
  return data.astype(uint8_dt).tobytes()

def decode_image(data, type='cv'):
  if type.lower() == 'cv':
    data = np.frombuffer(data, dtype=uint8_dt)
    image = cv2.imdecode(np.frombuffer(data, dtype=uint8_dt), cv2.IMREAD_UNCHANGED)
  elif type.lower() == 'pil':
    try:
      from PIL import Image
      data = io.BytesIO(data)
      image = Image.open(data)
    except:
      image = None
      print("Pillow not available")
  return image