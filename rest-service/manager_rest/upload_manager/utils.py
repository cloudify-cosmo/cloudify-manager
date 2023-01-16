import json
import os
import shutil
import tarfile
import tempfile
import uuid
import zipfile

import requests
import wagon
import yaml
from flask import request
from setuptools import archive_util

from manager_rest import chunked, manager_exceptions
from manager_rest.constants import (SUPPORTED_ARCHIVE_TYPES)


def zip_dir(dir_to_zip, target_zip_path):
    zipf = zipfile.ZipFile(target_zip_path, 'w', zipfile.ZIP_DEFLATED)
    try:
        plugin_dir_base_name = os.path.basename(dir_to_zip)
        rootlen = len(dir_to_zip) - len(plugin_dir_base_name)
        for base, dirs, files in os.walk(dir_to_zip):
            for entry in files:
                fn = os.path.join(base, entry)
                zipf.write(fn, fn[rootlen:])
    finally:
        zipf.close()


def extract_file_to_file_server(archive_path, destination_root):
    """
    Extracting a package.

    :param destination_root: the root destination for the unzipped archive
    :param archive_path: the archive path
    :return: the full path for the extracted archive
    """
    # extract application to file server
    tempdir = tempfile.mkdtemp('-blueprint-submit')
    try:
        try:
            archive_util.unpack_archive(archive_path, tempdir)
        except archive_util.UnrecognizedFormat:
            raise manager_exceptions.BadParametersError(
                'Blueprint archive is of an unrecognized format. '
                'Supported formats are: {0}'
                .format(SUPPORTED_ARCHIVE_TYPES))
        archive_file_list = os.listdir(tempdir)
        if len(archive_file_list) != 1 or not os.path.isdir(
                os.path.join(tempdir, archive_file_list[0])):
            raise manager_exceptions.BadParametersError(
                'archive must contain exactly 1 directory')
        application_dir_base_name = archive_file_list[0]
        # generating temporary unique name for app dir, to allow multiple
        # uploads of apps with the same name (as it appears in the file
        # system, not the app name field inside the blueprint.
        # the latter is guaranteed to be unique).
        generated_app_dir_name = '{0}-{1}'.format(
            application_dir_base_name, uuid.uuid4())
        temp_application_dir = os.path.join(tempdir,
                                            application_dir_base_name)
        temp_application_target_dir = os.path.join(tempdir,
                                                   generated_app_dir_name)
        shutil.move(temp_application_dir, temp_application_target_dir)
        shutil.move(temp_application_target_dir, destination_root)
        return generated_app_dir_name
    finally:
        shutil.rmtree(tempdir)


def save_file_from_url(archive_target_path, url, data_type):
    if request.data or \
        'Transfer-Encoding' in request.headers or \
            'blueprint_archive' in request.files:
        raise manager_exceptions.BadParametersError(
            "Can pass {0} as only one of: URL via query parameters, "
            "request body, multi-form or chunked.".format(data_type))
    try:
        with requests.get(url, stream=True, timeout=(5, None)) as resp:
            resp.raise_for_status()
            with open(archive_target_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    except requests.exceptions.RequestException as e:
        raise manager_exceptions.BadParametersError(
            "Cannot fetch {0}: {1}".format(url, e))


def save_files_multipart(archive_target_path):
    inputs = {}
    for file_key in request.files:
        if file_key == 'inputs':
            content = request.files[file_key]
            # The file is a binary
            if 'application' in content.content_type:
                content_payload = _save_bytes(content)
                # Handling yaml
                if content.content_type == 'application/octet-stream':
                    inputs = yaml.safe_load(content_payload)
                # Handling json
                elif content.content_type == 'application/json':
                    inputs = json.load(content_payload)
            # The file is raw json
            elif 'text' in content.content_type:
                inputs = json.load(content)
        elif file_key == 'blueprint_archive':
            _save_bytes(request.files[file_key],
                        archive_target_path)
    return inputs


def _save_bytes(content, target_path=None):
    """
    content should support read() function if target isn't supplied,
    string rep is returned

    :param content:
    :param target_path:
    :return:
    """
    if not target_path:
        return content.getvalue().decode("utf-8")
    else:
        with open(target_path, 'wb') as f:
            f.write(content.read())


def save_file_from_chunks(archive_target_path, data_type):
    if request.data or 'blueprint_archive' in request.files:
        raise manager_exceptions.BadParametersError(
            "Can pass {0} as only one of: request body, multi-form or "
            "chunked.".format(data_type))
    with open(archive_target_path, 'w') as f:
        for buffered_chunked in chunked.decode(request.input_stream):
            f.write(buffered_chunked)


def load_plugin_package_json(wagon_source):
    try:
        return wagon.show(wagon_source)
    except (wagon.WagonError, tarfile.ReadError, zipfile.BadZipFile) as e:
        raise manager_exceptions.InvalidPluginError(
            'The provided wagon archive can not be read.\n{0}: {1}'
            .format(type(e).__name__, e))


def is_wagon_file(file_path):
    try:
        load_plugin_package_json(file_path)
    except Exception:
        return False
    else:
        return True


def load_plugin_extras(filenames):
    filename = _choose_plugin_yaml(filenames)
    if not filename:
        return {}

    with open(filename, 'r') as fh:
        try:
            plugin_yaml = yaml.safe_load(fh) or {}
        except yaml.YAMLError as e:
            raise manager_exceptions.InvalidPluginError(
                f"The provided plugin's description ({filename}) "
                f"can not be read.\n{e}")
    return {
        'blueprint_labels': _retrieve_labels(
            plugin_yaml.get('blueprint_labels')),
        'labels': _retrieve_labels(plugin_yaml.get('labels')),
        'resource_tags': plugin_yaml.get('resource_tags'),
    }


def _choose_plugin_yaml(filenames):
    if not filenames:
        return None
    for fn in filenames:
        if 'plugin.' in fn.lower():
            return fn
    return filenames[0]


def unpack_caravan(path, directory):
    if not tarfile.is_tarfile(path):
        return None

    try:
        with tarfile.open(path) as caravan:
            root_path = caravan.getmembers()[0].path
            caravan.extractall(directory)
    except tarfile.ReadError:
        return None

    with open(os.path.join(directory, root_path, 'METADATA')) as f:
        return json.load(f), root_path


def _retrieve_labels(labels):
    if not labels:
        return labels
    try:
        flattened = _flatten_labels_dict(labels)
    except AttributeError:
        raise manager_exceptions.InvalidPluginError(
            f"Invalid labels: {labels}")
    for k, v in flattened.items():
        if not isinstance(v, list):
            raise manager_exceptions.InvalidPluginError(
                f"Invalid labels: {labels}")
    return flattened


def _flatten_labels_dict(labels):
    """Flatten labels dictionary by dropping 'values' key."""
    flattened = {}
    for k, v in labels.items():
        flattened[k] = v.get('values')
    return flattened


def base_archive_filename(archive_filename):
    filename = archive_filename
    while True:
        filename, _, ext = filename.rpartition('.')
        if ext in ['tar', 'tgz', 'zip']:
            return filename
        if ext in ['bz2', 'gz', 'lzma', 'xz']:
            continue
        return archive_filename
