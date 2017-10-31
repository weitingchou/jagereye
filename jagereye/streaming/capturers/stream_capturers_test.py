"""Tests for stream modules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

import pytest

from jagereye.streaming.capturers.stream_capturers import VideoStreamCapturer


class TestVideoStreamCapturer(object):
    """Tests for VideoStreamCapturer class."""

    def test_prepare_non_existing_video(self):
        capturer = VideoStreamCapturer('non_existing.mp4')
        with pytest.raises(RuntimeError):
            capturer.prepare()

    def test_prepare(self):
        pass

    def test_execute(self):
        # TODO(JiaKuan Su): We should also test data source from RTSP, Motion
        # JPEG in the future.
        src = os.path.join(os.getcwd(), 'testdata/hamster.mp4')
        capturer = VideoStreamCapturer(src)
        capturer.prepare()

        blob = capturer.capture()
        image = blob.fetch('image')
        # Test dimension and shape of the captured image
        assert image.ndim == 3
        assert image.shape[0] == 240
        assert image.shape[1] == 320
        assert image.shape[2] == 3

        capturer.destroy()

    def test_destroy(self):
        pass
