"""Test utils for jagereye."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from jagereye.streaming.blob import Blob


def create_blob(tensor_name=None, tensor=None):
    """Helper function to create a blob instance.

    Args:
      tensor_name (string): The fed tensor name. Defaults to None.
      tensor (numpy `ndarray`): The fed tensor. Defaults to None.
    """
    blob = Blob()
    if not tensor_name is None and not tensor is None:
        blob.feed(tensor_name, tensor)
    return blob
