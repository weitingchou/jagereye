"""Tests for pipeline."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time

import numpy as np
import pytest

from jagereye.framework.test_util import spy
from jagereye.streaming.blob import Blob
from jagereye.streaming.capturers.base import ICapturer
from jagereye.streaming.modules.base import IModule
from jagereye.streaming.pipeline import Pipeline


class _NumberCapturer(ICapturer):
    """Capturer to generate number blobs."""

    def __init__(self, num=0.0):
        self._num = np.array([num])

    def prepare(self):
        pass

    def capture(self):
        blob = Blob()
        blob.feed('number', self._num)
        return blob

    def destroy(self):
        pass


class _NumberOpModule(IModule):
    """Module for arithmetic operators execution on number module, including '+'
    and '*'."""

    def __init__(self, operator='+', operand=1.0):
        self._operator = operator
        self._operand = np.array([operand])

    def prepare(self):
        pass

    def execute(self, blobs):
        result_blobs = []
        for blob in blobs:
            num = blob.fetch('number')
            if self._operator == '*':
                blob.feed('number', np.multiply(num, self._operand))
            else:
                blob.feed('number', np.add(num, self._operand))
            result_blobs.append(blob)
        return result_blobs

    def destroy(self):
        pass


class _NumberResultModule(IModule):
    """Module to store the result."""

    def __init__(self):
        self._results = []

    @property
    def results(self):
        """list of numpy `ndarray`: The results."""
        return self._results

    def prepare(self):
        pass

    def execute(self, blobs):
        self._results = []
        for blob in blobs:
            num = blob.fetch('number')
            self._results.append(num)
        return blobs

    def destroy(self):
        pass


class _ExceptionModule(IModule):
    """Module to raise an exception."""

    def __init__(self, count=1):
        self._counter = 0
        self._count = count

    def prepare(self):
        pass

    def execute(self, blobs):
        self._counter += 1
        if self._counter >= self._count:
            raise Exception()
        return blobs

    def destroy(self):
        pass

def _gen_pipeline(capturer=None, modules=None):
    """Generate a pipeline."""
    pipeline = Pipeline()

    if not capturer is None:
        pipeline.source(capturer)
    if not modules is None:
        for module in modules:
            pipeline.pipe(module)

    return pipeline


def _gen_num_pipeline(init_num=0.0, to_add=1.0, to_mul=1.0):
    """Generate a pipeline for number arithmetic execution."""
    capturer = _NumberCapturer(num=init_num)
    modules = [
        _NumberOpModule(operator='+', operand=to_add),
        _NumberOpModule(operator='*', operand=to_mul)
    ]
    pipeline = _gen_pipeline(capturer=capturer, modules=modules)
    return pipeline


def _spy_pipeline(pipeline):
    "Spy the capturer and modules in a pipeline."
    capturer = pipeline.capturer
    spy(capturer, 'prepare')
    spy(capturer, 'capture')
    spy(capturer, 'destroy')
    for module in pipeline.modules:
        spy(module, 'prepare')
        spy(module, 'execute')
        spy(module, 'destroy')


class TestPipeline(object):
    """Tests for Pipeline class."""

    def test_source_non_capturer(self):
        pipeline = Pipeline()
        with pytest.raises(TypeError):
            pipeline.source(100)

    def test_source(self):
        pipeline = Pipeline()
        capturer = _NumberCapturer()
        assert pipeline.source(capturer) == pipeline
        assert pipeline.capturer == capturer

    def test_pipe_non_module(self):
        pipeline = _gen_pipeline()
        with pytest.raises(TypeError):
            pipeline.pipe(100)

    def test_pipe(self):
        pipeline = _gen_pipeline()
        modules = [_NumberOpModule() for i in range(3)] # pylint: disable=unused-variable
        for module in modules:
            assert pipeline.pipe(module) == pipeline
        assert pipeline.modules == modules

    def test_start_without_capturer(self):
        pipeline = _gen_pipeline(modules=[_NumberOpModule()])
        with pytest.raises(RuntimeError):
            pipeline.start()

    def test_start_without_module(self):
        pipeline = _gen_pipeline(capturer=_NumberCapturer())
        with pytest.raises(RuntimeError):
            pipeline.start()

    def test_start_twice(self):
        pipeline = _gen_num_pipeline()
        pipeline.start()
        with pytest.raises(RuntimeError):
            pipeline.start()
        pipeline.stop()

    def test_start_after_stop(self):
        pipeline = _gen_num_pipeline()
        pipeline.start()
        pipeline.stop()
        with pytest.raises(RuntimeError):
            pipeline.start()

    def test_start_then_stop(self):
        result_module = _NumberResultModule()
        pipeline = _gen_num_pipeline(init_num=10, to_add=30, to_mul=5)
        pipeline.pipe(result_module)
        _spy_pipeline(pipeline)

        capturer = pipeline.capturer
        modules = pipeline.modules

        # Test whether the "prepare" callbacks are called after starting.
        pipeline.start()
        assert capturer.prepare.call_count == 1
        for module in modules:
            assert module.prepare.call_count == 1

        # Manually wait and then test whether the results are right.
        time.sleep(0.5)
        assert capturer.capture.call_count > 0
        for module in modules:
            assert module.execute.call_count > 0
        for result in result_module.results:
            np.testing.assert_equal(result, np.array([200]))

        # Test whether the "destroy" callbacks are called after stopping.
        pipeline.stop()
        assert capturer.destroy.call_count == 1
        for module in modules:
            assert module.destroy.call_count == 1

    def test_start_then_await(self):
        result_module = _NumberResultModule()
        exception_module = _ExceptionModule(count=10)
        pipeline = _gen_num_pipeline(init_num=3, to_add=33, to_mul=7)
        pipeline.pipe(result_module)
        pipeline.pipe(exception_module)
        _spy_pipeline(pipeline)

        capturer = pipeline.capturer
        modules = pipeline.modules

        # Test whether the "prepare" callbacks are called after starting.
        pipeline.start()
        assert capturer.prepare.call_count == 1
        for module in modules:
            assert module.prepare.call_count == 1

        # Await and then test whether the results are right.
        pipeline.await_termination()
        assert capturer.capture.call_count > 0
        for module in modules:
            assert module.execute.call_count == 10
        for result in result_module.results:
            np.testing.assert_equal(result, np.array([252]))

        # Test whether the "destroy" callbacks are called after stopping.
        assert capturer.destroy.call_count == 1
        for module in modules:
            assert module.destroy.call_count == 1

    def test_stop_before_start(self):
        pipeline = _gen_num_pipeline()
        with pytest.raises(RuntimeError):
            pipeline.stop()

    def test_stop_twice(self):
        pipeline = _gen_num_pipeline()
        pipeline.start()
        pipeline.stop()
        with pytest.raises(RuntimeError):
            pipeline.stop()

    def test_await_before_start(self):
        pipeline = _gen_num_pipeline()
        with pytest.raises(RuntimeError):
            pipeline.await_termination()

    def test_await_after_stop(self):
        pipeline = _gen_num_pipeline()
        pipeline.start()
        pipeline.stop()
        with pytest.raises(RuntimeError):
            pipeline.await_termination()
