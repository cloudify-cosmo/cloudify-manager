from flask import current_app, request

from cloudify.models_states import AgentState
from cloudify.cryptography_utils import encrypt, decrypt
from cloudify.amqp_client import SendHandler

from manager_rest.config import instance
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.amqp_manager import AMQPManager
from manager_rest import utils, manager_exceptions
from manager_rest.rest.responses_v3 import AgentResponse
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import (validate_inputs,
                                          verify_and_convert_bool,
                                          get_json_and_verify_params,
                                          parse_datetime_string,
                                          valid_user)
from manager_rest.workflow_executor import get_amqp_client


class Agents(SecuredResource):

    @rest_decorators.marshal_with(AgentResponse)
    @rest_decorators.create_filters(models.Agent)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Agent)
    @rest_decorators.all_tenants
    @rest_decorators.search('name')
    @authorize('agent_list')
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, search=None):

        get_all_results = verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.Agent,
            include=_include,
            filters=filters,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

    @authorize('agent_replace_certs')
    def patch(self):
        """Replace CA certificates on running agents."""
        request_dict = get_json_and_verify_params({'bundle': {'type': bool}})
        # broker_ca_cert or manager_ca_cert can be None so no need to
        # specify their type
        broker_ca_cert = request_dict.get('broker_ca_cert')
        manager_ca_cert = request_dict.get('manager_ca_cert')
        bundle = request_dict.get('bundle')
        sm = get_storage_manager()
        num_of_updated_agents = 0

        new_broker_ca, new_manager_ca = self._get_new_ca_certs(sm,
                                                               bundle,
                                                               broker_ca_cert,
                                                               manager_ca_cert)

        all_tenants = sm.list(models.Tenant, get_all_results=True)
        for tenant in all_tenants:
            tenant_agents = sm.list(
                models.Agent,
                get_all_results=True,
                all_tenants=True,
                filters={'tenant': tenant}
            )

            amqp_client = get_amqp_client(tenant=tenant)
            to_send = []
            for agent in tenant_agents:
                message = {
                    'service_task': {
                        'task_name': 'replace-ca-certs',
                        'kwargs': {
                            'new_broker_ca': new_broker_ca,
                            'new_manager_ca': new_manager_ca
                        }
                    }
                }
                handler = SendHandler(
                    agent.rabbitmq_exchange,
                    exchange_type='direct',
                    routing_key='service')
                to_send.append((handler, message))
                amqp_client.add_handler(handler)
                num_of_updated_agents += 1

            with amqp_client:
                for handler, message in to_send:
                    handler.publish(message)

        return {'number_of_updated_agents': num_of_updated_agents}

    @staticmethod
    def _get_new_ca_certs(sm, bundle, broker_ca_cert, manager_ca_cert):
        if not bundle:
            return broker_ca_cert, manager_ca_cert

        # Creating the CA bundle
        new_manager_ca_cert, new_broker_ca_cert = None, None
        if manager_ca_cert:
            manager_certs = {manager_ca_cert}
            manager_certs.update({mgr.ca_cert_content for mgr
                                  in sm.list(models.Manager)})
            new_manager_ca_cert = '\n'.join(manager_certs)

        if broker_ca_cert:
            broker_certs = {broker_ca_cert}
            broker_certs.update({broker.ca_cert_content for broker
                                 in sm.list(models.RabbitMQBroker)})
            new_broker_ca_cert = '\n'.join(broker_certs)

        return new_broker_ca_cert, new_manager_ca_cert


class AgentsName(SecuredResource):
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

    @rest_decorators.marshal_with(models.Agent)
    @authorize('agent_create')
    def put(self, name):
        """
        Create a new agent
        """
        request_dict = get_json_and_verify_params({
            'node_instance_id': {'type': str},
            'state': {'type': str},
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

    @rest_decorators.marshal_with(models.Agent)
    @authorize('agent_update')
    def patch(self, name):
        """Update an existing agent"""
        validate_inputs({'name': name})
        sm = get_storage_manager()

        request_dict = get_json_and_verify_params({
            'state': {'type': str, 'optional': True},
            'system': {'type': str, 'optional': True},
            'version': {'type': str, 'optional': True},
        })

        updated_agent = sm.get(models.Agent, name)
        updated_agent.updated_at = utils.get_formatted_timestamp()

        if state := request_dict.get('state'):
            self._validate_state(state)
            updated_agent.state = state

        if system := request_dict.get('system'):
            updated_agent.system = system

        if version := request_dict.get('version'):
            updated_agent.version = version

        return sm.update(updated_agent)

    def _create_agent(self, name, state, request_dict):
        created_at = owner = None
        if request_dict.get('created_at'):
            check_user_action_allowed('set_timestamp', None, True)
            created_at = parse_datetime_string(request_dict['created_at'])

        if request_dict.get('created_by'):
            check_user_action_allowed('set_owner', None, True)
            owner = valid_user(request_dict['created_by'])

        now = utils.get_formatted_timestamp()
        rabbitmq_password = request_dict.get('rabbitmq_password')
        rabbitmq_password = encrypt(rabbitmq_password) if rabbitmq_password \
            else rabbitmq_password

        storage_manager = get_storage_manager()
        node_instance = storage_manager.get(
            models.NodeInstance,
            request_dict.get('node_instance_id')
        )

        # TODO: remove these fields from the runtime properties
        new_agent = models.Agent(
            id=name,
            name=name,
            ip=request_dict.get('ip'),
            install_method=request_dict.get('install_method'),
            system=request_dict.get('system'),
            state=state,
            version=request_dict.get('version') or '',
            rabbitmq_username=request_dict.get('rabbitmq_username'),
            rabbitmq_password=rabbitmq_password,
            rabbitmq_exchange=request_dict.get('rabbitmq_exchange'),
            created_at=created_at or now,
            updated_at=now,
            node_instance=node_instance
        )
        if owner:
            new_agent.creator = owner
        if request_dict.get('visibility'):
            new_agent.visibility = request_dict['visibility']
        return storage_manager.put(new_agent)

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
            cadata=instance.amqp_ca
        )
