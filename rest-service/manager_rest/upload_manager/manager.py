import os
import json
import tarfile
import uuid

import wagon
import yaml
import shutil
import zipfile
import tempfile
import requests

from setuptools import archive_util
from flask import request, current_app

from cloudify.models_states import BlueprintUploadState
from manager_rest.manager_exceptions import ArchiveTypeError
from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_SNAPSHOTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    BLUEPRINT_ICON_FILENAME)
from manager_rest.dsl_back_compat import create_bc_plugin_yaml
from manager_rest.archiving import get_archive_type
from manager_rest.storage.models import Blueprint
from manager_rest import config, chunked, manager_exceptions
from manager_rest.utils import (mkdirs,
                                current_tenant,
                                unzip,
                                files_in_folder,
                                remove)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import (SUPPORTED_ARCHIVE_TYPES)


UPLOADING_FOLDER_NAME = '.uploading'


def _zip_dir(dir_to_zip, target_zip_path):
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


def _extract_file_to_file_server(archive_path, destination_root):
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


def _save_file_from_url(archive_target_path, url, data_type):
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


def _save_file_content(archive_target_path, data_type):
    if 'blueprint_archive' in request.files:
        raise manager_exceptions.BadParametersError(
            "Can't pass {0} both as URL via request body and multi-form"
            .format(data_type))
    uploaded_file_data = request.data
    with open(archive_target_path, 'wb') as f:
        f.write(uploaded_file_data)


def _save_files_multipart(archive_target_path):
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


def _save_file_locally_and_extract_inputs(archive_target_path,
                                          url_key,
                                          data_type='unknown'):
    """
    Retrieves the file specified by the request to the local machine.

    :param archive_target_path: the target of the archive
    :param data_type: the kind of the data (e.g. 'blueprint')
    :param url_key: if the data is passed as a url to an online resource,
    the url_key specifies what header points to the requested url.
    :return: None
    """
    inputs = {}
    # Handling importing blueprint through url
    if url_key in request.args:
        _save_file_from_url(archive_target_path,
                            request.args[url_key],
                            data_type)
    # handle receiving chunked blueprint
    elif 'Transfer-Encoding' in request.headers:
        _save_file_from_chunks(archive_target_path, data_type)
    # handler receiving entire content through data
    elif request.data:
        _save_file_content(archive_target_path, data_type)

    # handle inputs from form-data (for both the blueprint and inputs
    # in body in form-data format)
    if request.files:
        inputs = _save_files_multipart(archive_target_path)

    return inputs


def _save_file_from_chunks(archive_target_path, data_type):
    if request.data or 'blueprint_archive' in request.files:
        raise manager_exceptions.BadParametersError(
            "Can pass {0} as only one of: request body, multi-form or "
            "chunked.".format(data_type))
    with open(archive_target_path, 'w') as f:
        for buffered_chunked in chunked.decode(request.input_stream):
            f.write(buffered_chunked)


def _do_upload_snapshot(snapshot_id, upload_path):
    _save_file_locally_and_extract_inputs(
        upload_path,
        'snapshot_archive_url',
        'snapshot',
    )

    target_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_SNAPSHOTS_FOLDER,
        snapshot_id,
        f'{snapshot_id}.zip',
    )
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.move(upload_path, target_path)


def upload_snapshot(snapshot_id):
    upload_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_SNAPSHOTS_FOLDER,
        UPLOADING_FOLDER_NAME,
        snapshot_id,
    )
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    try:
        return _do_upload_snapshot(snapshot_id, upload_path)
    finally:
        shutil.rmtree(upload_path, ignore_errors=True)


def _do_upload_blueprint(blueprint_id, upload_path):
    _save_file_locally_and_extract_inputs(
        upload_path,
        None,
        'blueprint')

    try:
        archive_type = get_archive_type(upload_path)
    except ArchiveTypeError:
        raise manager_exceptions.BadParametersError(
            'Blueprint archive is of an unrecognized format. '
            'Supported formats are: {0}'.format(
                SUPPORTED_ARCHIVE_TYPES))

    target_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        current_tenant.name,
        blueprint_id,
        f'{blueprint_id}.{archive_type}',
    )
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.move(upload_path, target_path)


def upload_blueprint_archive_to_file_server(blueprint_id):
    upload_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        UPLOADING_FOLDER_NAME,
        current_tenant.name,
        blueprint_id,
    )
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    try:
        return _do_upload_blueprint(blueprint_id, upload_path)
    finally:
        shutil.rmtree(upload_path, ignore_errors=True)


def cleanup_blueprint_archive_from_file_server(blueprint_id, tenant):
    remove(os.path.join(config.instance.file_server_root,
                        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                        tenant,
                        blueprint_id))


