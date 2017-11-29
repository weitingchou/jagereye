"""The Blob class definition."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from six import string_types

import numpy as np


class Blob(object):
    """The basic data unit for streaming.

    Blob is the basic data unit for streaming. A blob can contain zero, one or
    more float-like tensors (that is, numpy `ndarrays` which are float-like
    types) or string tensors.
    """

    def __init__(self):
        """Create a new `Blob`."""
        self._data = dict()

    def feed(self, name, tensor):
        """Feed a tensor into the blob.

        Args:
          name (string): The name of the tensor.
          tensor (numpy `ndarray`): A numpy `ndarray` object to fed into the
            blob. The data types must be float-like (bool, int, unsigned
            int and float) or string.

        Returns:
          Fed tensor (numpy `ndarray`) if successful.

        Raises:
          TypeError: if `name` is not a string or `tensor` is not a float-like
            tensor.
        """
        if not isinstance(name, string_types):
            raise TypeError('Tensor name must be a string.')
        if not isinstance(tensor, np.ndarray):
            raise TypeError('Only numpy ndarray is supported for feeding.')
        if tensor.dtype.kind not in 'biufS':
            raise TypeError('Only float-like types (bool, int, unsigned '
                            'int and float) are supported for tensor.')

        self._data[name] = tensor

        return tensor

    def has(self, name):
        """Check whether a tensor is in the blob or not.

        Args:
          name (string): The name of the tensor.

        Returns:
          bool: True if the tensor exists, False otherwise.

        Raises:
          TypeError: if `name` is not a string.
        """
        if not isinstance(name, string_types):
            raise TypeError('Tensor name must be a string.')

        return name in self._data

    def fetch(self, name):
        """Fetch a tensor from the blob.

        Args:
          name (string): The name of the tensor.

        Returns:
          Fetched tensor (numpy `ndarray`) if successful.

        Raises:
          TypeError: if `name` is not a string.
          RuntimeError: if the tensor does not exist in the blob.
        """
        if not isinstance(name, string_types):
            raise TypeError('Tensor name must be a string.')
        if not self.has(name):
            raise RuntimeError("Can't find tensor: {}".format(name))

        return self._data[name]

    def remove(self, name):
        """Remove a tensor from the blob.

        Args:
          name (string): The name of the tensor.

        Returns:
          Removed tensor (numpy `ndarray`) if successful.

        Raises:
          TypeError: if `name` is not a string.
          RuntimeError: if the tensor does not exist in the blob.
        """
        if not isinstance(name, string_types):
            raise TypeError('Tensor name must be a string.')
        if not self.has(name):
            raise RuntimeError("Can't find tensor: {}".format(name))

        tensor = self._data[name]
        del self._data[name]

        return tensor

    def copy(self):
        """Copy the blob to a new instance.

        Returns:
          `Blob`: The copied blob.
        """
        c_blob = Blob()

        for name, tensor in self._data.items():
            # TODO(JiaKuan Su): Currently, the tensors are copied during blob
            # copying. Maybe we can also implement more efficient methods
            # such as copy-on-write.
            c_blob.feed(name, np.copy(tensor))

        return c_blob
