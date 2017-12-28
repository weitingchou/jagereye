"""The base definition of capturer."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc


class ICapturer(object):
    """The base capturer interface.

    Capturer is the data source in the streaming pipeline. The base of
    capturers is `ICapturer` class, which provides interface of capturer
    lifecycle hooks.
    """

    @abc.abstractmethod
    def prepare(self):
        """The routine of capturer preparation.

        The pipeline will call this function immediately after starting. The
          function is for capturer preparation before pipeline execution.

        Raises:
          NotImplementedError: If the function is not implemented.
        """
        raise NotImplementedError('Should have implemented this function.')

    @abc.abstractmethod
    def capture(self):
        """The routine to capture a blob.

        The Pipeline will periodically call this function to capture blobs
          during pipeline execution. The pipeline expects to get a new blob,
          but the result can also be None. If no more data to capture, this
          function should raise an EOFError to let pipeline know.

        Returns:
            The captured blob (`Blob`) or None.

        Raises:
          NotImplementedError: If the function is not implemented.
          EOFError: If no more data to read.
        """
        raise NotImplementedError('Should have implemented this function.')

    @abc.abstractmethod
    def destroy(self):
        """The routine of capturer destruction.

        The pipeline will call this function immediately after stopping. The
          function is for capturer destruction after pipeline execution.

        Raises:
          NotImplementedError: If the function is not implemented.
        """
        raise NotImplementedError('Should have implemented this function.')
