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

from flask_security import current_user

from manager_rest.app_logging import raise_unauthorized_user_error
from manager_rest.constants import VIEWER_PERMISSION, ALL_PERMISSIONS
from manager_rest.storage import models, get_storage_manager, user_datastore
from manager_rest.manager_exceptions import (NotFoundError,
                                             BadParametersError)


class PermissionsHandler(object):
    MODEL_CLASS_MAPPING = {
        'blueprint': models.Blueprint,
        'deployment': models.Deployment,
        'snapshot': models.Snapshot,
        'plugin': models.Plugin
    }

    @staticmethod
    def _get_permission(params):
        permission = params.get('permission', VIEWER_PERMISSION)
        if permission not in ALL_PERMISSIONS:
            raise BadParametersError('Incorrect permission passed: {0}'.format(
                permission
            ))
        return permission

    @staticmethod
    def _get_resource(resource_type, resource_id):
        model_class = PermissionsHandler.MODEL_CLASS_MAPPING.get(resource_type)
        if not model_class:
            raise BadParametersError(
                'Incorrect resource type passed: {0}'.format(resource_type)
            )
        return get_storage_manager().get(model_class, resource_id)

    @staticmethod
    def _get_users(params):
        users_list = []
        for username in params['users']:
            user = user_datastore.get_user(username)
            if not user:
                raise NotFoundError('User `{0}` was not '
                                    'found'.format(username))
            users_list.append(user)
        return users_list

    @staticmethod
    def _get_users_list_from_permission(resource, permission):
        if permission == VIEWER_PERMISSION:
            return resource.viewers
        else:
            return resource.owners

    @staticmethod
    def _set_permissions_for_resource(resource,
                                      users_list,
                                      users,
                                      add_permissions):
        sm = get_storage_manager()

        for user in users:
            if add_permissions and user not in users_list:
                users_list.append(user)
            elif not add_permissions and user in users_list:
                users_list.remove(user)

        sm.update(resource)

    @staticmethod
    def _assert_user_authorized_set_permissions(resource):
        if current_user.is_admin \
                or current_user == resource.creator \
                or current_user in resource.owners:
            return

        raise_unauthorized_user_error(
            '{0} does not have privileges to change permissions for '
            '{1}'.format(current_user, resource)
        )

    @staticmethod
    def _set_or_update_permissions(params, add_permissions=True):
        resource = PermissionsHandler._get_resource(
            params['resource_type'],
            params['resource_id']
        )
        PermissionsHandler._assert_user_authorized_set_permissions(resource)
        permission = PermissionsHandler._get_permission(params)
        users = PermissionsHandler._get_users(params)
        users_list = PermissionsHandler._get_users_list_from_permission(
            resource,
            permission
        )
        PermissionsHandler._set_permissions_for_resource(
            resource, users_list, users, add_permissions
        )

        return {'resource_id': resource.id}

    @staticmethod
    def add_permissions(params):
        return PermissionsHandler._set_or_update_permissions(params)

    @staticmethod
    def remove_permissions(params):
        return PermissionsHandler._set_or_update_permissions(params, False)
