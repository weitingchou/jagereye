"""Tests for base modules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import pytest

from jagereye.framework.test_util import create_blob
from jagereye.framework.test_util import create_image_full
from jagereye.framework.test_util import create_image_rand
from jagereye.streaming.modules.grayscale_modules import GrayscaleModule


class TestGrayscaleModule(object):
    """Tests for GrayscaleModule class."""

    def test_prepare(self):
        pass

    def test_execute_non_3_channels_image(self):
        for channels in [1, 2, 4]:
            grayscale_module = GrayscaleModule()
            blob = create_blob('image', create_image_rand(channels=channels))
            with pytest.raises(RuntimeError):
                grayscale_module.execute([blob])

    def test_execute_3_channels_image(self):
        grayscale_module = GrayscaleModule()
        blob = create_blob('image', create_image_full([10, 20, 30]))
        exe_blob = grayscale_module.execute([blob])[0]
        # OUTPUT = 0.587 * G + 0.114 * B + 0.299 * R
        np.testing.assert_equal(exe_blob.fetch('gray_image'),
                                create_image_full([22]))

    def test_destroy(self):
        pass
