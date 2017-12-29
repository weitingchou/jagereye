import glob
import os
from setuptools import Command
from setuptools import find_packages
from setuptools import setup
from shutil import copy
from shutil import rmtree
import subprocess

# Metadata about the package
NAME = 'jagereye'
VERSION = '0.0.1'
DESCRIPTION = 'A large distributed scale video analysis framework.'


# Dependencies for testing
SETUP_REQUIRED=[
    'pytest-runner'
],
TESTS_REQUIRED=[
    'pytest',
    'pytest-mock'
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


class DockerCommand(Command):
    """Command to build docker images."""

    description = 'Build docker images.'
    user_options = [
        ('target=', None, 'Target to build')
    ]
    supported_targets = [
        'worker',
        'brain'
    ]

    def initialize_options(self):
        self.target = None

    def finalize_options(self):
        if self.target is not None:
            if self.target not in self.supported_targets:
                raise Exception('Unsupported docker image: {}'
                                .format(self.target))

    def run(self):
        if self.target is not None:
            self._build(self.target)
        else:
            for target in self.supported_targets:
                self._build(target)

    def _build(self, target):
        docker_file = 'docker/Dockerfile.{}'.format(target)
        image_name = 'jagereye/{}'.format(target)
        docker_cmd = [
            'docker', 'build',
            '-f', docker_file,
            '-t', image_name,
            '.'
        ]
        print('Building Docker: file = {}, image={}'
              .format(docker_file, image_name))
        subprocess.check_call(docker_cmd)


def cp_static_files(static_files):
    """Copy files to static folder.

    Args:
      static_files (list of string): The files to be copied.
    """
    static_dir = os.path.join(NAME, 'static')
    # Create the static directory if necessary.
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    # Now, copy files into the static directory.
    for static_file in static_files:
        if os.path.isfile(static_file):
            copy(static_file, static_dir)
            print('Copy {} into {}'.format(static_file, static_dir))

def load_requirements():
    """Load requirements files."""
    requirements = []
    req_files = glob.glob('./requirements*.txt')
    for req_file in req_files:
        with open(req_file) as f:
            content = f.readlines()
        lines = [x.strip() for x in content]
        requirements = requirements + list(set(lines) - set(requirements))
    return requirements


def main():
    # Get the project root directory.
    if 'JAGER_ROOT' in os.environ:
        proj_root = os.environ['JAGER_ROOT']
    else:
        proj_root = os.path.join(os.getcwd(), '..')

    # Copy static files into framework library directory.
    cp_static_files([
        os.path.join(proj_root, 'services/messaging.json')
    ])

    # Load the requirements.
    install_requires = load_requirements()

    # Now, run the setup script.
    setup(
        name=NAME,
        version=VERSION,
        description=DESCRIPTION,
        packages=find_packages(include=[NAME, '{}.*'.format(NAME)]),
        install_requires=install_requires,
        include_package_data=True,
        setup_requires=SETUP_REQUIRED,
        tests_require=TESTS_REQUIRED,
        zip_safe=False,
        cmdclass = {
            'doc': DocCommand,
            'docker': DockerCommand,
            'lint': LintCommand
        }
    )


if __name__ == '__main__':
    main()
