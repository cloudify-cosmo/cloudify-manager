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
import contextlib
from urllib2 import urlopen, URLError

import sys
import logging
import shutil
import importlib
import tempfile
import traceback
import StringIO
import errno
from os import path, makedirs, listdir
import uuid

import json
from flask.ext.restful import abort
from setuptools import archive_util

from manager_rest import manager_exceptions
from manager_rest import chunked


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


def mkdirs(folder_path):
    try:
        makedirs(folder_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and path.isdir(folder_path):
            pass
        else:
            raise


def extract_blueprint_archive_to_mgr(archive_path, destination_root):
    """
    Extracting a package.

    :param destination_root: the root destination for the unzipped archive
    :param archive_path: the archive path
    :return: the full path for the extracted archive
    """
    # Importing this archives in the global scope causes import loop
    from manager_rest.resources import SUPPORTED_ARCHIVE_TYPES
    # extract application to file server
    tempdir = tempfile.mkdtemp('-blueprint-submit')
    try:
        try:
            archive_util.unpack_archive(archive_path, tempdir)
        except archive_util.UnrecognizedFormat:
            raise manager_exceptions.BadParametersError(
                    'Blueprint archive is of an unrecognized format. '
                    'Supported formats are: {0}'.format(
                            SUPPORTED_ARCHIVE_TYPES))
        archive_file_list = listdir(tempdir)
        if len(archive_file_list) != 1 or not path.isdir(
                path.join(tempdir, archive_file_list[0])):
            raise manager_exceptions.BadParametersError(
                    'archive must contain exactly 1 directory')
        application_dir_base_name = archive_file_list[0]
        # generating temporary unique name for app dir, to allow multiple
        # uploads of apps with the same name (as it appears in the file
        # system, not the app name field inside the blueprint.
        # the latter is guaranteed to be unique).
        generated_app_dir_name = '{0}-{1}'.format(
                application_dir_base_name, uuid.uuid4())
        temp_application_dir = path.join(tempdir,
                                         application_dir_base_name)
        temp_application_target_dir = path.join(tempdir,
                                                generated_app_dir_name)
        shutil.move(temp_application_dir, temp_application_target_dir)
        shutil.move(temp_application_target_dir, destination_root)
        return generated_app_dir_name
    finally:
        shutil.rmtree(tempdir)


def save_request_content_to_file(request, archive_target_path, url_key,
                                 data_type='unknown'):
    """
    Retrieves the file specified by the request to the local machine.

    :param request: the request received by the rest client
    :param archive_target_path: the target of the archive
    :param data_type: the kind of the data (e.g. 'blueprint')
    :param url_key: if the data is passed as a url to an online resource, the
    url_key specifies what header points to the requested url.
    :return: None
    """
    if url_key in request.args:
        if request.data or 'Transfer-Encoding' in request.headers:
            raise manager_exceptions.BadParametersError(
                    "Can't pass both a {0} URL via query parameters "
                    "and {0} data via the request body at the same time"
                    .format(data_type))
        data_url = request.args[url_key]
        try:
            with contextlib.closing(urlopen(data_url)) as urlf:
                with open(archive_target_path, 'w') as f:
                    f.write(urlf.read())
        except URLError:
            raise manager_exceptions.ParamUrlNotFoundError(
                    "URL {0} not found - can't download {1} archive"
                    .format(data_url, data_type))
        except ValueError:
            raise manager_exceptions.BadParametersError(
                    "URL {0} is malformed - can't download {1} archive"
                    .format(data_url, data_type))

    elif 'Transfer-Encoding' in request.headers:
        with open(archive_target_path, 'w') as f:
            for buffered_chunked in chunked.decode(request.input_stream):
                f.write(buffered_chunked)
    else:
        if not request.data:
            raise manager_exceptions.BadParametersError(
                    'Missing {0} archive in request body or '
                    '"{1}" in query parameters'.format(data_type,
                                                       url_key))
        uploaded_file_data = request.data
        with open(archive_target_path, 'w') as f:
            f.write(uploaded_file_data)


def create_filter_params_list_description(parameters, list_type):
    return [{'name': filter_val,
             'description': 'List {type} matching the \'{filter}\' '
                            'filter value'.format(type=list_type,
                                                  filter=filter_val),
             'required': False,
             'allowMultiple': False,
             'dataType': 'string',
             'defaultValue': None,
             'paramType': 'query'} for filter_val in parameters]


def read_json_file(file_path):
    with open(file_path) as f:
        return json.load(f)


def write_dict_to_json_file(file_path, dictionary):
    with open(file_path, 'w') as f:
        json.dump(dictionary, f)
