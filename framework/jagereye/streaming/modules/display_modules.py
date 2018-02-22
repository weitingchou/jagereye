"""Modules to display video streams."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cv2

from jagereye.streaming.modules.base import IModule


class DisplayModule(IModule):
    """The video stream displaying module.

    The stream displaying module to show on a window. Each input blob must
    contain a tensor whose default name is "image". Users can also specify the
    name of input tensor such as "gray_image" instead of the default name.

    The dimension of input "image" tensor must be a 2 (grayscale) or 3 (BGR) and
    its type is unit8. The shape format is:
    1. Image height.
    2. Image width.
    3. (Only for 3-dimensional tensor) Number of channels, which is usually 3.
    """

    def __init__(self, window_name='Stream', image_name='image'):
        """Create a new `DisplayModule`.

        Args:
          window_name (string): The window name. Defaults to "stream".
          image_name (string): The name of input tensor to read. Defaults to
            "image".
        """
        self._window_name = window_name
        self._image_name = image_name

    def prepare(self):
        """The routine of display module preparation to create a new window."""
        cv2.namedWindow(self._window_name)

    def execute(self, blobs):
        """The routine of display module execution to show a new image.

        Args:
          blobs (list of `Blob`): The input blobs for execution. Each blob must
            contain a tensor whose default name is "image". The dimension of
            the tensor must be 2 or 3.

        Returns:
          list of `Blob`: The output blobs which are equal to the input blobs.

        Raises:
            RuntimeError: If the input tensor is not 3-dimensional.
        """
        if blobs:
            # TODO(JiaKuan Su): Handle multiple blobs.
            image = blobs[0].fetch(self._image_name)
            if image.ndim != 2 and image.ndim != 3:
                raise RuntimeError('The input "image" tensor is not '
                                   '2 or 3-dimensional.')
            cv2.imshow(self._window_name, image)
            cv2.waitKey(1)
        return blobs

    def destroy(self):
        """The routine of display module destruction to destroy window."""
        cv2.destroyWindow(self._window_name)
