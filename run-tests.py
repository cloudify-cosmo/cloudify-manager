#!/usr/bin/env python

import argparse
import os

from subprocess import call

CIRCLE_NODE_INDEX = os.environ.get('CIRCLE_NODE_INDEX')
REST_CONFIG = './rest-service/tox.ini'
WORKFLOWS_CONFIG = './workflows/tox.ini'


def install_dependencies():
    print('### Installing dependencies...')

    if CIRCLE_NODE_INDEX == 0:
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


def run():
    print('### Running tests...')
    if CIRCLE_NODE_INDEX == 0:
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
    elif CIRCLE_NODE_INDEX == 1:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2-endpoints',
        ])
    elif CIRCLE_NODE_INDEX == 2:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2-infrastructure',
        ])
        call([
            'tox',
            '-c', WORKFLOWS_CONFIG,
        ])
    elif CIRCLE_NODE_INDEX == 3:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2_1-endpoints',
        ])
    elif CIRCLE_NODE_INDEX == 4:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV2_1-infrastructure',
        ])
    elif CIRCLE_NODE_INDEX == 5:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV3-endpoints',
        ])
    elif CIRCLE_NODE_INDEX == 6:
        call([
            'tox',
            '-c', REST_CONFIG,
            '-e', 'clientV3-infrastructure',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Run test cases and split them accross CircleCI nodes')
    parser.add_argument(
        '-i', '--install-dependencies',
        action='store_true',
        help='Install dependencies (do not run test cases)',
    )
    args = parser.parse_args()

    if args.install_dependencies:
        install_dependencies()
    else:
        run()
