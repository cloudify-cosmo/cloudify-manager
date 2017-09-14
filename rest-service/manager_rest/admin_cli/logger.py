########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import os
import copy
import logging
import logging.config


DEFAULT_LOG_FILE = os.path.join('/var', 'log', 'cloudify', 'admin_cli.log')

VERBOSE = 1
NO_VERBOSE = 0

verbosity_level = NO_VERBOSE

_lgr = None


LOGGER = {
    "version": 1,
    "formatters": {
        "file": {
            "format": "%(asctime)s [%(levelname)s] %(message)s"
        },
        "console": {
            "format": "%(message)s"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "maxBytes": "5000000",
            "backupCount": "20"
        },
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "console"
        }
    }
}


def get_logger():
    if not _lgr:
        configure_loggers()
    return _lgr


def configure_loggers():
    # first off, configure defaults
    # to enable the use of the logger
    # even before the init was executed.
    # add handlers to the main logger
    logger_dict = copy.deepcopy(LOGGER)
    logger_dict['loggers'] = {
        'manager_rest.admin_cli.main': {
            'handlers': list(logger_dict['handlers'].keys())
        }
    }
    logger_dict['handlers']['file']['filename'] = DEFAULT_LOG_FILE
    logfile_dir = os.path.dirname(DEFAULT_LOG_FILE)
    if not os.path.exists(logfile_dir):
        os.makedirs(logfile_dir)

    logging.config.dictConfig(logger_dict)
    logging.getLogger('manager_rest.admin_cli.main').setLevel(logging.INFO)

    global _lgr
    _lgr = logging.getLogger('manager_rest.admin_cli.main')


def set_global_verbosity_level(verbose):
    """Set the global verbosity level.
    """
    global verbosity_level
    verbosity_level = verbose
    if verbosity_level >= VERBOSE:
        _lgr.setLevel(logging.DEBUG)


def get_global_verbosity():
    """Return the globally set verbosity
    """
    return verbosity_level
