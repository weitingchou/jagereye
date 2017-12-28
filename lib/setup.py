from setuptools import Command
from setuptools import find_packages
from setuptools import setup
import subprocess

# Metadata about the package
NAME = 'jagereye'
VERSION = '0.0.1'
DESCRIPTION = 'A large distributed scale video analysis framework.'

# Dependencies for installation
INSTALL_REQUIRED = [
    'asyncio-nats-client',
    'numpy',
    'six',
    'tensorflow',
    'tensorflow-gpu'
]

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
    self.supported_targets = [
        'worker'
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
        # subprocess.check_call(docker_cmd)

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    packages=find_packages(exclude='testdata'),
    install_requires=INSTALL_REQUIRED,
    setup_requires=SETUP_REQUIRED,
    tests_require=TESTS_REQUIRED,
    zip_safe=False,
    cmdclass = {
        'doc': DocCommand,
        'docker': DockerCommand,
        'lint': LintCommand
    }
)
