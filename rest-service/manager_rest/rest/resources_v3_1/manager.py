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
import requests
import xmltodict
from typing import Any

from flask import request, send_file
from flask_restful.reqparse import Argument

from cloudify.constants import MANAGER_RESOURCES_PATH
from manager_rest import config
from manager_rest.security import SecuredResource, premium_only
from manager_rest.rest import rest_utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.security.authorization import (
    authorize,
    is_user_action_allowed
)
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate
)

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
    def get(self, **_):
        file_server_protocol = 'http'
        file_server_host = 'fileserver'
        file_server_port = '9000'
        bucket_name = 'resources'

        original_uri = request.headers['X-Original-Uri']

        if not original_uri.startswith('/resources/'):
            return {}, 404

        relative_path = original_uri.replace('/resources/', '', 1)
        file_server_type = config.instance.file_server_type
        uri_is_directory = rest_utils.is_resource_uri_directory(original_uri)

        if file_server_type == 'minio':
            url = '{}://{}:{}/{}?prefix={}'.format(
                file_server_protocol,
                file_server_host,
                file_server_port,
                bucket_name,
                relative_path,
            )
            response = requests.get(url)
            response_dict = xmltodict.parse(response.content)

            if 'Contents' not in response_dict['ListBucketResult']:
                return {}, 404

            if uri_is_directory:
                files_list = []

                for file in response_dict['ListBucketResult']['Contents']:
                    file_path = f"/resources/{file['Key']}"
                    files_list.append(file_path)

                return {'files': files_list}, 200
            else:
                uri = original_uri.replace(
                    'resources',
                    f'resources-{file_server_type}',
                )

                file_full_name = uri.split('/')[-1]
                file_info = file_full_name.split('.', 1)
                file_name = file_info[0]
                file_extension = file_info[1] if len(file_info) > 1 else ''

                response = rest_utils.make_streaming_response(
                    file_name,
                    uri,
                    file_extension,
                )

                return response

        if file_server_type == 'local':
            dir_path = os.path.join(
                MANAGER_RESOURCES_PATH,
                relative_path,
            )

            if not os.path.exists(dir_path):
                return {}, 404

            if uri_is_directory:
                files_list = []

                for path, _, files in os.walk(dir_path):
                    for name in files:
                        if not name.startswith('.'):
                            files_list.append(
                                os.path.join(path, name).replace(
                                    MANAGER_RESOURCES_PATH,
                                    "/resources",
                                )
                            )

                return {'files': files_list}, 200
            else:
                return send_file(dir_path, as_attachment=True)

        return {}, 404
