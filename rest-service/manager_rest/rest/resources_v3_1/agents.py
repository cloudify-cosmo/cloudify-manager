#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_decorators
from manager_rest.resource_manager import get_resource_manager
from manager_rest.security import SecuredResource
from manager_rest.rest.responses_v3 import AgentResponse
from manager_rest.rest.rest_utils import get_args_and_verify_arguments


class Agents(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(AgentResponse)
    @rest_decorators.paginate
    @authorize('agent_list')
    def get(self, pagination=None):
        args = get_args_and_verify_arguments([
            Argument('deployment_id', required=False),
            Argument('node_ids', required=False, action='append'),
            Argument('node_instance_ids', required=False,
                     action='append'),
            Argument('install_methods', required=False,
                     action='append'),

        ])
        return get_resource_manager().list_agents(
            deployment_id=args.get('deployment_id'),
            node_ids=args.get('node_ids'),
            node_instance_ids=args.get('node_instance_ids'),
            install_method=args.get('install_methods'))
