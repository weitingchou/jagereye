"""Capturers to capture images from stream."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cv2

from jagereye.streaming.blob import Blob
from jagereye.streaming.capturers.base import ICapturer


class VideoStreamCapturer(ICapturer):
    """The video stream capturer.

    The capturer to read images from a video stream. The video stream can be a
    video file or a live stream such as RTSP, Motion JPEG. Each captured blob
    has a "image" tensor that stores the read image.

    The "image" tensor is a 3-dimensional numpy `ndarray` and the shape format
    is:
    1. Image height.
    2. Image width.
    3. Number of channels, which is usually 3.
    """

    def __init__(self, src):
        """Create a new `VideoStreamCapturer`.

        Args:
          src(string): The video source. It can be a video file name, or live
            stream URL such as RTSP, Motion JPEG.
        """
        self._src = src
        self._cap = None

    @property
    def src(self):
        """string: The video source. It can be a video file name, or live
        stream URL such as RTSP, Motion JPEG."""
        return self._src

    def prepare(self):
        """The routine of video stream capturer preparation.

        Raises:
          RuntimeError: If the video stream is not opened.
        """
        self._cap = cv2.VideoCapture(self._src)
        if not self._cap.isOpened():
            raise RuntimeError(
                'The video stream {} is not opened.'.format(self._src))

    def capture(self):
        """The routine of video stream capturer capturation."""
        success, image = self._cap.read()
        if not success:
            raise EOFError()

        blob = Blob()
        blob.feed('image', image)

        return blob

    def destroy(self):
        """The routine of video stream capturer destruction."""
        self._cap.release()
