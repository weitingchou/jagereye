import inspect

def get_func_name():
    """ get the function name when inside the current function
    """
    return inspect.stack()[1][3] + str('()')

