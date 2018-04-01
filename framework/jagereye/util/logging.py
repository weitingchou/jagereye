"""Logging utilities."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging as _logging
import logging.config
from logging import DEBUG # pylint: disable=unused-import
from logging import ERROR # pylint: disable=unused-import
from logging import FATAL # pylint: disable=unused-import
from logging import INFO # pylint: disable=unused-import
from logging import WARN # pylint: disable=unused-import

from jagereye.util.generic import get_config

class HbeatFilter(_logging.Filter):
    def __init__(self, is_allowed):
        self._is_allowed = is_allowed
    def filter(self, rec):
        if not self._is_allowed:
            if 'hbeat' in rec.msg:
                return False
        return True

class Logger(object):
    def __init__(self, component):
        config = get_config()['logging']
        formatters = config['formatters']
        for key, value in formatters.items():
            formatters[key]['format'] = '{} - {}'.format(component, value['format'])
        config['formatters'] = formatters
        _logging.config.dictConfig(config)
        self._logger = _logging.getLogger('jagereye_logger')

    def log(self, level, msg, *args, **kwargs):
        """Log message for a given level.

        Args:
          level (int): The log level.
          msg (string): The message to log.
        """
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        """Log debug level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.debug(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Log error level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.error(msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        """Log fatal level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.fatal(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """Log info level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.info(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        """Log warn level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.warn(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Log warn level message.

        Args:
          msg (string): The message to log.
        """
        self._logger.warning(msg, *args, **kwargs)

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
