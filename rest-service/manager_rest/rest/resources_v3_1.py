#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
#
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    rest_decorators,
)
from manager_rest.storage import models

from flask_restful_swagger import swagger
from manager_rest.security import SecuredResource

from . import resources_v1


class DeploymentsId(resources_v1.DeploymentsId):

    def create_request_schema(self):
        request_schema = super(DeploymentsId, self).create_request_schema()
        request_schema['skip_plugins_validation'] = {
            'optional': True, 'type': bool}
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return request_dict.get('skip_plugins_validation', False)


class SnapshotsDepEnvRestore(SecuredResource):
    @swagger.operation(
        nickname='_restoreDepEnvs',
        notes='DO NOT USE, used during snapshot restores.'
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Execution)
    def post(self):
        execution = get_resource_manager().restore_deployment_environments(
            bypass_maintenance=is_bypass_maintenance_mode()
        )
        return execution, 200
