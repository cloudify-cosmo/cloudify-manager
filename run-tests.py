#!/usr/bin/env python

import argparse
import logging
import os

from subprocess import call

LOGGER = logging.getLogger()
REST_CONFIG = './rest-service/tox.ini'
WORKFLOWS_CONFIG = './workflows/tox.ini'


def install_dependencies():
    """Install dependencies for each tox virtual environment."""
    LOGGER.debug('### Installing dependencies...')

    call(['pip', 'install', 'flake8'])

    tox_commands = {
        WORKFLOWS_CONFIG: [
            'py27',
        ],
        REST_CONFIG: [
            'clientV1-endpoints',
            'clientV1-infrastructure',
            'clientV2-endpoints',
            'clientV2-infrastructure',
            'clientV2_1-endpoints',
            'clientV2_1-infrastructure',
            'clientV3-endpoints',
            'clientV-infrastructure',
        ],
    }
    for config, virtualenvs in tox_commands.iteritems():
        for virtualenv in virtualenvs:
            call(['tox', '-c', config, '-e', virtualenv, '--notest'])


def run(circle_node_index):
    """Run test cases splitted in different nodes."""
    LOGGER.debug('### Running tests...')

    all_commands = [
        {REST_CONFIG: ['clientV1-endpoints', 'clientV1-infrastructure']},
        {REST_CONFIG: ['clientV2-endpoints']},
        {
            WORKFLOWS_CONFIG: ['py27'],
            REST_CONFIG: ['clientV2-infrastructure'],
        },
        {REST_CONFIG: ['clientV2_1-endpoints']},
        {REST_CONFIG: ['clientV3-endpoints']},
        {REST_CONFIG: ['clientV3-infrastructure']},
    ]

    if circle_node_index == 0:
        call([
            'flake8',
            'plugins/riemann-controller/',
            'workflows/',
            'rest-service/',
            'tests/',
        ])

    node_commands = all_commands[circle_node_index]
    for config, virtualenvs in node_commands.iteritems():
        for virtualenv in virtualenvs:
            call(['tox', '-c', config, '-e', virtualenv])


def parse_arguments():
    """Parse command line arguments.

    :return: Arguments parsed
    :rtype: :class:`argparse.Namespace`

    """
    parser = argparse.ArgumentParser(
        description='Run test cases and split them accross CircleCI nodes')
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

    # Install dependencies only in first node
    # This is because caching only happens in the first node
    if args.install_dependencies and circle_node_index == 0:
        install_dependencies()
    else:
        run(circle_node_index)
