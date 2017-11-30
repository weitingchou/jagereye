"""Pipeline implementation."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import threading
import Queue
import time

from jagereye.streaming.capturers.base import ICapturer
from jagereye.streaming.modules.base import IModule


def _receive(capturer, cap_interval, queue, stop_event):
    """Worker function to receive blobs from a capturer."""
    cap_interval_sec = cap_interval / 1000.0
    while not stop_event.is_set():
        try:
            blob = capturer.capture()
            if not blob is None:
                queue.put(blob)
        except Exception: # pylint: disable=broad-except
            # TODO(JiaKuan Su): Handle more exception cases.
            stop_event.set()
        time.sleep(cap_interval_sec)


def _operate(modules, batch_size, wait_interval, queue, stop_event):
    """Worker function to feed blobs and execute modules."""
    wait_interval_sec = wait_interval / 1000.0
    while not stop_event.is_set():
        if queue.qsize() >= batch_size:
            try:
                blobs = [queue.get() for i in range(batch_size)] # pylint: disable=unused-variable
                for module in modules:
                    blobs = module.execute(blobs)
            except Exception: # pylint: disable=broad-except
                # TODO(JiaKuan Su): Handle more exception cases.
                stop_event.set()
        else:
            # Sleep only when queue size is not enough.
            time.sleep(wait_interval_sec)


class Pipeline(object):
    """The streaming execution pipeline.

    Pipeline is the streaming execution runtime. A typical pipeline consists
    of a capturer as data source and multiple modules for data operations. The
    class provides API to register a capturer and modules for pipeline building.
    The class also provides API for pipeline management such as start and stop.
    """

    STATE_INITIALIZED = 0
    STATE_ACTIVE = 1
    STATE_STOPPED = 2

    def __init__(self, cap_interval=50, batch_size=1):
        """Create a new `Pipeline`.

        Args:
          cap_interval (int): The interval (in milliseconds) to capture a new
            blob. Defaults to 0.
          batch_size (int): The size of batch. Defaults to 1.
        """
        self._cap_interval = cap_interval
        self._batch_size = batch_size
        self._capturer = None
        self._modules = []
        self._state = self.STATE_INITIALIZED
        self._threads = []
        self._stop_event = None

    @property
    def cap_interval(self):
        """int: The interval (in milliseconds) to capture a new blob."""
        return self._cap_interval

    @property
    def batch_size(self):
        """int: The size of batch."""
        return self._batch_size

    @property
    def capturer(self):
        """`ICapturer`: The capturer in the pipeline."""
        return self._capturer

    @property
    def modules(self):
        """list of `IModule`: The modules in the pipeline."""
        return self._modules

    @property
    def state(self):
        """int: The pipeline state."""
        return self._state

    def source(self, capturer):
        """Set a capturer as the data source.

        Args:
          capturer (`ICapturer`): The capturer to set.

        Returns:
          `Pipeline`: The pipeline instance.

        Raises:
          TypeError: if capturer is not a `ICapturer` instance.
        """
        if not isinstance(capturer, ICapturer):
            raise TypeError('Source must a ICapturer instance.')
        self._capturer = capturer
        return self

    def pipe(self, module):
        """Add a module to the end of the pipeline.

        Args:
          module (IModule): The module to be added.

        Returns:
          `Pipeline`: The pipeline instance.

        Raises:
          TypeError: if module is not a `IModule` instance.
        """
        if not isinstance(module, IModule):
            raise TypeError('Module must a ICapturer instance.')
        self._modules.append(module)
        return self

    def start(self):
        """Start the execution of pipeline streaming without blocking.

        Raises:
          RuntimeError: if no capturer is set, or no module is added, or the
            pipeline is not in initialized state.
        """
        if self._state == self.STATE_INITIALIZED:
            if self._capturer is None:
                raise RuntimeError('Capturer is not set for pipeline starting.')
            if not self._modules:
                raise RuntimeError('At least one module must be added for '
                                   'pipeline running.')
            self._start()
            self._state = self.STATE_ACTIVE
        elif self._state == self.STATE_ACTIVE:
            raise RuntimeError('Pipeline has been already started.')
        elif self._state == self.STATE_STOPPED:
            raise RuntimeError('Pipeline has been already stopped.')

    def stop(self):
        """Stop the execution of pipeline streaming.

        Raises:
          RuntimeError: if the pipeline is not in stopped state.
        """
        if self._state == self.STATE_INITIALIZED:
            raise RuntimeError('Pipeline has not been already started yet.')
        elif self._state == self.STATE_ACTIVE:
            self._stop()
            self._state = self.STATE_STOPPED
        elif self._state == self.STATE_STOPPED:
            raise RuntimeError('Pipeline has been already stopped.')

    def await_termination(self):
        """Wait for the execution to stop.

        Wait for the execution to stop. Any exception that occurs during the
          execution will cause the pipeline to stop.
        """
        if self._state == self.STATE_INITIALIZED:
            raise RuntimeError('Pipeline has not been already started yet.')
        elif self._state == self.STATE_ACTIVE:
            self._await_termination()
            self._state = self.STATE_STOPPED
        elif self._state == self.STATE_STOPPED:
            raise RuntimeError('Pipeline has been already stopped.')

    def _prepare(self):
        """Inner method for pipeline preparation."""
        self._capturer.prepare()
        for module in self._modules:
            module.prepare()

    def _destroy(self):
        """Inner method for pipeline destruction."""
        self._capturer.destroy()
        for module in self._modules:
            module.destroy()

    def _start(self):
        """Inner method for pipeline starting."""
        self._prepare()

        # Create threads for pipeline execution.
        queue = Queue.Queue()
        self._stop_event = threading.Event()
        rec_args = (self._capturer, self._cap_interval, queue,
                    self._stop_event,)
        op_args = (self._modules, self._batch_size, self._cap_interval,
                   queue, self._stop_event,)
        self._threads.append(threading.Thread(target=_receive, args=rec_args))
        self._threads.append(threading.Thread(target=_operate, args=op_args))

        # Start the threads.
        for thread in self._threads:
            thread.setDaemon(True)
            thread.start()

    def _stop(self):
        """Inner method for pipeline stopping."""
        self._stop_event.set()

        # Wait for threads to make sure they stopped.
        for thread in self._threads:
            thread.join()

        self._destroy()

    def _await_termination(self):
        """Inner method for await_termination."""
        # FIXME(JiaKuan Su): It seems that the main thread can't receive
        # external signal (such as Ctrl-C) when using Event.wait() without
        # timeout, so I temporalily use Event.wait() with timeout in a while
        # loop.
        while not self._stop_event.isSet():
            self._stop_event.wait(0.1)

        # Wait for threads to make sure they stopped.
        for thread in self._threads:
            thread.join()

        self._destroy()
