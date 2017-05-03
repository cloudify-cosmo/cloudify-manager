########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""Downgrade/upgrade database schema to target revision."""

import argparse
import logging
import os
import sys

import flask_migrate

from manager_rest.flask_utils import setup_flask_app


LOGGER = logging.getLogger(__name__)


def main():
    """Run migration command."""
    args = parse_arguments(sys.argv[1:])
    configure_logging(args['log_level'])

    setup_flask_app()
    directory = os.path.dirname(__file__)

    command = getattr(flask_migrate, args['command'])
    command(directory, args['revision'])


def parse_arguments(argv):
    """Parse command line arguments.

    :param argv: Command line arguments
    :type argv: list(str)
    :returns: Parsed arguments
    :rtype: argparse.Namespace

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'command',
        choices=['downgrade', 'upgrade'],
        help='Migration command',
    )
    parser.add_argument('revision', help='Target schema revision')

    log_levels = ['debug', 'info', 'warning', 'error', 'critical']
    parser.add_argument(
        '-l', '--log-level',
        dest='log_level',
        choices=log_levels,
        default='debug',
        help=('Log level. One of {0} or {1} '
              '(%(default)s by default)'
              .format(', '.join(log_levels[:-1]), log_levels[-1])))

    args = vars(parser.parse_args(argv))
    args['log_level'] = getattr(logging, args['log_level'].upper())
    return args


def configure_logging(log_level):
    """Configure logging based on command line argument.

    :param log_level: Log level passed form the command line
    :type log_level: int

    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Log to sys.stderr using log level
    # passed through command line
    log_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(threadName)s %(levelname)s: %(message)s')
    log_handler.setFormatter(formatter)
    log_handler.setLevel(log_level)
    root_logger.addHandler(log_handler)


if __name__ == '__main__':
    main()
