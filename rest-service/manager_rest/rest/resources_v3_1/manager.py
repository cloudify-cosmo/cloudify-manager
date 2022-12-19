#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
import shutil
import tempfile
import tarfile
import zipfile
from typing import Any

from flask import request
from flask_restful.reqparse import Argument

from cloudify.constants import MANAGER_RESOURCES_PATH
from manager_rest.manager_exceptions import (
    ArchiveTypeError,
    UploadFileMissing,
)
from manager_rest.security import SecuredResource, premium_only
from manager_rest.rest import rest_utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.security.authorization import (
    authorize,
    is_user_action_allowed,
    check_user_action_allowed,
)
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate
)
from manager_rest.persistent_storage import get_storage_handler
try:
    from cloudify_premium import manager as manager_premium
except ImportError:
    manager_premium = None


# community base classes for the managers and brokers endpoints:
# the http verbs that are implemented in premium, are made to throw a
# "premium-only" exception here, so they throw that in community instead of
# a 404. The method body should never be executed, because the @premium_only
# decorator should prevent it.
class _CommunityManagersBase(SecuredResource):
    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def post(self):
        raise NotImplementedError('Premium implementation only')


class _CommunityManagersId(SecuredResource):
    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def put(self):
        raise NotImplementedError('Premium implementation only')

    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def delete(self):
        raise NotImplementedError('Premium implementation only')


class _CommunityBrokersBase(SecuredResource):
    @authorize('broker_manage')
    @marshal_with(models.RabbitMQBroker)
    @premium_only
    def post(self):
        raise NotImplementedError('Premium implementation only')


class _CommunityDBNodesBase(SecuredResource):
    @authorize('cluster_node_config_update')
    @marshal_with(models.DBNodes)
    @paginate
    @premium_only
    def post(self, pagination=None):
        raise NotImplementedError('Premium implementation only')


class _CommunityBrokersId(SecuredResource):
    @authorize('broker_manage')
    @marshal_with(models.Manager)
    @premium_only
    def put(self):
        raise NotImplementedError('Premium implementation only')

    @authorize('broker_manage')
    @marshal_with(models.Manager)
    @premium_only
    def delete(self):
        raise NotImplementedError('Premium implementation only')


managers_base: Any
brokers_base: Any
dbnodes_base: Any
ManagersId: Any
RabbitMQBrokersId: Any
if manager_premium:
    managers_base = manager_premium.ManagersBase
    brokers_base = manager_premium.RabbitMQBrokersBase
    dbnodes_base = manager_premium.DBNodeBase
    ManagersId = manager_premium.ManagersId
    RabbitMQBrokersId = manager_premium.RabbitMQBrokersId
else:
    managers_base = _CommunityManagersBase
    brokers_base = _CommunityBrokersBase
    dbnodes_base = _CommunityDBNodesBase
    ManagersId = _CommunityManagersId
    RabbitMQBrokersId = _CommunityBrokersId


class Managers(managers_base):
    @marshal_with(models.Manager)
    @paginate
    @authorize('manager_get')
    def get(self, pagination=None, _include=None):
        """
        Get the list of managers in the database
        :param hostname: optional hostname to return only a specific manager
        :param _include: optional, what columns to include in the response
        """
        args = rest_utils.get_args_and_verify_arguments([
            Argument('hostname', type=str, required=False)
        ])
        hostname = args.get('hostname')
        if hostname:
            return get_storage_manager().list(
                models.Manager,
                None,
                filters={'hostname': hostname}
            )
        return get_storage_manager().list(
            models.Manager,
            include=_include
        )


class RabbitMQBrokers(brokers_base):
    @marshal_with(models.RabbitMQBroker)
    @paginate
    @authorize('broker_get')
    def get(self, pagination=None):
        """List brokers from the database."""
        brokers = get_storage_manager().list(models.RabbitMQBroker)
        if not is_user_action_allowed('broker_credentials'):
            for broker in brokers:
                broker.username = None
                broker.password = None
        return brokers