def update_blueprint_icon_file(self, tenant_name, blueprint_id):
    icon_tmp_path = tempfile.mktemp()
    _save_file_content(icon_tmp_path, 'blueprint_icon')
    _set_blueprints_icon(tenant_name, blueprint_id, icon_tmp_path)
    remove(icon_tmp_path)
    _update_blueprint_archive(tenant_name, blueprint_id)


def remove_blueprint_icon_file(self, tenant_name, blueprint_id):
    _set_blueprints_icon(tenant_name, blueprint_id)
    _update_blueprint_archive(tenant_name, blueprint_id)


def _set_blueprints_icon(tenant_name, blueprint_id, icon_path=None):
    blueprint_icon_path = os.path.join(config.instance.file_server_root,
                                       FILE_SERVER_BLUEPRINTS_FOLDER,
                                       tenant_name,
                                       blueprint_id,
                                       BLUEPRINT_ICON_FILENAME)
    if icon_path:
        shutil.move(icon_path, blueprint_icon_path)
    else:
        os.remove(blueprint_icon_path)


def _update_blueprint_archive(tenant_name, blueprint_id):
    file_server_root = config.instance.file_server_root
    blueprint_dir = os.path.join(
        file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        tenant_name,
        blueprint_id)
    archive_dir = os.path.join(
        file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        tenant_name,
        blueprint_id)
    # Filename will be like [BLUEPRINT_ID].tar.gz or [BLUEPRINT_ID].zip
    archive_filename = [fn for fn in os.listdir(archive_dir)
                        if fn.startswith(blueprint_id)][0]
    base_filename = _base_archive_filename(archive_filename)
    orig_archive_path = os.path.join(archive_dir, archive_filename)
    new_archive_path = os.path.join(archive_dir, f'{base_filename}.tar.gz')
    with tempfile.TemporaryDirectory(dir=file_server_root) as tmpdir:
        # Copy blueprint files into `[tmpdir]/blueprint` directory
        os.chdir(tmpdir)
        os.mkdir('blueprint')
        for filename in os.listdir(blueprint_dir):
            srcname = os.path.join(blueprint_dir, filename)
            dstname = os.path.join(tmpdir, 'blueprint', filename)
            if os.path.isdir(srcname):
                shutil.copytree(srcname, dstname)
            else:
                shutil.copy2(srcname, dstname)
        # Create a new archive and substitute the old one
        with tempfile.NamedTemporaryFile(dir=file_server_root) as fh:
            with tarfile.open(fh.name, "w:gz") as tar_handle:
                tar_handle.add('blueprint')
            shutil.copy2(fh.name, new_archive_path)
            os.remove(orig_archive_path)
        os.chmod(new_archive_path, 0o644)


def extract_blueprint_archive_to_file_server(blueprint_id, tenant):
    sm = get_resource_manager().sm
    file_server_root = config.instance.file_server_root
    local_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        tenant,
        blueprint_id)
    for arc_type in SUPPORTED_ARCHIVE_TYPES:
        # attempting to find the archive file on the file system
        local_file_path = os.path.join(
            local_path,
            '{0}.{1}'.format(blueprint_id, arc_type)
        )
        if os.path.isfile(local_file_path):
            break
    else:
        error_msg = "Could not find blueprint's archive; " \
                    "Blueprint ID: {0}".format(blueprint_id)
        blueprint = sm.get(Blueprint, blueprint_id)
        blueprint.state = \
            BlueprintUploadState.FAILED_EXTRACTING_TO_FILE_SERVER
        blueprint.error = error_msg
        sm.update(blueprint)
        raise manager_exceptions.NotFoundError(error_msg)
    try:
        app_dir = _extract_file_to_file_server(local_file_path,
                                               file_server_root)
    except Exception as e:
        blueprint = sm.get(Blueprint, blueprint_id)
        blueprint.state = \
            BlueprintUploadState.FAILED_EXTRACTING_TO_FILE_SERVER
        blueprint.error = str(e)
        sm.update(blueprint)
        remove(local_path)
        raise e

    tenant_dir = os.path.join(
        file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        tenant)
    mkdirs(tenant_dir)
    bp_from = os.path.join(file_server_root, app_dir)
    bp_dir = os.path.join(tenant_dir, blueprint_id)
    try:
        # use os.rename - bp_from is already in file_server_root, ie.
        # same filesystem as the target dir
        os.rename(bp_from, bp_dir)
    except OSError as e:  # eg. directory not empty
        shutil.rmtree(bp_from)
        raise manager_exceptions.ConflictError(str(e))
    _process_blueprint_plugins(file_server_root, blueprint_id)


def _process_blueprint_plugins(file_server_root, blueprint_id):
    plugins_directory = os.path.join(
        file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        current_tenant.name,
        blueprint_id,
        "plugins")
    if not os.path.isdir(plugins_directory):
        return
    plugins = [os.path.join(plugins_directory, directory)
               for directory in os.listdir(plugins_directory)
               if os.path.isdir(os.path.join(plugins_directory,
                                             directory))]

    for plugin_dir in plugins:
        final_zip_name = '{0}.zip'.format(os.path.basename(plugin_dir))
        target_zip_path = os.path.join(plugins_directory, final_zip_name)
        _zip_dir(plugin_dir, target_zip_path)


