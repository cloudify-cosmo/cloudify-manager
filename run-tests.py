#!/usr/bin/env python
"""Run test cases and split them across CircleCI nodes."""

import argparse
import logging
import os
import subprocess

LOGGER = logging.getLogger()
REST_CONFIG = './rest-service/tox.ini'
WORKFLOWS_CONFIG = './workflows/tox.ini'


def install_dependencies():
    """Install dependencies for each tox virtual environment."""
    LOGGER.debug('### Installing dependencies...')

    call(['pip', 'install', 'flake8'])

    tox_commands = {
        WORKFLOWS_CONFIG: 'py27',
        REST_CONFIG: [
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
    run_tox_commands(tox_commands, ['--notest'])


def run(circle_node_index):
    """Run test cases splitted in different nodes.

    :param circle_node_index: Node index executing this code in CircleCI
    :type circle_node_index: int

    """
    LOGGER.debug('### Running tests...')

    all_commands = [
        {REST_CONFIG: ['clientV1-endpoints', 'clientV1-infrastructure']},
        {REST_CONFIG: 'clientV2-endpoints'},
        {
            WORKFLOWS_CONFIG: 'py27',
            REST_CONFIG: 'clientV2-infrastructure',
        },
        {REST_CONFIG: 'clientV2_1-endpoints'},
        {REST_CONFIG: 'clientV2_1-infrastructure'},
        {REST_CONFIG: 'clientV3-endpoints'},
        {REST_CONFIG: 'clientV3-infrastructure'},
    ]

    if circle_node_index == 0:
        call([
            'flake8',
            'plugins/riemann-controller/',
            'workflows/',
            'rest-service/',
            'tests/',
        ])

    run_tox_commands(all_commands[circle_node_index])


def run_tox_commands(tox_commands, extra_parameters=None):
    """Run tox commands.

    :param tox_commands: Metadata with configuration file path and virtualenvs
    :type tox_commands: dict(str, list(str) | str)

    """
    for config, virtualenvs in tox_commands.iteritems():
        if isinstance(virtualenvs, str):
            virtualenvs = [virtualenvs]

        for virtualenv in virtualenvs:
            command = ['tox', '-c', config, '-e', virtualenv]
            if extra_parameters:
                command.extend(extra_parameters)
            call(command)


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

    if args.install_dependencies:
        # Install dependencies only in first node
        # because that's the node that CircleCI uses for caching
        if circle_node_index == 0:
            install_dependencies()
    else:
        run(circle_node_index)
