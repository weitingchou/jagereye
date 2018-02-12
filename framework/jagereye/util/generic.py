"""Generic utilities."""

import inspect
import time
import yaml
import os

from jagereye.util import static_util

def get_func_name():
    """ get the function name when inside the current function
    """
    return inspect.stack()[1][3] + str('()')

def now():
    """Get current timestamp.

    Returns:
      float: Current timestamp.
    """
    return time.time()

def get_config():
    JAGERENV = os.environ['JAGERENV']
    config_file = 'config.{}.yml'.format(JAGERENV)
    with open(static_util.get_path(config_file), 'r') as f:
        return yaml.load(f)
