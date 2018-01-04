"""
docker_gen

Usage:
    docker_gen [--workdir=WORKDIR] [--rootdir=ROOTDIR] TARGET
    docker_gen -h | --help

Arguments:
    TARGET                  Target to generate.

Options:
    --workdir=WORKDIR       Working dirctory of the script to run in.
    --rootdir=ROOTDIR       Root dirctory of the project.
    -h --help               Show this screen.

Examples:
    docker_gen all
"""

from docopt import docopt
from termcolor import colored
import jinja2
import yaml
import sys
import os
import errno


SUPPORTED_TARGETS = ['All', 'Services', 'Apps']


def load_config(filename):
    with open(filename, 'r') as f:
        config = yaml.load(f.read())
    return config


def write_file(filename, content):
    with open(filename, 'w') as f:
        f.write(content)


def errexit(message):
    sys.exit('{}: {}'.format(colored('ERROR', 'red'), message))


class Base(object):
    """A base target class."""
    def __init__(self, workdir, rootdir):
        self._workdir = workdir if workdir else '.'
        self._rootdir = rootdir if rootdir else '.'

    def run(self):
        """Generate a docker-compose.yml.

        Generate a docker-compose.yml according to corresponding
        configuration file, and put it under workdir.

        """
        raise NotImplementedError(
            'You must implement the run() method yourself!!'
        )


class All(Base):
    def run(self):
        print('gen all')


class Services(Base):
    def run(self):
        # Load template
        tempfile = os.path.join(self._rootdir,
                                'deploy/templates/docker-compose.services.jin')
        with open(tempfile, 'r') as f:
            tempfile = f.read()
        self._template = jinja2.Template(tempfile)

        try:
            config_file = os.path.join(self._workdir, 'services/config.yml')
            config = load_config(config_file)['services']
        except OSError as e:
            if e.errno == errno.ENOENT:
                errexit('Service config file "{}" was not found'.format(e.filename))
        except KeyError as e:
            if e == 'services':
                errexit('Invalid service config file format')

        # Construct build path
        for (k, v) in config.items():
            config[k]['buildpath'] = os.path.join(self._workdir, 'services', k)

        # Generate docker-compose file
        output = self._template.render(
            api=config['api'],
            database=config['database'],
            messaging=config['messaging'],
            mem_db=config['mem_db'],
            environ=os.environ
        )
        output_file = os.path.join(self._workdir, 'docker-compose.yml')
        write_file(output_file, output)


class Apps(Base):
    def run(self):
        print('gen apps docker-compose.yml')


def main():
    options = docopt(__doc__, version='1.0.0')

    # Parse options
    workdir = options['--workdir']
    if options['--rootdir']:
        rootdir = options['--rootdir']
    elif os.environ['JAGERROOT']:
        rootdir = os.environ['JAGERROOT']
    else:
        errexit('--rootdir was not specified and JAGERROOT was not defined')

    # Generate target docker-compose file
    target = options['TARGET'].capitalize()
    if target in SUPPORTED_TARGETS:
        target_cls = getattr(sys.modules[__name__], target)
        instance = target_cls(workdir, rootdir)
        instance.run()
    else:
        errexit('Invalid target: {}, not in: {}'.format(target,
                                                        SUPPORTED_TARGETS))


if __name__ == '__main__':
    main()