class DBNodes(dbnodes_base):
    @marshal_with(models.DBNodes)
    @paginate
    @authorize('db_nodes_get')
    def get(self, pagination=None):
        """List DB nodes from database"""
        return get_storage_manager().list(models.DBNodes)


class FileServerIndex(SecuredResource):
    def get(self, **_):
        """
        Index a directory tree on the Cloudify file server
        """
        uri = request.headers['X-Original-Uri'].strip('/')
        if not uri.startswith('resources/'):
            return {}, 404

        dir_path = os.path.join(MANAGER_RESOURCES_PATH,
                                uri.replace('resources/', '', 1))
        files_list = []
        for path, dir, files in os.walk(dir_path):
            for name in files:
                if not name.startswith('.'):
                    files_list.append(
                        os.path.join(path, name).replace(dir_path+'/', ""))

        return {'files': files_list}, 200


class FileServerProxy(SecuredResource):
    def __init__(self):
        self.storage_handler = get_storage_handler()

    def get(self, path=None, **_):
        rel_path = _resource_relative_path(path)

        if not path:
            return {}, 404

        if _is_resource_path_directory(rel_path):
            files_list = [f'/resources/{file_name}'
                          for file_name in self.storage_handler.list(rel_path)]
            return {'files': files_list}, 200

        # else path probably points to a file
        return self.storage_handler.proxy(rel_path)

    def put(self, path=None):
        args = rest_utils.get_args_and_verify_arguments([
            Argument('extract', type=bool, required=False)
        ])
        extract = args.get('extract', False)

        _, tmp_file_name = tempfile.mkstemp()
        with open(tmp_file_name, 'wb') as tmp_file:
            tmp_file.write(request.data)
            tmp_file.close()

        if not extract:
            return self.storage_handler.move(tmp_file_name, path)

        try:
            tmp_dir_name = _extract_archive(
                tmp_file_name,
                _archive_type(tmp_file_name),
            )
        finally:
            os.remove(tmp_file_name)

        for dir_path, _, file_names in os.walk(tmp_dir_name):
            for file_name in file_names:
                src = os.path.join(tmp_dir_name, dir_path, file_name)
                dst = os.path.join(
                    os.path.dirname(path),
                    os.path.relpath(
                        os.path.join(dir_path, file_name),
                        tmp_dir_name,
                    ),
                )

                self.storage_handler.move(src, dst)
        shutil.rmtree(tmp_dir_name)

    def post(self, path=None):
        if not request.files:
            raise UploadFileMissing('File upload error: no files provided')

        for _, file in request.files.items():
            _, tmp_file_name = tempfile.mkstemp()
            with open(tmp_file_name, 'wb') as tmp_file:
                tmp_file.write(file.stream.read())
                tmp_file.close()
            self.storage_handler.move(
                tmp_file_name,
                os.path.join(path or '', file.filename)
            )


class MonitoringAuth(SecuredResource):
    """Auth endpoint for monitoring.

    Users who access /monitoring need to first pass through auth_request
    proxying to here. If this returns 200, the user has full access
    to local prometheus.
    """
    def get(self, **_):
        check_user_action_allowed("monitoring")
        return "", 200


def _extract_archive(file_name, archive_type):
    match archive_type.lower():
        case 'tar':
            tmp_dir_name = tempfile.mkdtemp()
            with tarfile.open(file_name, 'r:*') as archive:
                archive.extractall(path=tmp_dir_name)
            return tmp_dir_name
        case 'zip':
            tmp_dir_name = tempfile.mkdtemp()
            with zipfile.ZipFile(file_name) as archive:
                archive.extractall(path=tmp_dir_name)
            return tmp_dir_name
    raise ArchiveTypeError(f'Unknown archive type {archive_type}')


def _archive_type(file_name):
    if tarfile.is_tarfile(file_name):
        return 'tar'
    if zipfile.is_zipfile(file_name):
        return 'zip'


def _is_resource_path_directory(path):
    return path.endswith('/')


def _resource_relative_path(uri=None):
    if not uri:
        uri = request.headers['X-Original-Uri']
        if not uri.startswith('/resources/'):
            return None

    return uri.replace('/resources/', '', 1)
