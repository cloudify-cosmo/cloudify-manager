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

from datetime import datetime

import jsonschema
from flask_security import current_user
from flask_restful.reqparse import Argument

from manager_rest.manager_exceptions import ConflictError
from manager_rest.rest import rest_utils
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with
)
from manager_rest import config
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models


class ManagerConfig(SecuredResource):
    @exceptions_handled
    @authorize('manager_config_get')
    def get(self):
        """Get the Manager config, optionally filtered to a scope.

        Scope can be eg. "rest" or "mgmtworker", for filtering out the
        settings only for a single Manager component.
        """
        args = rest_utils.get_args_and_verify_arguments([
            Argument('scope', type=unicode, required=False)
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
            filters = {
                'scope': lambda column: column.contains([scope])
            }
        else:
            filters = None
        return [item.to_dict() for item in
                sm.list(models.Config, filters=filters).items]

    @property
    def _authorization_config(self):
        return {
            'roles': config.instance.authorization_roles,
            'permissions': config.instance.authorization_permissions
        }


class ManagerConfigId(SecuredResource):
    @exceptions_handled
    @marshal_with(models.Config)
    @authorize('manager_config_get')
    def get(self, name):
        """Get a single config value"""
        sm = get_storage_manager()
        return sm.get(models.Config, None, filters={'name': name})

    @exceptions_handled
    @marshal_with(models.Config)
    @authorize('manager_config_put')
    def put(self, name):
        """Update a config value.

        Settings which have is_editable set to False, can only be edited
        when passing the force flag.
        If a schema is specified for the given setting, the new value
        must validate.
        """
        sm = get_storage_manager()
        data = rest_utils.get_json_and_verify_params({
            'value': {},
            'force': {'type': bool, 'optional': True}
        })
        value = data['value']
        force = data.get('force', False)

        inst = sm.get(models.Config, None, filters={'name': name})
        if not inst.is_editable and not force:
            raise ConflictError('{0} is not editable'.format(name))
        if inst.schema:
            try:
                jsonschema.validate(value, inst.schema)
            except jsonschema.ValidationError as e:
                raise ConflictError(e.args[0])
        inst.value = value
        inst.updated_at = datetime.now()
        inst.updated_by = current_user
        sm.update(inst)
        return inst
