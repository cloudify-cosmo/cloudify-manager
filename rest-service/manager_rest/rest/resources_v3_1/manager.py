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

from flask import request
from flask_restful import Resource
from flask_restful.reqparse import Argument

from cloudify._compat import text_type
from cloudify.constants import MANAGER_RESOURCES_PATH
from manager_rest import config
from manager_rest.manager_exceptions import NoAuthProvided
from manager_rest.security import SecuredResource, premium_only
from manager_rest.security.user_handler import get_token_status
from manager_rest.rest import rest_utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.security.authorization import (
    authorize,
    is_user_action_allowed,
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
            Argument('hostname', type=text_type, required=False)
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


class MonitoringAuth(Resource):
    """Auth endpoint for monitoring.

    Users who access /monitoring need to first pass through auth_request
    proxying to here. If this returns 200, the user has full access
    to local prometheus.

    Note: This is a subclass of Resource, not SecuredResource, because this
    does authentication in a special way.
    """
    def get(self, **_):
        # this request checks for stage's auth cookie and authenticates that
        # way, so that users can access monitoring once they've logged in
        # to stage.
        # Only this endpoint allows cookie login, because other endpoints
        # don't have any CSRF protection, and this one is read-only anyway.
        if token := request.cookies.get('XSRF-TOKEN'):
            user = get_token_status(token)
            monitoring_allowed_roles = set(
                config.instance.authorization_permissions
                .get('monitoring', [])
            )
            if (
                user.is_bootstrap_admin
                # only check system roles, and not tenant roles, because
                # monitoring is not a tenant-specific action
                or set(user.system_roles) & monitoring_allowed_roles
            ):
                return "", 200
        raise NoAuthProvided()
