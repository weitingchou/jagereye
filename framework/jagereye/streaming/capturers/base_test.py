"""Tests for base modules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pytest

from jagereye.streaming.capturers.base import ICapturer


class TestICapturer(object):
    """Tests for ICapturer class."""

    def test_prepare(self):
        i_capturer = ICapturer()
        with pytest.raises(NotImplementedError):
            i_capturer.prepare()

    def test_execute(self):
        i_capturer = ICapturer()
        with pytest.raises(NotImplementedError):
            i_capturer.capture()

    def test_destroy(self):
        i_capturer = ICapturer()
        with pytest.raises(NotImplementedError):
            i_capturer.destroy()
