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

import os
import uuid

from . import resources_v1

from manager_rest.config import instance as config
from manager_rest.security import SecuredResource
from manager_rest.rest.rest_decorators import exceptions_handled


class DeploymentsId(resources_v1.DeploymentsId):

    def create_request_schema(self):
        request_schema = super(DeploymentsId, self).create_request_schema()
        request_schema['skip_plugins_validation'] = {
            'optional': True, 'type': bool}
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return request_dict.get('skip_plugins_validation', False)


class AgentInstallLink(SecuredResource):

    """Generate installation link for the agent.

    This endpoint generates a temporary link to the agent installation script.

    """

    @exceptions_handled
    def post(self):
        """Render agent installation script and return a link to it."""
        script_filename = '{}.py'.format(uuid.uuid4())
        script_relpath = os.path.join('cloudify_agent', script_filename)
        script_path = os.path.join(config.file_server_root, script_relpath)
        script_url = (
            '{}/{}'.
            format(config.file_server_url, script_relpath)
        )

        with open(script_path, 'w') as script_file:
            script_file.write("print('TBD')")

        return script_url
