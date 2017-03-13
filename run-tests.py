#!/usr/bin/env python
"""Run test cases and split them across CircleCI nodes."""

import argparse
import logging
import os
import subprocess

LOGGER = logging.getLogger()

# Mapping from CircleCI node index to virtualenv
NODE_INDEX_TO_VIRTUALENV_NAMES = [
    ['clientV1-endpoints'],
    [],
    [],
    [],
    [],
    [],
    [],
]


class VirtualEnv(object):

    """Tox virtual environment."""

    def __init__(self, name, config_path):
        self.name = name
        self.config_path = config_path

    def install_dependencies(self):
        """Install dependencies defined in tox configuration."""
        self._run_tox_command(['--notest'])

    def upgrade_development_dependencies(self):
        """Upgrade development dependencies.

        This will upgrade only development dependencies. The reason for this is
        that development dependencies coming from cloudify github repositories
        might be updated even if the version didn't change, so they need to be
        updated on each run.

        """
        base_dir = os.path.dirname(self.config_path)
        virtualenv_dir = os.path.join(base_dir, '.tox', self.name)
        if not os.path.isdir(virtualenv_dir):
            LOGGER.debug(
                "virtualenv directory doesn't exist yet, nothing to upgrade")
            return

        activate_path = os.path.join(virtualenv_dir, 'bin', 'activate')
        dev_requirements_path = os.path.join(base_dir, 'dev-requirements.txt')
        call(
            '. {0}; '
            'pip install -U --no-deps -r {1}; '
            'deactivate'
            .format(activate_path, dev_requirements_path),
            shell=True
        )

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


def upgrade_dependencies(circle_node_index, virtualenvs):
    """Upgrade development dependencies for each tox virtual environment.

    The upgrade happens only for the tox environments to be executed in the
    node in which the command is executed.

    :param virtualenvs: Virtual environments to consider.
    :type virtualenvs: dict(str, VirtualEnv)

    """
    LOGGER.debug('### Upgrading development dependencies...')

    virtualenv_names = NODE_INDEX_TO_VIRTUALENV_NAMES[circle_node_index]
    for virtualenv_name in virtualenv_names:
        virtualenv = virtualenvs[virtualenv_name]
        virtualenv.upgrade_development_dependencies()


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


def call(command, **kwargs):
    """Call subprocess with logging.

    :param command: Command as passed to `subprocess.call`
    :type command: list(str)
    :param kwargs: Keyword arguments to pass to `subprocess.call`
    :type kwargs: dict(str)

    """
    LOGGER.debug('>>> %s', command)
    return subprocess.check_call(command, **kwargs)


def parse_arguments():
    """Parse command line arguments.

    :return: Arguments parsed
    :rtype: :class:`argparse.Namespace`

    """
    parser = argparse.ArgumentParser(description=__doc__)

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-i', '--install-dependencies',
        action='store_true',
        help='Install dependencies (do not run test cases)',
    )
    group.add_argument(
        '-u', '--upgrade-dependencies',
        action='store_true',
        help='Upgrade development dependencies (do not run test cases)',
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
            LOGGER.debug('Not running on first node. Skipping...')
    elif args.upgrade_dependencies:
        upgrade_dependencies(circle_node_index, virtualenvs)
    else:
        run_tests(circle_node_index, virtualenvs)
