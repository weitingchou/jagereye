"""Modules to convert images to graysclae images."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cv2

from jagereye.streaming.modules.base import IModule


class GrayscaleModule(IModule):
    """The grayscale module.

    The grayscale module converts BGR images into grayscale images. Each input
    blob must contain a tensor whose name is "image". Each output blob will be
    fed a "gray_image" tensor that stores the converted image.

    The input "image" tensor must be a 3-dimensional numpy `ndarray` and the
    shape format is:
    1. Image height.
    2. Image width.
    3. Number of channels, which must be 3.

    The output "gray_image" tensor is a 2-dimensional numpy `ndarray` and the
    shape format is:
    1. Image height.
    2. Image width.
    """

    def prepare(self):
        """The routine of grayscale module preparation."""
        pass

    def execute(self, blobs):
        """The routine of grayscale module execution.

        Args:
          blobs (list of `Blob`): The input blobs for execution. Each blob
            must contain a "image" tensor. The tensor must be 3-dimensional
            and the 3rd dimension must be 3.

        Returns:
          list of `Blob`: The executed blobs. Each blob will be fed a
            "gray_scale" tensor. The tensor is 3-dimensional.

        Raises:
            RuntimeError: If the input "image" tensor is not 3-dimensional or
              the 3rd dimension is not 3
        """
        exe_blobs = []

        for blob in blobs:
            image = blob.fetch('image')
            if image.ndim != 3:
                raise RuntimeError('The input "image" tensor is not'
                                   '3-dimensional.')
            if image.shape[2] != 3:
                raise RuntimeError('The 3rd dimension of input "image" tensor'
                                   'is not 3.')
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blob.feed('gray_image', gray_image)
            exe_blobs.append(blob)

        return exe_blobs

    def destroy(self):
        """The routine of module destruction."""
        pass
