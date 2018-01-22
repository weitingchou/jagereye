"""Capturers to capture images from stream."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
from urllib.parse import urlparse

import cv2
import numpy as np

from jagereye.streaming.exceptions import EndOfVideoError
from jagereye.streaming.exceptions import RetryError
from jagereye.streaming.blob import Blob
from jagereye.streaming.capturers.base import ICapturer
from jagereye.util import logging
from jagereye.util.generic import now


class VideoStreamCapturer(ICapturer):
    """The video stream capturer.

    The capturer to read images from a video stream. The video stream can be a
    video file or a live stream such as RTSP, Motion JPEG. Each captured blob
    has a "image" tensor that stores the read image and a "timestamp" tensor
    that stores the timestamp of the image.

    The "image" tensor is a 3-dimensional numpy `ndarray` whose type is uint8
    and the shape format is:
    1. Image height.
    2. Image width.
    3. Number of channels, which is usually 3.

    The "timestamp" tensor is a 0-dimensional numpy `ndarray` whose type is
    string.
    """

    def __init__(self, src):
        """Create a new `VideoStreamCapturer`.

        Args:
          src(string): The video source. It can be a video file name, or live
            stream URL such as RTSP, Motion JPEG.
        """
        self._src = src
        self._cap = None
        self._retry = False

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
        """The routine of video stream capturer capturation.

        Returns:
          `Blob`: The blob which contains "image" and "timestamp" tensor.

        Raises:
          RetryError: If the stream is live and disconnected temporarily.
          EndOfVideoError: If the stream ends.
        """
        if self._retry:
            self._cap.release()
            self._cap = cv2.VideoCapture(self._src)
            self._retry = False

        success, image = self._cap.read()
        timestamp = np.array(now())

        if not success:
            if self._is_live_stream():
                self._retry = True
                raise RetryError('Try to reconnect to {}'.format(self._src))
            else:
                raise EndOfVideoError('Video {} ends'.format(self._src))

        blob = Blob()
        blob.feed('image', image)
        blob.feed('timestamp', timestamp)

        return blob

    def _is_live_stream(self):
        """Check whether the source is live stream or not.

        Returns:
          bool: True if the source is stream, False otherwise.
        """
        # TODO(JiaKuan Su): Also need check the URL file format, such as
        # "http://url.to/vdieo.mp4"
        return urlparse(self._src).scheme != ''

    def destroy(self):
        """The routine of video stream capturer destruction."""
        self._cap.release()
