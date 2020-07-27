import sys, os, io
import numpy as np
from PIL import Image
import cv2


uint8_dt = np.uint8(1).dtype.newbyteorder('<')

def encode_image(image, format='.jpg', jpeg_quality=95, png_compresion=3):
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
    data = io.BytesIO(data)
    image = Image.open(data)
  return image