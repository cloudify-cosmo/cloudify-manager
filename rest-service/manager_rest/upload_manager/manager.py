import os
import tarfile
import uuid

import shutil
import zipfile
import tempfile

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
from manager_rest import config, manager_exceptions
from manager_rest.utils import current_tenant, unzip, files_in_folder, remove
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import (SUPPORTED_ARCHIVE_TYPES)
from manager_rest.upload_manager.storage import storage_client

from manager_rest.upload_manager.utils import (
    base_archive_filename,
    extract_file_to_file_server,
    is_wagon_file,
    load_plugin_extras,
    load_plugin_package_json,
    save_file_from_chunks,
    save_files_multipart,
    save_file_from_url,
    unpack_caravan,
    zip_dir,
)


UPLOADING_FOLDER_NAME = '.uploading'


def _do_upload_snapshot(snapshot_id, upload_path):
    save_file_locally_and_extract_inputs(
        upload_path,
        'snapshot_archive_url',
        'snapshot',
    )
    target_path = os.path.join(
        FILE_SERVER_SNAPSHOTS_FOLDER,
        snapshot_id,
        f'{snapshot_id}.zip',
    )
    storage_client().put(upload_path, target_path)


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
    save_file_locally_and_extract_inputs(
        upload_path,
        None,
        'blueprint')

    try:
        archive_type = get_archive_type(upload_path)
    except ArchiveTypeError as exc:
        raise manager_exceptions.BadParametersError(
            'Blueprint archive is of an unrecognized format. '
            'Supported formats are: {0}'.format(
                SUPPORTED_ARCHIVE_TYPES)) from exc

    target_path = os.path.join(
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        current_tenant.name,
        blueprint_id,
        f'{blueprint_id}.{archive_type}',
    )
    storage_client().put(upload_path, target_path)


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


def update_blueprint_icon_file(tenant_name, blueprint_id):
    with tempfile.NamedTemporaryFile(delete=False) as fh:
        tmp_file_name = fh.name
        save_file_content(tmp_file_name, 'blueprint_icon')
        _set_blueprints_icon(tenant_name, blueprint_id, tmp_file_name)
    if os.path.exists(tmp_file_name):
        os.remove(tmp_file_name)
    _update_blueprint_archive(tenant_name, blueprint_id)


def save_file_content(archive_target_path, data_type):
    if 'blueprint_archive' in request.files:
        raise manager_exceptions.BadParametersError(
            "Can't pass {0} both as URL via request body and multi-form"
            .format(data_type))
    uploaded_file_data = request.data
    with open(archive_target_path, 'wb') as fh:
        fh.write(uploaded_file_data)


def remove_blueprint_icon_file(tenant_name, blueprint_id):
    _set_blueprints_icon(tenant_name, blueprint_id)
    _update_blueprint_archive(tenant_name, blueprint_id)


def _set_blueprints_icon(tenant_name, blueprint_id, icon_path=None):
    blueprint_icon_path = os.path.join(
        FILE_SERVER_BLUEPRINTS_FOLDER,
        tenant_name,
        blueprint_id,
        BLUEPRINT_ICON_FILENAME,
    )
    if icon_path:
        storage_client().put(icon_path, blueprint_icon_path)
    else:
        storage_client().delete(blueprint_icon_path)


def _update_blueprint_archive(tenant_name, blueprint_id):
    file_server_root = config.instance.file_server_root
    archive_dir = os.path.join(
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        tenant_name,
        blueprint_id)
    blueprint_dir = os.path.join(
        FILE_SERVER_BLUEPRINTS_FOLDER,
        tenant_name,
        blueprint_id)
    archive_filename = storage_client().find(
        os.path.join(archive_dir, blueprint_id),
        SUPPORTED_ARCHIVE_TYPES
    )
    new_archive_path = base_archive_filename(archive_filename) + '.tar.gz'

    # Copy blueprint's files to local temporary directory
    with tempfile.TemporaryDirectory(dir=file_server_root) as tmpdir:
        os.chdir(tmpdir)
        os.mkdir('blueprint')
        for src_file_path in storage_client().list(blueprint_dir):
            file_rel_path = \
                src_file_path.replace(blueprint_dir, '').lstrip('/')
            dst_file_path = os.path.join(tmpdir, 'blueprint', file_rel_path)

            with storage_client().get(src_file_path) as tmp_file_name:
                dst_dir_path = os.path.dirname(file_rel_path)
                if dst_dir_path:
                    os.makedirs(
                        os.path.join(tmpdir, 'blueprint', dst_dir_path),
                        exist_ok=True,
                    )
                shutil.copy2(tmp_file_name, dst_file_path)

        with tempfile.NamedTemporaryFile(dir=file_server_root,
                                         delete=False) as fh:
            tmp_file_name = fh.name
            with tarfile.open(fh.name, "w:gz") as tar_handle:
                tar_handle.add('blueprint')
            storage_client().delete(archive_filename)
            storage_client().put(tmp_file_name, new_archive_path)
        if os.path.exists(tmp_file_name):
            os.remove(tmp_file_name)


