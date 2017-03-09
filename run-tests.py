#!/usr/bin/env python

import argparse
import os

from subprocess import call

REST_CONFIG = './rest-service/tox.ini'
WORKFLOWS_CONFIG = './workflows/tox.ini'


def install_dependencies():
    """Install dependencies for each tox virtual environment."""
    print('### Installing dependencies...')

    call(['pip', 'install', 'flake8'])
    call(['tox', '-c', WORKFLOWS_CONFIG, '--notest'])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV1-endpoints',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV1-infrastructure',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV2-endpoints',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV2-infrastructure',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV2_1-endpoints',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV2_1-infrastructure',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV3-endpoints',
        '--notest',
    ])
    call([
        'tox',
        '-c', REST_CONFIG,
        '-e', 'clientV3-infrastructure',
        '--notest',
    ])


def run(circle_node_index):
    """Run test cases splitted in different nodes."""
    print('### Running tests...')
    if circle_node_index == 0:
        call([
            'flake8',
            'plugins/riemann-controller/',
            'workflows/',
            'rest-service/',
            'tests/',
        ])
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV1-endpoints',
        ])
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV1-infrastructure',
        ])
    elif circle_node_index == 1:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2-endpoints',
        ])
    elif circle_node_index == 2:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2-infrastructure',
        ])
        call([
            'tox',
            '-c', WORKFLOWS_CONFIG,
        ])
    elif circle_node_index == 3:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2_1-endpoints',
        ])
    elif circle_node_index == 4:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2_1-infrastructure',
        ])
    elif circle_node_index == 5:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV3-endpoints',
        ])
    elif circle_node_index == 6:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV3-infrastructure',
        ])


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

    circle_node_index = int(os.environ['CIRCLE_NODE_INDEX'])

    # Install dependencies only in first node
    # This is because caching only happens in the first node
    if args.install_dependencies and circle_node_index == 0:
        install_dependencies()
    else:
        run(circle_node_index)
