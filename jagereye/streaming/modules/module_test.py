"""Tests for module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pytest

from jagereye.streaming.modules.module import IModule


class TestIModule(object):
    """Tests for IModule class."""

    def test_prepare(self):
        i_module = IModule()
        with pytest.raises(NotImplementedError):
            i_module.prepare()

    def test_execute(self):
        i_module = IModule()
        with pytest.raises(NotImplementedError):
            i_module.execute([])

    def test_destroy(self):
        i_module = IModule()
        with pytest.raises(NotImplementedError):
            i_module.destroy()