def extract_blueprint_archive_to_file_server(blueprint_id, tenant):
    sm = get_resource_manager().sm
    file_server_root = config.instance.file_server_root
    local_path = os.path.join(
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        tenant,
        blueprint_id)
    blueprint_file_path = storage_client().find(
        os.path.join(local_path, blueprint_id),
        SUPPORTED_ARCHIVE_TYPES,
    )
    if not blueprint_file_path:
        error_msg = "Could not find blueprint's archive; " \
                    "Blueprint ID: {0}".format(blueprint_id)
        blueprint = sm.get(Blueprint, blueprint_id)
        blueprint.state = \
            BlueprintUploadState.FAILED_EXTRACTING_TO_FILE_SERVER
        blueprint.error = error_msg
        sm.update(blueprint)
        raise manager_exceptions.NotFoundError(error_msg)
    try:
        with storage_client().get(blueprint_file_path) as local_file_name:
            app_dir = extract_file_to_file_server(local_file_name,
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
        FILE_SERVER_BLUEPRINTS_FOLDER,
        tenant)
    bp_from = os.path.join(file_server_root, app_dir)
    bp_dir = os.path.join(tenant_dir, blueprint_id)
    try:
        # use os.rename - bp_from is already in file_server_root, i.e.
        # same filesystem as the target dir
        storage_client().put(bp_from, bp_dir)
    except OSError as e:  # e.g. directory not empty
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
        zip_dir(plugin_dir, target_zip_path)


def _store_plugin(plugin_id, wagon_path, yaml_paths):
    wagon_info = {
        'id': plugin_id,
        'blueprint_labels': None,
        'labels': None,
        'resource_tags': None,
    }

    wagon_info.update(load_plugin_package_json(wagon_path))
    wagon_info.update(load_plugin_extras(yaml_paths))

    plugin_dir = os.path.dirname(wagon_path)
    if yaml_paths:
        yaml_paths += create_bc_plugin_yaml(yaml_paths, plugin_dir)

    target_path = os.path.join(
        FILE_SERVER_PLUGINS_FOLDER,
        plugin_id,
    )
    storage_client().put(
        wagon_path,
        os.path.join(target_path, wagon_info['archive_name'])
    )
    for yaml_path in yaml_paths:
        storage_client().put(
            yaml_path,
            os.path.join(target_path, os.path.basename(yaml_path)),
        )
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
    save_file_locally_and_extract_inputs(
        archive_target_path,
        'plugin_archive_url',
        'plugin',
    )

    plugins = []
    if is_caravan(archive_target_path):
        metadata, root_path = unpack_caravan(archive_target_path, plugin_dir)
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
    elif is_wagon_file(archive_target_path):
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


def upload_plugin(data_id=None, **_):
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


def save_file_locally_and_extract_inputs(archive_target_path,
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
        save_file_from_url(archive_target_path,
                           request.args[url_key],
                           data_type)
    # handle receiving chunked blueprint
    elif 'Transfer-Encoding' in request.headers:
        save_file_from_chunks(archive_target_path, data_type)
    # handler receiving entire content through data
    elif request.data:
        save_file_content(archive_target_path, data_type)

    # handle inputs from form-data (for both the blueprint and inputs
    # in body in form-data format)
    if request.files:
        inputs = save_files_multipart(archive_target_path)

    return inputs
