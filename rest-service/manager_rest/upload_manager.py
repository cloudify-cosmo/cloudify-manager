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
import uuid
import yaml
import urllib
import shutil
import zipfile
import tarfile
import tempfile
import contextlib
from os import path
from setuptools import archive_util
from urllib2 import urlopen, URLError

from flask import request, current_app
from flask_restful import types
from flask_restful.reqparse import RequestParser

from manager_rest.constants import (FILE_SERVER_PLUGINS_FOLDER,
                                    FILE_SERVER_SNAPSHOTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)

from manager_rest.deployment_update.manager import \
    get_deployment_updates_manager
from manager_rest.archiving import get_archive_type
from manager_rest.storage.models import Plugin
from manager_rest.storage.models_states import SnapshotState
from manager_rest import config, chunked, manager_exceptions
from manager_rest.utils import mkdirs, get_formatted_timestamp
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import (CONVENTION_APPLICATION_BLUEPRINT_FILE,
                                    SUPPORTED_ARCHIVE_TYPES,
                                    CURRENT_TENANT_CONFIG)


class UploadedDataManager(object):

    def receive_uploaded_data(self, data_id):
        file_server_root = config.instance.file_server_root
        resource_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            additional_inputs = self._save_file_locally_and_extract_inputs(
                    resource_target_path,
                    self._get_data_url_key(),
                    self._get_kind())
            doc, dest_file_name = self._prepare_and_process_doc(
                data_id,
                file_server_root,
                resource_target_path,
                additional_inputs=additional_inputs)
            self._move_archive_to_uploaded_dir(doc.id,
                                               file_server_root,
                                               resource_target_path,
                                               dest_file_name=dest_file_name)

            return doc, 201
        finally:
            if os.path.exists(resource_target_path):
                os.remove(resource_target_path)

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
                        'Supported formats are: {0}'.format(
                                SUPPORTED_ARCHIVE_TYPES))
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
    def _save_file_from_url(archive_target_path, data_url, data_type):
        if any([request.data,
                'Transfer-Encoding' in request.headers,
                'blueprint_archive' in request.files]):
            raise manager_exceptions.BadParametersError(
                "Can't pass both a {0} URL via query parameters, request body"
                ", multi-form and chunked.".format(data_type))
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

    @staticmethod
    def _save_file_from_chunks(archive_target_path, data_type):
        if any([request.data,
                'blueprint_archive' in request.files]):
            raise manager_exceptions.BadParametersError(
                "Can't pass both a {0} URL via request body , multi-form "
                "and chunked.".format(data_type))
        with open(archive_target_path, 'w') as f:
            for buffered_chunked in chunked.decode(request.input_stream):
                f.write(buffered_chunked)

    @staticmethod
    def _save_file_content(archive_target_path, data_type):
        if 'blueprint_archive' in request.files:
            raise manager_exceptions.BadParametersError(
                "Can't pass both a {0} URL via request body , multi-form"
                .format(data_type))
        uploaded_file_data = request.data
        with open(archive_target_path, 'w') as f:
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
        archive_type = self._get_archive_type(archive_path)
        if not dest_file_name:
            dest_file_name = '{0}.{1}'.format(data_id, archive_type)
        shutil.move(archive_path,
                    os.path.join(uploaded_dir, dest_file_name))

    def _get_kind(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_data_url_key(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_target_dir_path(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_archive_type(self, archive_path):
        raise NotImplementedError('Subclass responsibility')

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path, additional_inputs):
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

    @staticmethod
    def _get_args():
        args_parser = RequestParser()
        args_parser.add_argument('private_resource',
                                 type=types.boolean,
                                 default=False)
        return args_parser.parse_args()

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):
        args = self._get_args()
        return get_resource_manager().create_snapshot_model(
            data_id,
            status=SnapshotState.UPLOADED,
            private_resource=args.private_resource
        ), None


class UploadedBlueprintsDeploymentUpdateManager(UploadedDataManager):

    def _get_kind(self):
        return 'deployment'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return os.path.join(FILE_SERVER_DEPLOYMENTS_FOLDER,
                            current_app.config[CURRENT_TENANT_CONFIG].name)

    def _get_archive_type(self, archive_path):
        return get_archive_type(archive_path)

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 additional_inputs=None):
        application_dir = self._extract_file_to_file_server(
            archive_target_path,
            file_server_root
        )
        return self._prepare_and_submit_blueprint(
                file_server_root,
                application_dir,
                data_id,
                additional_inputs), archive_target_path

    def _move_archive_to_uploaded_dir(self, *args, **kwargs):
        pass

    @classmethod
    def _prepare_and_submit_blueprint(cls,
                                      file_server_root,
                                      app_dir,
                                      deployment_id,
                                      additional_inputs=None):

        app_dir, app_file_name = \
            cls._extract_application_file(file_server_root, app_dir)

        # add to deployment update manager (will also dsl_parse it)
        try:
            cls._process_plugins(file_server_root, app_dir)
            update = get_deployment_updates_manager().stage_deployment_update(
                    deployment_id,
                    app_dir,
                    app_file_name,
                    additional_inputs=additional_inputs or {}
                )

            # Moving the contents of the app dir to the dest dir, while
            # overwriting any file encountered

            # create the destination root dir
            file_server_deployment_root = \
                os.path.join(file_server_root,
                             FILE_SERVER_DEPLOYMENTS_FOLDER,
                             current_app.config[CURRENT_TENANT_CONFIG].name,
                             deployment_id)

            app_root_dir = os.path.join(file_server_root, app_dir)

            for root, dirs, files in os.walk(app_root_dir):
                # Creates a corresponding dir structure in the deployment dir
                dest_rel_dir = os.path.relpath(root, app_root_dir)
                dest_dir = os.path.abspath(
                        os.path.join(file_server_deployment_root,
                                     dest_rel_dir))
                mkdirs(dest_dir)

                # Calculate source dir
                source_dir = os.path.join(file_server_root, app_dir, root)

                for file_name in files:
                    source_file = os.path.join(source_dir, file_name)
                    relative_dest_path = os.path.relpath(source_file,
                                                         app_root_dir)
                    dest_file = os.path.join(file_server_deployment_root,
                                             relative_dest_path)
                    shutil.copy(source_file, dest_file)

            return update
        except Exception:
            shutil.rmtree(os.path.join(file_server_root, app_dir))
            raise

    @classmethod
    def _extract_application_file(cls, file_server_root, application_dir):

        full_application_dir = os.path.join(file_server_root, application_dir)

        if 'application_file_name' in request.args:
            application_file_name = urllib.unquote(
                    request.args['application_file_name']).decode('utf-8')
            application_file = os.path.join(full_application_dir,
                                            application_file_name)
            if not os.path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                        '{0} does not exist in the application '
                        'directory'.format(application_file_name)
                )
        else:
            application_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE
            application_file = os.path.join(full_application_dir,
                                            application_file_name)
            if not os.path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                        'application directory is missing blueprint.yaml and '
                        'application_file_name query parameter was not passed')

        # return relative path from the file server root since this path
        # is appended to the file server base uri
        return application_dir, application_file_name

    @classmethod
    def _process_plugins(cls, file_server_root, app_dir):
        plugins_directory = os.path.join(file_server_root, app_dir, 'plugins')
        if not os.path.isdir(plugins_directory):
            return
        plugins = [os.path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if os.path.isdir(os.path.join(plugins_directory,
                                                 directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(os.path.basename(plugin_dir))
            target_zip_path = os.path.join(file_server_root, app_dir,
                                           'plugins', final_zip_name)
            cls._zip_dir(plugin_dir, target_zip_path)

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


class UploadedBlueprintsManager(UploadedDataManager):

    def _get_kind(self):
        return 'blueprint'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return os.path.join(
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            current_app.config[CURRENT_TENANT_CONFIG].name)

    def _get_archive_type(self, archive_path):
        return get_archive_type(archive_path)

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):
        application_dir = self._extract_file_to_file_server(
                archive_target_path,
                file_server_root
            )
        return self._prepare_and_submit_blueprint(file_server_root,
                                                  application_dir,
                                                  data_id), None

    @classmethod
    def _process_plugins(cls, file_server_root, blueprint_id):
        plugins_directory = path.join(
            file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            current_app.config[CURRENT_TENANT_CONFIG].name,
            blueprint_id,
            "plugins")
        if not path.isdir(plugins_directory):
            return
        plugins = [path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if path.isdir(path.join(plugins_directory, directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(path.basename(plugin_dir))
            target_zip_path = path.join(plugins_directory, final_zip_name)
            cls._zip_dir(plugin_dir, target_zip_path)

    @classmethod
    def _zip_dir(cls, dir_to_zip, target_zip_path):
        zipf = zipfile.ZipFile(target_zip_path, 'w', zipfile.ZIP_DEFLATED)
        try:
            plugin_dir_base_name = path.basename(dir_to_zip)
            rootlen = len(dir_to_zip) - len(plugin_dir_base_name)
            for base, dirs, files in os.walk(dir_to_zip):
                for entry in files:
                    fn = os.path.join(base, entry)
                    zipf.write(fn, fn[rootlen:])
        finally:
            zipf.close()

    @classmethod
    def _get_args(cls):
        args_parser = RequestParser()
        args_parser.add_argument('private_resource',
                                 type=types.boolean,
                                 default=False)
        args_parser.add_argument('application_file_name', type=str, default='')
        return args_parser.parse_args()

    @classmethod
    def _prepare_and_submit_blueprint(cls, file_server_root,
                                      app_dir,
                                      blueprint_id):

        args = cls._get_args()
        app_dir, app_file_name = cls._extract_application_file(
            file_server_root, app_dir, args.application_file_name)

        # add to blueprints manager (will also dsl_parse it)
        try:
            blueprint = get_resource_manager().publish_blueprint(
                app_dir,
                app_file_name,
                file_server_root,
                blueprint_id,
                private_resource=args.private_resource
            )

            # moving the app directory in the file server to be under a
            # directory named after the blueprint id
            tenant_dir = os.path.join(
                file_server_root,
                FILE_SERVER_BLUEPRINTS_FOLDER,
                current_app.config[CURRENT_TENANT_CONFIG].name)
            mkdirs(tenant_dir)
            shutil.move(os.path.join(file_server_root, app_dir),
                        os.path.join(tenant_dir, blueprint.id))
            cls._process_plugins(file_server_root, blueprint.id)
            return blueprint
        except manager_exceptions.DslParseException, ex:
            shutil.rmtree(os.path.join(file_server_root, app_dir))
            raise manager_exceptions.InvalidBlueprintError(
                'Invalid blueprint - {0}'.format(ex.message))

    @classmethod
    def _extract_application_file(cls,
                                  file_server_root,
                                  application_dir,
                                  application_file_name):

        full_application_dir = path.join(file_server_root, application_dir)

        if application_file_name:
            application_file_name = urllib.unquote(
                application_file_name).decode('utf-8')
            application_file = path.join(full_application_dir,
                                         application_file_name)
            if not path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                    '{0} does not exist in the application '
                    'directory'.format(application_file_name)
                )
        else:
            application_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE
            application_file = path.join(full_application_dir,
                                         application_file_name)
            if not path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                    'application directory is missing blueprint.yaml and '
                    'application_file_name query parameter was not passed')

        # return relative path from the file server root since this path
        # is appended to the file server base uri
        return application_dir, application_file_name


class UploadedPluginsManager(UploadedDataManager):

    def _get_kind(self):
        return 'plugin'

    def _get_data_url_key(self):
        return 'plugin_archive_url'

    def _get_target_dir_path(self):
        return FILE_SERVER_PLUGINS_FOLDER

    def _get_archive_type(self, archive_path):
        return 'tar.gz'

    @staticmethod
    def _get_args():
        args_parser = RequestParser()
        args_parser.add_argument('private_resource',
                                 type=types.boolean,
                                 default=False)
        return args_parser.parse_args()

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 **kwargs):
        args = self._get_args()
        new_plugin = self._create_plugin_from_archive(data_id,
                                                      archive_target_path,
                                                      args.private_resource)
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
        else:
            sm.put(new_plugin)

        return new_plugin, new_plugin.archive_name

    def _create_plugin_from_archive(self,
                                    plugin_id,
                                    archive_path,
                                    private_resource):
        plugin = self._load_plugin_package_json(archive_path)
        build_props = plugin.get('build_server_os_properties')
        return Plugin(
            id=plugin_id,
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
            private_resource=private_resource
        )

    @staticmethod
    def _load_plugin_package_json(tar_source):

        if not tarfile.is_tarfile(tar_source):
            raise manager_exceptions.InvalidPluginError(
                'the provided tar archive can not be read.')

        with tarfile.open(tar_source) as tar:
            tar_members = tar.getmembers()
            # a wheel plugin will contain exactly one sub directory
            if not tar_members:
                raise manager_exceptions.InvalidPluginError(
                    'archive file structure malformed. expecting exactly one '
                    'sub directory; got none.')
            package_json_path = os.path.join(tar_members[0].name,
                                             'package.json')
            try:
                package_member = tar.getmember(package_json_path)
            except KeyError:
                raise manager_exceptions. \
                    InvalidPluginError("'package.json' was not found under {0}"
                                       .format(package_json_path))
            try:
                package_json = tar.extractfile(package_member)
            except (tarfile.ExtractError, EnvironmentError) as e:
                raise manager_exceptions. \
                    InvalidPluginError(str(e))
            try:
                return json.load(package_json)
            except ValueError as e:
                raise manager_exceptions. \
                    InvalidPluginError("'package.json' is not a valid json: "
                                       "{json_str}. error is {error}"
                                       .format(json_str=package_json.read(),
                                               error=str(e)))
