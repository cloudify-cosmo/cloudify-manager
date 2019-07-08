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

from flask import current_app
from flask_restful.reqparse import Argument

from cloudify.models_states import AgentState
from cloudify.cryptography_utils import encrypt, decrypt

from manager_rest.config import instance
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.amqp_manager import AMQPManager
from manager_rest import utils, manager_exceptions
from manager_rest.rest.responses_v3 import AgentResponse
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.rest_utils import (validate_inputs,
                                          get_json_and_verify_params,
                                          get_args_and_verify_arguments)


class Agents(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(AgentResponse)
    @rest_decorators.paginate
    @authorize('agent_list')
    def get(self, pagination=None):
        args = get_args_and_verify_arguments([
            Argument('deployment_id', required=False),
            Argument('node_ids', required=False, action='append'),
            Argument('node_instance_ids', required=False, action='append'),
            Argument('install_methods', required=False, action='append'),
            Argument('all_tenants', required=False,  action='append')
        ])
        return get_resource_manager().list_agents(
            deployment_id=args.get('deployment_id'),
            node_ids=args.get('node_ids'),
            node_instance_ids=args.get('node_instance_ids'),
            install_method=args.get('install_methods'),
            all_tenants=args.get('all_tenants'))


class AgentsName(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Agent)
    @authorize('agent_get')
    def get(self, name):
        """
        Get agent by name
        """
        validate_inputs({'name': name})
        agent = get_storage_manager().get(models.Agent, name)
        agent_dict = agent.to_dict()
        if agent.rabbitmq_password:
            agent_dict['rabbitmq_password'] = decrypt(agent.rabbitmq_password)
        return agent_dict

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Agent)
    @authorize('agent_create')
    def put(self, name):
        """
        Create a new agent
        """
        request_dict = get_json_and_verify_params({
            'node_instance_id': {'type': unicode},
            'state': {'type': unicode},
            'create_rabbitmq_user': {'type': bool}
        })
        validate_inputs({'name': name})
        state = request_dict.get('state')
        self._validate_state(state)
        response = {}

        try:
            new_agent = self._create_agent(name, state, request_dict)
            response = new_agent
        except manager_exceptions.ConflictError:
            # Assuming the agent was already created in cases of reinstalling
            # or healing
            current_app.logger.info("Not creating agent {0} because it "
                                    "already exists".format(name))
            new_agent = get_storage_manager().get(models.Agent, name)

        if request_dict.get('create_rabbitmq_user'):
            # Create rabbitmq user
            self._get_amqp_manager().create_agent_user(new_agent)
        return response

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Agent)
    @authorize('agent_update')
    def patch(self, name):
        """
        Update an existing agent
        """
        request_dict = get_json_and_verify_params({
            'state': {'type': unicode}
        })
        validate_inputs({'name': name})
        state = request_dict['state']
        self._validate_state(state)
        return self._update_agent(name, state)

    def _create_agent(self, name, state, request_dict):
        timestamp = utils.get_formatted_timestamp()
        rabbitmq_password = request_dict.get('rabbitmq_password')
        rabbitmq_password = encrypt(rabbitmq_password) if rabbitmq_password \
            else rabbitmq_password

        # TODO: remove these fields from the runtime properties
        new_agent = models.Agent(
            id=name,
            name=name,
            ip=request_dict.get('ip'),
            install_method=request_dict.get('install_method'),
            system=request_dict.get('system'),
            state=state,
            version=request_dict.get('version'),
            rabbitmq_username=request_dict.get('rabbitmq_username'),
            rabbitmq_password=rabbitmq_password,
            rabbitmq_exchange=request_dict.get('rabbitmq_exchange'),
            created_at=timestamp,
            updated_at=timestamp,
        )
        storage_manager = get_storage_manager()
        node_instance = storage_manager.get(
            models.NodeInstance,
            request_dict.get('node_instance_id')
        )
        new_agent.node_instance = node_instance
        return storage_manager.put(new_agent)

    def _update_agent(self, name, state):
        storage_manager = get_storage_manager()
        updated_agent = storage_manager.get(models.Agent, name)
        updated_agent.state = state
        updated_agent.updated_at = utils.get_formatted_timestamp()
        return storage_manager.update(updated_agent)

    def _validate_state(self, state):
        if state not in AgentState.STATES:
            raise manager_exceptions.BadParametersError(
                'Invalid agent state: `{0}`.'.format(state)
            )

    def _get_amqp_manager(self):
        return AMQPManager(
            host=instance.amqp_management_host,
            username=instance.amqp_username,
            password=instance.amqp_password,
            verify=instance.amqp_ca_path
        )
