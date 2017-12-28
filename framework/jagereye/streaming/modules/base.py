"""The base definition of modules."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc


class IModule(object):
    """The base module interface.

    Module is the basic operation unit in the streaming pipeline. The base of
    modules is `IModule` class, which provides interface of module lifecycle
    hooks.
    """

    @abc.abstractmethod
    def prepare(self):
        """The routine of module preparation.

        The pipeline will call this function immediately after starting. The
          function is for module preparation before pipeline execution.

        Raises:
          NotImplementedError: If the function is not implemented.
        """
        raise NotImplementedError('Should have implemented this function.')

    @abc.abstractmethod
    def execute(self, blobs):
        """The routine of module execution.

        The pipeline will iteratively call this function during pipeline
          execution. The pipeline feeds a list of blobs into the module and
          expects to get a list of executed blobs.

        Args:
            blobs (list of `Blob`): The input blobs for execution.

        Returns:
            list of `Blob`: The executed blobs.

        Raises:
          NotImplementedError: If the function is not implemented.
        """
        raise NotImplementedError('Should have implemented this function.')

    @abc.abstractmethod
    def destroy(self):
        """The routine of module destruction.

        The pipeline will call this function immediately after stopping. The
          function is for module destruction after pipeline execution.

        Raises:
          NotImplementedError: If the function is not implemented.
        """
        raise NotImplementedError('Should have implemented this function.')
