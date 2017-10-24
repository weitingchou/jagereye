from setuptools import find_packages
from setuptools import setup

NAME = 'jagereye'
VERSION = '0.0.1'
DESCRIPTION = 'A large distributed scale video analysis framework.'

REQUIRED = [
    'numpy'
]

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    py_modules=['jagereye'],
    install_requires=REQUIRED
)
