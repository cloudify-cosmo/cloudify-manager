#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import sys
import logging
import shutil
import importlib
import traceback
import StringIO
from os import path
from flask.ext.restful import abort


def setup_logger(logger_name, logger_level=logging.DEBUG, handlers=None,
                 remove_existing_handlers=True):
    """
    :param logger_name: Name of the logger.
    :param logger_level: Level for the logger (not for specific handler).
    :param handlers: An optional list of handlers (formatter will be
                     overridden); If None, only a StreamHandler for
                     sys.stdout will be used.
    :param remove_existing_handlers: Determines whether to remove existing
                                     handlers before adding new ones
    :return: A logger instance.
    :rtype: Logger
    """

    logger = logging.getLogger(logger_name)

    if remove_existing_handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    if not handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handlers = [handler]

    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%d/%m/%Y %H:%M:%S')
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logger_level)
    return logger


def copy_resources(file_server_root, resources_path=None):
    if resources_path is None:
        resources_path = path.abspath(__file__)
        for i in range(3):
            resources_path = path.dirname(resources_path)
        resources_path = path.join(resources_path, 'resources')
    cloudify_resources = path.join(resources_path,
                                   'rest-service',
                                   'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root,
                                                  'cloudify'))


def get_class(class_path):
    """Returns a class from a string formatted as module:class"""
    if not class_path:
        raise ValueError('class path is missing or empty')

    if not isinstance(class_path, basestring):
        raise ValueError('class path is not a string')

    class_path = class_path.strip()
    if ':' not in class_path or class_path.count(':') > 1:
        raise ValueError('Invalid class path, expected format: '
                         'module:class')

    class_path_parts = class_path.split(':')
    class_module_str = class_path_parts[0].strip()
    class_name = class_path_parts[1].strip()

    if not class_module_str or not class_name:
        raise ValueError('Invalid class path, expected format: '
                         'module:class')

    module = importlib.import_module(class_module_str)
    if not hasattr(module, class_name):
        raise ValueError('module {0}, does not contain class {1}'
                         .format(class_module_str, class_name))

    return getattr(module, class_name)


def get_class_instance(class_path, properties=None):
    """Returns an instance of a class from a string formatted as module:class
    the given *args, **kwargs are passed to the instance's __init__"""
    if not properties:
        properties = {}
    try:
        cls = get_class(class_path)
        instance = cls(**properties)
    except Exception as e:
        exc_type, exc, traceback = sys.exc_info()
        raise RuntimeError('Failed to instantiate {0}, error: {1}'
                           .format(class_path, e)), None, traceback

    return instance


def abort_error(error, logger, hide_server_message=False):
    logger.info('{0}: {1}'.format(type(error).__name__, str(error)))
    s_traceback = StringIO.StringIO()
    if hide_server_message:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, file=s_traceback)
    else:
        traceback.print_exc(file=s_traceback)

    abort(error.http_code,
          message=str(error),
          error_code=error.error_code,
          server_traceback=s_traceback.getvalue())
