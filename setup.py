from setuptools import Command
from setuptools import setup
import subprocess

# Metadata about the package
NAME = 'jagereye'
VERSION = '0.0.1'
DESCRIPTION = 'A large distributed scale video analysis framework.'

# Dependencies for installation
INSTALL_REQUIRED = [
    'numpy',
    'six'
]

# Dependencies for testing
SETUP_REQUIRED=[
    'pytest-runner'
],
TESTS_REQUIRED=[
    'pytest'
]

class DocCommand(Command):
    """Command to generate documentation."""

    description = 'Generate documentation.'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.check_call(['doxygen', '.Doxyfile'])

class LintCommand(Command):
    """Command to lint source code."""

    description = 'Lint source code.'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.check_call(['pylint', 'jagereye'])

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    py_modules=['jagereye'],
    install_requires=INSTALL_REQUIRED,
    setup_requires=SETUP_REQUIRED,
    tests_require=TESTS_REQUIRED,
    cmdclass = {
        'doc': DocCommand,
        'lint': LintCommand
    }
)
