"""Logging utilities."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import logging as _logging
import logging.config
from logging import DEBUG # pylint: disable=unused-import
from logging import ERROR # pylint: disable=unused-import
from logging import FATAL # pylint: disable=unused-import
from logging import INFO # pylint: disable=unused-import
from logging import WARN # pylint: disable=unused-import

from jagereye.util.generic import get_config

config = get_config()['logging']
_logging.config.dictConfig(config)

class Logger(object):
    def __init__(self, component):
        self.component = component
        self.extra_info = {'component': self.component}
        self._logger = _logging.getLogger('default')

    def log(self, level, msg, *args, **kwargs):
        """Log message for a given level.

        Args:
          level (int): The log level.
          msg (string): The message to log.
        """
        self._logger.log(level, msg, extra=self.extra_info, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        """Log debug level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.debug(msg, extra=self.extra_info, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Log error level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.error(msg, extra=self.extra_info, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        """Log fatal level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.fatal(msg, extra=self.extra_info, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """Log info level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.info(msg, extra=self.extra_info, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        """Log warn level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.warn(msg, extra=self.extra_info, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Log warn level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.warning(msg, extra=self.extra_info, *args, **kwargs)


# Controls which methods from pyglib.logging are available within the project.
_allowed_symbols_ = [
    'DEBUG',
    'ERROR',
    'FATAL',
    'INFO',
    'WARN'
    'debug',
    'error',
    'fatal',
    'info',
    'log',
    'warn',
    'warning'
]
