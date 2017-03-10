#!/usr/bin/env python
"""Run test cases and split them across CircleCI nodes."""

import argparse
import logging
import os
import subprocess

LOGGER = logging.getLogger()

# Mapping from CircleCI node index to virtualenv
NODE_INDEX_TO_VIRTUALENV_NAMES = [
    ['clientV1-endpoints', 'clientV1-infrastructure'],
    ['clientV2-endpoints'],
    ['py27', 'clientV2-infrastructure'],
    ['clientV2_1-endpoints'],
    ['clientV2_1-infrastructure'],
    ['clientV3-endpoints'],
    ['clientV3-infrastructure'],
]


class VirtualEnv(object):

    """Tox virtual environment."""

    def __init__(self, name, config_path):
        self.name = name
        self.config_path = config_path

    def install_dependencies(self):
        """Install dependencies defined in tox configuration."""
        self._run_tox_command(['--notest'])

    def run_tests(self):
        """Run test cases for the virtual environment."""
        self._run_tox_command()

    def _run_tox_command(self, extra_parameters=None):
        """Run tox command.

        :extra_parameters: Additional parameters to pass to the command.
        :type extra_parameters: list(str)

        """
        command = ['tox', '-c', self.config_path, '-e', self.name]
        if extra_parameters:
            command.extend(extra_parameters)
        call(command)


def get_virtualenvs():
    """Get virtualenv metadata for this repository.

    :return: Virtual environments
    :rtype: dict(str, VirtualEnv)

    """
    virtualenvs = {}

    rest_config = './rest-service/tox.ini'
    workflows_config = './workflows/tox.ini'

    metadata = {
        workflows_config: ['py27'],
        rest_config: [
            'clientV1-endpoints',
            'clientV1-infrastructure',
            'clientV2-endpoints',
            'clientV2-infrastructure',
            'clientV2_1-endpoints',
            'clientV2_1-infrastructure',
            'clientV3-endpoints',
            'clientV3-infrastructure',
        ],
    }
    for config_path, virtualenv_names in metadata.iteritems():
        for virtualenv_name in virtualenv_names:
            virtualenvs[virtualenv_name] = (
                VirtualEnv(name=virtualenv_name, config_path=config_path)
            )
    return virtualenvs


def install_dependencies(virtualenvs):
    """Install dependencies for each tox virtual environment.

    :param virtualenvs: Virtual environments to consider.
    :type virtualenvs: dict(str, VirtualEnv)

    """
    LOGGER.debug('### Installing dependencies...')

    call(['pip', 'install', 'flake8'])

    for virtualenv in virtualenvs.itervalues():
        virtualenv.install_dependencies()


def run_tests(circle_node_index, virtualenvs):
    """Run test cases splitted in different nodes.

    :param circle_node_index: Node index executing this code in CircleCI
    :type circle_node_index: int
    :param virtualenvs: Virtual environments to consider.
    :type virtualenvs: dict(str, VirtualEnv)

    """
    LOGGER.debug('### Running tests...')

    if circle_node_index == 0:
        call([
            'flake8',
            'plugins/riemann-controller/',
            'workflows/',
            'rest-service/',
            'tests/',
        ])

    virtualenv_names = NODE_INDEX_TO_VIRTUALENV_NAMES[circle_node_index]
    for virtualenv_name in virtualenv_names:
        virtualenv = virtualenvs[virtualenv_name]
        virtualenv.run_tests()


def call(command):
    """Call subprocess with logging.

    :param command: Command as passed to `subprocess.call`
    :type command: list(str)

    """
    LOGGER.debug('>>> %s', ' '.join(command))
    subprocess.call(command)


def parse_arguments():
    """Parse command line arguments.

    :return: Arguments parsed
    :rtype: :class:`argparse.Namespace`

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i', '--install-dependencies',
        action='store_true',
        help='Install dependencies (do not run test cases)',
    )
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_arguments()
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(message)s',
    )

    circle_node_index = int(os.environ['CIRCLE_NODE_INDEX'])
    virtualenvs = get_virtualenvs()

    if args.install_dependencies:
        # Install dependencies only in first node
        # because that's the node that CircleCI uses for caching
        if circle_node_index == 0:
            install_dependencies(virtualenvs)
    else:
        run_tests(circle_node_index, virtualenvs)
