#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from flask_restful.reqparse import Argument

from cloudify._compat import text_type
from manager_rest.rest import rest_utils
from manager_rest.rest.rest_decorators import (
    marshal_with
)
from manager_rest import config, manager_exceptions
from manager_rest.utils import is_administrator
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models


class ManagerConfig(SecuredResource):
    @authorize('manager_config_get')
    def get(self):
        """Get the Manager config, optionally filtered to a scope.

        Scope can be eg. "rest" or "mgmtworker", for filtering out the
        settings only for a single Manager component.
        """
        args = rest_utils.get_args_and_verify_arguments([
            Argument('scope', type=text_type, required=False)
        ])
        scope = args.get('scope')
        result = {'metadata': {}}
        if scope:
            result['items'] = self._get_items(scope)
        else:
            result['items'] = self._get_items()

        if not scope or scope == 'authorization':
            result['authorization'] = self._authorization_config
        return result

    def _get_items(self, scope=None):
        sm = get_storage_manager()
        if scope:
            filters = {'scope': scope}
        else:
            filters = None
        is_admin = is_administrator(tenant=None)
        configs = [item.to_dict() for item in
                   sm.list(models.Config, filters=filters).items]
        if is_admin:
            return configs
        for setting in configs:
            if setting['admin_only']:
                setting['value'] = '********'
        return configs

    @property
    def _authorization_config(self):
        return {
            'roles': config.instance.authorization_roles,
            'permissions': config.instance.authorization_permissions
        }


class ManagerConfigId(SecuredResource):
    @marshal_with(models.Config)
    @authorize('manager_config_get')
    def get(self, name):
        """Get a single config value

        Name can be prefixed with scope, in the format of "name.scope".
        If the name by itself is ambiguous (because it exists for multiple
        scopes), then it MUST be prefixed with the scope.
        """
        return self._get_config(name)

    @marshal_with(models.Config)
    @authorize('manager_config_put')
    def put(self, name):
        """Update a config value.

        Settings which have is_editable set to False, can only be edited
        when passing the force flag.
        If a schema is specified for the given setting, the new value
        must validate.
        Names can be prefixed with scope, using the same semantics as GET.
        """
        data = rest_utils.get_json_and_verify_params({
            'value': {},
            'force': {'type': bool, 'optional': True}
        })
        value = data['value']
        force = data.get('force', False)
        config.instance.update_db({name: value}, force)

        return self._get_config(name)

    def _get_config(self, name):
        sm = get_storage_manager()
        scope, _, name = name.rpartition('.')
        filters = {'name': name}
        if scope:
            filters['scope'] = scope
        results = sm.list(models.Config, None, filters=filters)
        if not results:
            raise manager_exceptions.NotFoundError(name)
        elif len(results) > 1:
            raise manager_exceptions.AmbiguousName(
                f'Expected 1 value, but found {len(results)}')
        result = results[0].to_dict()
        if result['admin_only'] and not is_administrator(tenant=None):
            result['value'] = '********'
        return result
