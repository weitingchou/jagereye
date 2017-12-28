"""Test utils for jagereye."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from pytest_mock import MockFixture

from jagereye.streaming.blob import Blob


def spy(obj, name):
    """Spy a object method.

    Args:
      obj (object): The object instance.
      name (string): The object method name to spy.

    Returns:
      function: The spy object.
    """
    return MockFixture(None).spy(obj, name)


def create_blob(tensor_name=None, tensor=None):
    """Utility to create a blob instance.

    Args:
      tensor_name (string): The fed tensor name. Defaults to None.
      tensor (numpy `ndarray`): The fed tensor. Defaults to None.

    Returns:
      `Blob`: The created blob.
    """
    blob = Blob()
    if not tensor_name is None and not tensor is None:
        blob.feed(tensor_name, tensor)
    return blob


def create_image_full(fill_value, width=100, height=100):
    """Utility to generate an image filled with given value.

    Args:
      fill_value(list of int): The filled value. The length of filled value
        must be at least one.
      width(int): The image width. Defaults to 100.
      height(int): The image height. Defaults to 100.

    Returns:
      numpy `ndarray`: The created image.
    """
    assert len(fill_value) >= 1, \
           'The length of filled value should at least one.'
    filled_value = fill_value if len(fill_value) > 1 else fill_value[0]
    return np.array([[filled_value] * width] * height).astype(np.uint8)


def create_image_rand(width=100, height=100, channels=3):
    """Utility to generate an image randomly.

    Args:
      width(int): The image width. Defaults to 100.
      height(int): The image height. Defaults to 100.
      channels(int): The number of channels. Defaults to 3.

    Returns:
      numpy `ndarray`: The created image.
    """
    size = (height, width, channels) if channels > 1 else (height, width)
    return np.random.randint(0, 256, size=size).astype(np.uint8)
