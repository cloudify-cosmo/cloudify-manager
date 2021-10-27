#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
import traceback

from setuptools import archive_util
from flask import request, current_app
from flask_restful.reqparse import Argument
from flask_restful.inputs import boolean

from cloudify.models_states import SnapshotState, BlueprintUploadState
from manager_rest.manager_exceptions import ArchiveTypeError
from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_SNAPSHOTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    BLUEPRINT_ICON_FILENAME)
from manager_rest.archiving import get_archive_type
from manager_rest.storage.models import Blueprint, Plugin
from manager_rest import config, chunked, manager_exceptions, workflow_executor
from manager_rest.utils import (mkdirs,
                                get_formatted_timestamp,
                                current_tenant,
                                unzip,
                                files_in_folder,
                                remove)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import (SUPPORTED_ARCHIVE_TYPES)
from manager_rest.rest.rest_utils import get_args_and_verify_arguments

_PRIVATE_RESOURCE = 'private_resource'
_VISIBILITY = 'visibility'


class UploadedDataManager(object):

    def receive_uploaded_data(self, data_id=None, **kwargs):
        file_server_root = config.instance.file_server_root
        resource_target_path = tempfile.mktemp()
        try:
            additional_inputs = self._save_file_locally_and_extract_inputs(
                resource_target_path,
                self._get_data_url_key(),
                self._get_kind())
            doc, dest_file_name = self._prepare_and_process_doc(
                data_id,
                file_server_root,
                resource_target_path,
                additional_inputs=additional_inputs,
                **kwargs)
            if not os.path.isfile(resource_target_path):
                # if the archive is a folder, we're copying its content,
                # so there is no meaning to a specific archive file name...
                dest_file_name = None
            self._move_archive_to_uploaded_dir(doc.id,
                                               file_server_root,
                                               resource_target_path,
                                               dest_file_name=dest_file_name)
            return doc, 201
        finally:
            remove(resource_target_path)

    @classmethod
    def _extract_file_to_file_server(cls, archive_path, destination_root):
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

    @staticmethod
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

    @staticmethod
    def _save_file_from_chunks(archive_target_path, data_type):
        if request.data or 'blueprint_archive' in request.files:
            raise manager_exceptions.BadParametersError(
                "Can pass {0} as only one of: request body, multi-form or "
                "chunked.".format(data_type))
        with open(archive_target_path, 'w') as f:
            for buffered_chunked in chunked.decode(request.input_stream):
                f.write(buffered_chunked)

    @staticmethod
    def _save_file_content(archive_target_path, data_type):
        if 'blueprint_archive' in request.files:
            raise manager_exceptions.BadParametersError(
                "Can't pass {0} both as URL via request body and multi-form"
                .format(data_type))
        uploaded_file_data = request.data
        with open(archive_target_path, 'wb') as f:
            f.write(uploaded_file_data)

    def _save_files_multipart(self, archive_target_path):
        inputs = {}
        for file_key in request.files:
            if file_key == 'inputs':
                content = request.files[file_key]
                # The file is a binary
                if 'application' in content.content_type:
                    content_payload = self._save_bytes(content)
                    # Handling yaml
                    if content.content_type == 'application/octet-stream':
                        inputs = yaml.load(content_payload)
                    # Handling json
                    elif content.content_type == 'application/json':
                        inputs = json.load(content_payload)
                # The file is raw json
                elif 'text' in content.content_type:
                    inputs = json.load(content)
            elif file_key == 'blueprint_archive':
                self._save_bytes(request.files[file_key],
                                 archive_target_path)
        return inputs

    @staticmethod
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

    def _save_file_locally_and_extract_inputs(self,
                                              archive_target_path,
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
            self._save_file_from_url(archive_target_path,
                                     request.args[url_key],
                                     data_type)
        # handle receiving chunked blueprint
        elif 'Transfer-Encoding' in request.headers:
            self._save_file_from_chunks(archive_target_path, data_type)
        # handler receiving entire content through data
        elif request.data:
            self._save_file_content(archive_target_path, data_type)

        # handle inputs from form-data (for both the blueprint and inputs
        # in body in form-data format)
        if request.files:
            inputs = self._save_files_multipart(archive_target_path)

        return inputs

    def _move_archive_to_uploaded_dir(self,
                                      data_id,
                                      root_path,
                                      archive_path,
                                      dest_file_name=None):
        if not os.path.exists(archive_path):
            raise RuntimeError("Archive [{0}] doesn't exist - Cannot move "
                               "archive to uploaded {1}s "
                               "directory".format(archive_path,
                                                  self._get_kind()))
        uploaded_dir = os.path.join(
            root_path,
            self._get_target_dir_path(),
            data_id)
        if not os.path.isdir(uploaded_dir):
            os.makedirs(uploaded_dir)
        current_app.logger.info('uploading archive to: {0}'
                                .format(uploaded_dir))
        if os.path.isfile(archive_path):
            if not dest_file_name:
                try:
                    archive_type = self._get_archive_type(archive_path)
                except ArchiveTypeError:
                    raise manager_exceptions.BadParametersError(
                        'Blueprint archive is of an unrecognized format. '
                        'Supported formats are: {0}'.format(
                            SUPPORTED_ARCHIVE_TYPES))
                dest_file_name = '{0}.{1}'.format(data_id, archive_type)
            shutil.move(archive_path,
                        os.path.join(uploaded_dir, dest_file_name))
        else:
            for item in os.listdir(archive_path):
                shutil.copy(os.path.join(archive_path, item), uploaded_dir)
            shutil.rmtree(archive_path)

    @classmethod
    def _zip_dir(cls, dir_to_zip, target_zip_path):
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

    def _get_kind(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_data_url_key(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_target_dir_path(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_archive_type(self, archive_path):
        raise NotImplementedError('Subclass responsibility')

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 additional_inputs,
                                 **kwargs):
        raise NotImplementedError('Subclass responsibility')


class UploadedSnapshotsManager(UploadedDataManager):

    def _get_kind(self):
        return 'snapshot'

    def _get_data_url_key(self):
        return 'snapshot_archive_url'

    def _get_target_dir_path(self):
        return FILE_SERVER_SNAPSHOTS_FOLDER

    def _get_archive_type(self, archive_path):
        return 'zip'

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):
        return get_resource_manager().create_snapshot_model(
            data_id,
            status=SnapshotState.UPLOADED
        ), None


class UploadedBlueprintsManager(UploadedDataManager):

    def receive_uploaded_data(self, data_id=None, **kwargs):
        blueprint_url = None
        visibility = kwargs.get(_VISIBILITY, None)
        labels = kwargs.get('labels', None)
        override_failed_blueprint = kwargs.get('override_failed', False)

        args = get_args_and_verify_arguments([
            Argument('private_resource', type=boolean),
            Argument('application_file_name', default='')
        ])

        # Handle importing blueprint through url
        if self._get_data_url_key() in request.args:
            if request.data or \
                    'Transfer-Encoding' in request.headers or \
                    'blueprint_archive' in request.files:
                raise manager_exceptions.BadParametersError(
                    "Can pass {0} as only one of: URL via query parameters, "
                    "request body, multi-form or "
                    "chunked.".format(self._get_kind()))
            blueprint_url = request.args[self._get_data_url_key()]

        visibility = get_resource_manager().get_resource_visibility(
            Blueprint, data_id, visibility, args.private_resource)

        new_blueprint = self._prepare_and_process_doc(
            data_id,
            visibility,
            blueprint_url,
            application_file_name=args.application_file_name,
            override_failed_blueprint=override_failed_blueprint,
            labels=labels)
        return new_blueprint, 201

    def _prepare_and_process_doc(self, data_id, visibility, blueprint_url,
                                 application_file_name,
                                 override_failed_blueprint,
                                 labels=None):
        # Put a new blueprint entry in DB
        now = get_formatted_timestamp()
        rm = get_resource_manager()
        if override_failed_blueprint:
            new_blueprint = rm.sm.get(Blueprint, data_id)
            new_blueprint.plan = None
            new_blueprint.description = None
            new_blueprint.created_at = now
            new_blueprint.updated_at = now
            new_blueprint.main_file_name = None
            new_blueprint.visibility = visibility
            new_blueprint.state = BlueprintUploadState.PENDING
            rm.sm.update(new_blueprint)
        else:
            new_blueprint = rm.sm.put(Blueprint(
                plan=None,
                id=data_id,
                description=None,
                created_at=now,
                updated_at=now,
                main_file_name=None,
                visibility=visibility,
                state=BlueprintUploadState.PENDING
            ))

        if not blueprint_url:
            new_blueprint.state = BlueprintUploadState.UPLOADING
            rm.sm.update(new_blueprint)
            self.upload_archive_to_file_server(data_id)

        try:
            new_blueprint.upload_execution, messages = rm.upload_blueprint(
                data_id,
                application_file_name,
                blueprint_url,
                config.instance.file_server_root,   # for the import resolver
                labels=labels
            )
            rm.sm.update(new_blueprint)
            workflow_executor.execute_workflow(messages)
        except manager_exceptions.ExistingRunningExecutionError as e:
            new_blueprint.state = BlueprintUploadState.FAILED_UPLOADING
            new_blueprint.error = str(e)
            new_blueprint.error_traceback = traceback.format_exc()
            rm.sm.update(new_blueprint)
            self.cleanup_blueprint_archive_from_file_server(
                data_id, current_tenant.name)
            raise
        return new_blueprint

    def upload_archive_to_file_server(self, blueprint_id):
        file_server_root = config.instance.file_server_root
        archive_target_path = tempfile.mktemp()
        try:
            self._save_file_locally_and_extract_inputs(
                archive_target_path,
                None,
                self._get_kind())
            self._move_archive_to_uploaded_dir(
                blueprint_id,
                file_server_root,
                archive_target_path)
        except Exception as e:
            sm = get_resource_manager().sm
            blueprint = sm.get(Blueprint, blueprint_id)
            blueprint.state = BlueprintUploadState.FAILED_UPLOADING
            blueprint.error = str(e)
            sm.update(blueprint)
            self.cleanup_blueprint_archive_from_file_server(
                blueprint_id, blueprint.tenant.name)
            raise
        finally:
            remove(archive_target_path)

    def extract_blueprint_archive_to_file_server(self, blueprint_id, tenant):
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
            app_dir = self._extract_file_to_file_server(local_file_path,
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
        self._process_plugins(file_server_root, blueprint_id)

    def upgrade_icon_file(self, blueprint_id):
        icon_tmp_path = tempfile.mktemp()
        self._save_file_content(icon_tmp_path, 'blueprint_icon')
        self._set_blueprints_icon(blueprint_id, icon_tmp_path)
        remove(icon_tmp_path)
        self._upgrade_blueprint_archive(blueprint_id)

    @staticmethod
    def cleanup_blueprint_archive_from_file_server(blueprint_id, tenant):
        remove(os.path.join(config.instance.file_server_root,
                            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                            tenant,
                            blueprint_id))

    def _get_kind(self):
        return 'blueprint'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return os.path.join(
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER, current_tenant.name)

    def _get_archive_type(self, archive_path):
        return get_archive_type(archive_path)

    def _set_blueprints_icon(self, blueprint_id, icon_tmp_path=None):
        blueprint_icon_path = os.path.join(config.instance.file_server_root,
                                           FILE_SERVER_BLUEPRINTS_FOLDER,
                                           current_tenant.name,
                                           blueprint_id,
                                           BLUEPRINT_ICON_FILENAME)
        if icon_tmp_path:
            shutil.move(icon_tmp_path, blueprint_icon_path)
        else:
            os.remove(blueprint_icon_path)

    def _upgrade_blueprint_archive(self, blueprint_id):
        file_server_root = config.instance.file_server_root
        blueprint_dir = os.path.join(
            file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            current_tenant.name,
            blueprint_id)
        archive_dir = os.path.join(
            file_server_root,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            current_tenant.name,
            blueprint_id)
        # Filename will be like [BLUEPRINT_ID].tar.gz or [BLUEPRINT_ID].zip
        archive_filename = [fn for fn in os.listdir(archive_dir)
                            if fn.startswith(blueprint_id)][0]
        archive_path = os.path.join(archive_dir, archive_filename)
        with tempfile.TemporaryDirectory(dir=file_server_root) as tmpdir:
            # Copy blueprint files into `[tmpdir]/blueprint` directory
            os.chdir(tmpdir)
            os.mkdir(self._get_kind())
            for filename in os.listdir(blueprint_dir):
                srcname = os.path.join(blueprint_dir, filename)
                dstname = os.path.join(tmpdir, self._get_kind(), filename)
                shutil.copy2(srcname, dstname)
            # Create a new archive and substitute the old one
            with tempfile.NamedTemporaryFile(dir=file_server_root) as fh:
                with tarfile.open(fh.name, "w:gz") as tar_handle:
                    tar_handle.add(self._get_kind())
                shutil.copy2(fh.name, archive_path)
            os.chmod(archive_path, 0o644)

    @classmethod
    def _process_plugins(cls, file_server_root, blueprint_id):
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
            cls._zip_dir(plugin_dir, target_zip_path)


class UploadedBlueprintsValidator(UploadedBlueprintsManager):

    def receive_uploaded_data(self, data_id=None, **kwargs):
        blueprint_url = None
        # avoid clashing with existing blueprint names
        blueprint_id = data_id + uuid.uuid4().hex[:16]
        args = get_args_and_verify_arguments([
            Argument('application_file_name', default='')
        ])

        # Handle importing blueprint through url
        if self._get_data_url_key() in request.args:
            if request.data or \
                    'Transfer-Encoding' in request.headers or \
                    'blueprint_archive' in request.files:
                raise manager_exceptions.BadParametersError(
                    "Can pass {0} as only one of: URL via query parameters, "
                    "request body, multi-form or "
                    "chunked.".format(self._get_kind()))
            blueprint_url = request.args[self._get_data_url_key()]

        self._prepare_and_process_doc(
            blueprint_id,
            blueprint_url,
            application_file_name=args.application_file_name)
        return "", 204

    def _prepare_and_process_doc(self, data_id, blueprint_url,
                                 application_file_name):
        # Put a temporary blueprint entry in DB
        rm = get_resource_manager()
        now = get_formatted_timestamp()
        temp_blueprint = rm.sm.put(Blueprint(
            plan=None,
            id=data_id,
            description=None,
            created_at=now,
            updated_at=now,
            main_file_name=None,
            visibility=None,
            state=BlueprintUploadState.VALIDATING
        ))

        if not blueprint_url:
            self.upload_archive_to_file_server(data_id)

        try:
            temp_blueprint.upload_execution, messages = rm.upload_blueprint(
                data_id,
                application_file_name,
                blueprint_url,
                config.instance.file_server_root,   # for the import resolver
                validate_only=True,
            )
            workflow_executor.execute_workflow(messages)
        except manager_exceptions.ExistingRunningExecutionError:
            rm.sm.delete(temp_blueprint)
            self.cleanup_blueprint_archive_from_file_server(
                data_id, current_tenant.name)
            raise


class UploadedPluginsManager(UploadedDataManager):

    def _get_kind(self):
        return 'plugin'

    def _get_data_url_key(self):
        return 'plugin_archive_url'

    def _get_target_dir_path(self):
        return FILE_SERVER_PLUGINS_FOLDER

    def _get_archive_type(self, archive_path):
        return 'tar.gz'

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):

        # support previous implementation
        wagon_target_path = archive_target_path

        # handle the archive_target_path, which may be zip or wagon
        if not self._is_wagon_file(archive_target_path):
            if not zipfile.is_zipfile(archive_target_path):
                raise manager_exceptions.InvalidPluginError(
                    'input can be only a wagon or a zip file.')
            archive_name = unzip(archive_target_path,
                                 logger=current_app.logger)
            os.remove(archive_target_path)
            shutil.move(archive_name, archive_target_path)
            try:
                wagon_target_path, _ = \
                    self._verify_archive(archive_target_path)
            except RuntimeError as re:
                raise manager_exceptions.InvalidPluginError(str(re))

        args = get_args_and_verify_arguments([
            Argument('title'),
            Argument('private_resource', type=boolean),
            Argument('visibility')])

        visibility = kwargs.get(_VISIBILITY, None)
        new_plugin = self._create_plugin_from_archive(data_id,
                                                      args.title,
                                                      wagon_target_path,
                                                      args.private_resource,
                                                      visibility)
        filter_by_name = {'package_name': new_plugin.package_name}
        sm = get_resource_manager().sm
        plugins = sm.list(Plugin, filters=filter_by_name)

        for plugin in plugins:
            if plugin.archive_name == new_plugin.archive_name:
                raise manager_exceptions.ConflictError(
                    'a plugin archive by the name of {archive_name} already '
                    'exists for package with name {package_name} and version '
                    '{version}'.format(archive_name=new_plugin.archive_name,
                                       package_name=new_plugin.package_name,
                                       version=new_plugin.package_version))
        dest_path = new_plugin.archive_name
        sm.put(new_plugin)
        return new_plugin, dest_path

    def _is_wagon_file(self, file_path):
        try:
            self._load_plugin_package_json(file_path)
        except Exception:
            return False
        else:
            return True

    @staticmethod
    def _verify_archive(archive_path):
        wagons = files_in_folder(archive_path, '*.wgn')
        yamls = files_in_folder(archive_path, '*.yaml')
        if len(wagons) != 1 or len(yamls) != 1:
            raise RuntimeError("Archive must include one wgn file "
                               "and one yaml file")
        return wagons[0], yamls[0]

    def _create_plugin_from_archive(self,
                                    plugin_id,
                                    plugin_title,
                                    archive_path,
                                    private_resource,
                                    visibility):
        plugin = self._load_plugin_package_json(archive_path)
        build_props = plugin.get('build_server_os_properties')
        plugin_info = {'package_name': plugin.get('package_name'),
                       'archive_name': plugin.get('archive_name')}
        resource_manager = get_resource_manager()
        visibility = resource_manager.get_resource_visibility(
            Plugin,
            plugin_id,
            visibility,
            private_resource,
            plugin_info
        )

        return Plugin(
            id=plugin_id,
            title=plugin_title or plugin.get('package_name'),
            package_name=plugin.get('package_name'),
            package_version=plugin.get('package_version'),
            archive_name=plugin.get('archive_name'),
            package_source=plugin.get('package_source'),
            supported_platform=plugin.get('supported_platform'),
            distribution=build_props.get('distribution'),
            distribution_version=build_props.get('distribution_version'),
            distribution_release=build_props.get('distribution_release'),
            wheels=plugin.get('wheels'),
            excluded_wheels=plugin.get('excluded_wheels'),
            supported_py_versions=plugin.get('supported_python_versions'),
            uploaded_at=get_formatted_timestamp(),
            visibility=visibility
        )

    @staticmethod
    def _load_plugin_package_json(wagon_source):
        # Disable validation for now - seems to break in certain
        # circumstances.
        # if wagon.validate(wagon_source):
        #     # wagon returns a list of validation issues.
        #     raise manager_exceptions.InvalidPluginError(
        #         'the provided wagon can not be read.')

        try:
            return wagon.show(wagon_source)
        except wagon.WagonError as e:
            raise manager_exceptions.InvalidPluginError(
                'The provided wagon archive can not be read.\n{0}'
                .format(str(e)))


class UploadedCaravanManager(UploadedPluginsManager):
    class InvalidCaravanException(Exception):
        pass

    class Caravan(object):
        def __init__(self, caravan_path):
            self._caravan_path = caravan_path
            self._tempdir = tempfile.mkdtemp()
            self._cvn_dir = None
            self._metadata = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            remove(self._tempdir)

        def init_metadata(self):
            self._cvn_dir = self._extract(self._caravan_path, self._tempdir)
            self._metadata = self._get_metadata(self._cvn_dir)

        @property
        def root_dir(self):
            return self._cvn_dir

        @staticmethod
        def _get_metadata(path):
            try:
                with open(os.path.join(path, 'METADATA')) as metadata_file:
                    metadata = yaml.load(metadata_file)
            except Exception:
                raise UploadedCaravanManager.InvalidCaravanException(
                    'Failed to get caravan metadata'
                )
            return metadata

        @property
        def metadata(self):
            return self._metadata

        def __iter__(self):
            for wgn_path, yaml_path in self._metadata.items():
                yield os.path.join(self._cvn_dir, wgn_path), \
                    os.path.join(self._cvn_dir, yaml_path)

        def __getitem__(self, item):
            return os.path.join(self._cvn_dir, self._metadata[item])

        @staticmethod
        def _extract(src, dest):
            try:
                tarfile_ = tarfile.open(name=src)
            except tarfile.ReadError:
                raise UploadedCaravanManager.InvalidCaravanException(
                    'Failed to load caravan file'
                )
            try:
                # Get the top level dir
                root_dir = tarfile_.getmembers()[0]
                tarfile_.extractall(path=dest, members=tarfile_.getmembers())
            finally:
                tarfile_.close()
            return os.path.join(dest, root_dir.path)

    def _get_kind(self):
        return 'caravan'

    def receive_uploaded_data(self, data_id=None, **kwargs):
        file_server_root = config.instance.file_server_root
        resource_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            self._save_file_locally_and_extract_inputs(
                resource_target_path,
                self._get_data_url_key(),
                self._get_kind())
            with self.Caravan(resource_target_path) as caravan_instance:
                caravan_instance.init_metadata()
                plugins = self._prepare_and_process_doc(
                    file_server_root,
                    resource_target_path,
                    caravan_instance=caravan_instance,
                    **kwargs)
                docs = []
                for doc, plugin_dir in plugins:
                    self._move_archive_to_uploaded_dir(
                        doc.id,
                        file_server_root,
                        plugin_dir,
                    )
                    docs.append(doc)

            return docs, 201
        finally:
            remove(resource_target_path)

    def _prepare_and_process_doc(self,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):
        plugins = []
        caravan_ = kwargs['caravan_instance']
        for wgn_path, _ in caravan_:
            files_dir = os.path.dirname(wgn_path)
            archive_path = shutil.make_archive(
                os.path.join(caravan_.root_dir, os.path.basename(files_dir)),
                'zip',
                files_dir)

            try:
                new_plugin, _ = \
                    super(UploadedCaravanManager,
                          self)._prepare_and_process_doc(
                        str(uuid.uuid4()),
                        file_server_root,
                        archive_path,
                        **kwargs
                    )
                plugins.append((new_plugin, files_dir))
            except manager_exceptions.ConflictError:
                pass

        return plugins
