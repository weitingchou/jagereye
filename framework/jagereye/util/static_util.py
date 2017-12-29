"""Utilities for manipulating static files."""

import os

import jagereye


def get_path(file_name):
    """Get path of a static file.

    file_name (string): The static file name.
    """
    file_dir = os.path.join(os.path.dirname(jagereye.__file__), 'static')
    file_path = os.path.join(file_dir, file_name)
    return file_path
