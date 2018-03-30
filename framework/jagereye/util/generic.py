"""Generic utilities."""

import inspect
import signal
import threading
import time
import yaml

from jagereye.util import static_util

class _FuncThread(threading.Thread):
    """Inner class for executing the function in a thread."""

    def __init__(self, func, args=(), kwargs={}):
        """Initialize a `_FuncThread` instance.

        Args:
          func (function): The function to execute.
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._result = None

    @property
    def result(self):
        """`object`: The result of function execution."""
        return self._result

    def run(self):
        """Running method of thread."""
        self._result = self._func(*self._args, **self._kwargs)

    def stop(self):
        """Stop the thread."""
        if self.isAlive():
            signal.pthread_kill(self.ident, 0)


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

def get_config(config_file='./config.yml'):
    with open(static_util.get_path(config_file), 'r') as f:
        return yaml.load(f)

def exec_timeout(timeout, func, *args, **kwargs):
    """Execute a function with timeout.

    Args:
      timeout (int): The timeout limit.
      func (function): The function to execute.

    Raises:
      TimeoutError: if the execution time of the given function exceeds the
        limit.
    """
    thread = _FuncThread(func, args, kwargs)

    thread.start()
    thread.join(timeout=timeout)

    if thread.isAlive():
        thread.stop()
        raise TimeoutError('Execution time of function "{}" exceeds the timeout'
                           ' limit ({} seconds)'.format(func.__name__, timeout))
    else:
        return thread.result
