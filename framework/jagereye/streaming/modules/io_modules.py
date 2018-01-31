"""Modules to manipulate I/O."""

import os

import cv2
import numpy as np

from jagereye.streaming.modules.base import IModule
from jagereye.util import logging


def _abs_file_name(files_dir, file_name):
    """Get absolute file name for a given file name.

    Args:
      files_dir (dict): The directory to store the output file. It has two
        items: "abs" for absolute path, "relative" for realtive path to the
        shared root directory.
      file_name (string): The name of file to store.

    Returns:
      string: The absolute file name.
    """
    return os.path.join(files_dir['abs'], file_name)


def _relative_file_name(files_dir, file_name):
    """Get relative file name for a given file name.

    Args:
      files_dir (dict): The directory to store the output file. It has two
        items: "abs" for absolute path, "relative" for realtive path to the
        shared root directory.
      file_name (string): The name of file to store.

    Returns:
      string: The relative file name.
    """
    return os.path.join(files_dir['relative'], file_name)


class ImageSaveModule(IModule):
    """The module for saving images."""

    def __init__(self,
                 files_dir,
                 image_format='jpg',
                 max_width=0,
                 image_name='image'):
        """Create a new `ImageSaveModule`.

        Args:
          files_dir (dict): The directory to store the output image. It has two
            items: "abs" for absolute path, "relative" for realtive path to the
            shared root directory.
          image_format (string): The format of image to save. Defaults to "jpg".
          max_width (int): The maximum width of output image. If the given
            image width is larger than max_width, the width of output image
            file will be equal to max_width, and the height will be shrunk
            proportionally. When max_width <= 0, the maximum width of output
            image is unlimited. Defaults to 0.
          image_name (string): The name of input tensor to read. Defaults to
            "image".

        Raises:
            RuntimeError: If the input tensor is not 2 or 3-dimensional.
        """
        self._files_dir = files_dir
        self._image_format = image_format
        self._max_width = max_width
        self._image_name = image_name

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        """The routine of module execution to save images."""
        # TODO(JiaKuan Su): Currently, I only handle the case for batch_size=1,
        # please help complete the case for batch_size>1.
        blob = blobs[0]

        if blob.has('to_save') and blob.fetch('to_save').tolist():
            image = blob.fetch(self._image_name)
            timestamp = blob.fetch('timestamp').tolist()

            if image.ndim != 2 and image.ndim != 3:
                raise RuntimeError('The input "image" tensor is not '
                                   '3-dimensional.')

            origianl_width = image.shape[1]
            if self._max_width > 0 and origianl_width > self._max_width:
                ratio = self._max_width / origianl_width
                image = cv2.resize(image, (0, 0), fx=ratio, fy=ratio)

            # Construct the image file name.
            image_file = '{}.{}'.format(timestamp, self._image_format)
            abs_image_name = _abs_file_name(self._files_dir, image_file)
            relative_image_name = _relative_file_name(self._files_dir,
                                                      image_file)
            # Save Image to disk.
            cv2.imwrite(abs_image_name, image)
            logging.info('Save image: {}'.format(abs_image_name))

            # Feed the relative image file name to blob.
            blob.feed('abs_image_name', np.array(abs_image_name))
            blob.feed('relative_image_name', np.array(relative_image_name))

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        pass
