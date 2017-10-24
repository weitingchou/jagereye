from setuptools import setup

# Metadata about the package
NAME = 'jagereye'
VERSION = '0.0.1'
DESCRIPTION = 'A large distributed scale video analysis framework.'

# Dependencies for installation
INSTALL_REQUIRED = [
    'numpy'
]

# Dependencies for testing
SETUP_REQUIRED=[
    'pytest-runner'
],
TESTS_REQUIRED=[
    'pytest'
]

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    py_modules=['jagereye'],
    install_requires=INSTALL_REQUIRED,
    setup_requires=SETUP_REQUIRED,
    tests_require=TESTS_REQUIRED
)
