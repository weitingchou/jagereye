"""Logging utilities."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging as _logging
from logging import DEBUG
from logging import ERROR
from logging import FATAL
from logging import INFO
from logging import WARN


_logging.basicConfig(level=_logging.INFO)
_logger = _logging.getLogger('jagereye')


def log(level, msg, *args, **kwargs):
    _logger.log(level, msg, *args, **kwargs)


def debug(msg, *args, **kwargs):
    _logger.debug(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    _logger.error(msg, *args, **kwargs)


def fatal(msg, *args, **kwargs):
    _logger.fatal(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    _logger.info(msg, *args, **kwargs)


def warn(msg, *args, **kwargs):
    _logger.warn(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    _logger.warning(msg, *args, **kwargs)


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