def _load_plugin_package_json(wagon_source):
    try:
        return wagon.show(wagon_source)
    except (wagon.WagonError, tarfile.ReadError, zipfile.BadZipFile) as e:
        raise manager_exceptions.InvalidPluginError(
            'The provided wagon archive can not be read.\n{0}: {1}'
            .format(type(e).__name__, e))


def _is_wagon_file(file_path):
    try:
        _load_plugin_package_json(file_path)
    except Exception:
        return False
    else:
        return True


def _load_plugin_extras(filenames):
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


def _unpack_caravan(path, directory):
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


def _store_plugin(plugin_id, wagon_path, yaml_paths):
    wagon_info = {
        'id': plugin_id,
        'blueprint_labels': None,
        'labels': None,
        'resource_tags': None,
    }

    wagon_info.update(_load_plugin_package_json(wagon_path))
    wagon_info.update(_load_plugin_extras(yaml_paths))

    plugin_dir = os.path.dirname(wagon_path)
    if yaml_paths:
        yaml_paths += create_bc_plugin_yaml(yaml_paths, plugin_dir)

    target_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_PLUGINS_FOLDER,
        plugin_id,
    )
    os.makedirs(target_path, exist_ok=True)
    shutil.move(
        wagon_path,
        os.path.join(target_path, wagon_info['archive_name']),
    )
    for yaml_path in yaml_paths:
        shutil.move(
            yaml_path,
            os.path.join(target_path, os.path.basename(yaml_path)),
        )
    os.chmod(target_path, 0o755)
    return wagon_info


def is_caravan(path):
    if not tarfile.is_tarfile(path):
        return False

    with tarfile.open(path) as caravan:
        members = caravan.getmembers()
        if not members:
            return False
        root_dir = members[0]
        try:
            caravan.getmember(os.path.join(root_dir.path, 'METADATA'))
        except KeyError:
            return False
        else:
            return True


def _do_upload_plugin(data_id, plugin_dir):
    archive_target_path = os.path.join(plugin_dir, 'plugin')
    _save_file_locally_and_extract_inputs(
        archive_target_path,
        'plugin_archive_url',
        'plugin',
    )

    plugins = []
    if is_caravan(archive_target_path):
        metadata, root_path = _unpack_caravan(archive_target_path, plugin_dir)
        for wagon_path, yaml_path in metadata.items():
            wagon_path = os.path.join(
                plugin_dir,
                root_path,
                wagon_path,
            )
            yaml_path = os.path.join(
                plugin_dir,
                root_path,
                yaml_path,
            )
            plugin_desc = (
                str(uuid.uuid4()),
                wagon_path,
                [yaml_path],
            )
            plugins.append(plugin_desc)
    elif _is_wagon_file(archive_target_path):
        plugins = [(data_id, archive_target_path, [])]
    elif zipfile.is_zipfile(archive_target_path):
        plugin_dir = os.path.dirname(archive_target_path)
        unzip(
            archive_target_path,
            destination=plugin_dir,
            logger=current_app.logger,
        )
        wagons = files_in_folder(plugin_dir, '*.wgn')
        yamls = files_in_folder(plugin_dir, '*.yaml')
        if len(wagons) != 1 or len(yamls) < 1:
            raise manager_exceptions.InvalidPluginError(
                "Archive must include one wgn file "
                "and at least one yaml file"
            )
        plugins = [(data_id, wagons[0], yamls)]
    else:
        raise manager_exceptions.InvalidPluginError(
            'input can be only a wagon or a zip file.')

    wagons = []
    for plugin_id, wagon_path, yamls in plugins:
        wagon_info = _store_plugin(plugin_id, wagon_path, yamls)
        wagons.append(wagon_info)
    return wagons


def upload_plugin(data_id=None, **kwargs):
    data_id = data_id or request.args.get('id') or str(uuid.uuid4())

    upload_path = os.path.join(
        config.instance.file_server_root,
        FILE_SERVER_PLUGINS_FOLDER,
        UPLOADING_FOLDER_NAME,
        data_id,
    )
    os.makedirs(upload_path, exist_ok=True)
    try:
        return _do_upload_plugin(data_id, upload_path)
    finally:
        shutil.rmtree(upload_path, ignore_errors=True)


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


def _base_archive_filename(archive_filename):
    while True:
        filename, _, ext = archive_filename.rpartition('.')
        if ext in ['tar', 'tgz', 'zip']:
            return filename
        if ext in ['bz2', 'gz', 'lzma', 'xz']:
            continue
        return archive_filename
