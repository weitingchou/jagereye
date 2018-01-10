"""Generic utilities."""

import inspect
import time


def get_func_name():
    """ get the function name when inside the current function
    """
    return inspect.stack()[1][3] + str('()')


def now():
    """Get current time.

    Returns:
      float: Current time.
    """
    return time.time()
