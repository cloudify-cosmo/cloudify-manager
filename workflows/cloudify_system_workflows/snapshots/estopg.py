########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import sys
import json
import logging
import argparse

from manager_rest import manager_exceptions
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import CURRENT_TENANT_CONFIG, DEFAULT_TENANT_NAME
from manager_rest.storage import models, get_storage_manager

format_str = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=format_str)
logger = logging.getLogger('estopg')

COMPUTE_NODE_TYPE = 'cloudify.nodes.Compute'


class EsToPg(object):
    def __init__(self, es_dump_path, tenant_name):
        self._storage_manager = self._get_storage_manager(tenant_name)
        self._es_dump_path = es_dump_path
        self._blueprints_path = '{0}.blueprints'.format(es_dump_path)
        self._deployments_path = '{0}.deployments'.format(es_dump_path)
        self._deployments_ex_path = '{0}.deployments_ex'.format(es_dump_path)
        self._nodes_path = '{0}.nodes'.format(es_dump_path)
        self._node_instances_path = '{0}.node_instances'.format(es_dump_path)
        self._plugins_path = '{0}.plugins'.format(es_dump_path)
        self._executions_path = '{0}.executions'.format(es_dump_path)
        self._events_path = '{0}.events'.format(es_dump_path)
        self._logs_path = '{0}.logs'.format(es_dump_path)

    def _get_storage_manager(self, tenant_name):
        app = setup_flask_app()
        admin = self._set_current_user(app)
        storage_manager = get_storage_manager()
        tenant = self._get_or_create_tenant(tenant_name)
        self._set_tenant_in_app(tenant, app, storage_manager, admin)
        return storage_manager

    @staticmethod
    def _set_tenant_in_app(tenant, app, storage_manager, admin_user):
        """Create a new tenant with `tenant_name`, and set it as the current
        tenant in the flask app
        """
        tenant.users.append(admin_user)
        storage_manager.put(tenant)
        app.config[CURRENT_TENANT_CONFIG] = tenant

    @staticmethod
    def _get_or_create_tenant(tenant_name):
        """Get the default tenant if using community edition, or
        """
        tenant = models.Tenant.query.filter_by(name=tenant_name).first()
        if tenant_name != DEFAULT_TENANT_NAME:
            assert not tenant, 'Attempted to restore into an ' \
                               'existing {0}:'.format(tenant)
            tenant = models.Tenant(name=tenant_name)
        else:
            assert tenant.name == DEFAULT_TENANT_NAME
        return tenant

    @staticmethod
    def _set_current_user(app):
        """Set the admin as the current user in the flask app

        :return: The admin user
        """
        admin = models.User.query.get(0)
        # This line is necessary for the `reload_user` method - we add a mock
        # request context to the flask stack
        app.test_request_context().push()

        # And then load the admin as the currently active user
        app.extensions['security'].login_manager.reload_user(admin)
        return admin

    def restore_es(self):
        logger.debug('Restoring elastic search..')
        self._split_dump()
        self._restore_blueprints()
        self._restore_deployments()
        self._restore_deployment_updates_and_modifications()
        self._restore_nodes()
        self._restore_node_instances()
        self._restore_executions()
        self._restore_plugins()
        self._restore_events()
        self._restore_logs()
        logger.debug('Restoring elastic search completed..')

    @staticmethod
    def _get_elem(line):
        elem = json.loads(line)
        return elem['_source']

    def _restore_blueprints(self):
        for line in open(self._blueprints_path, 'r'):
            elem = self._get_elem(line)
            blueprint = models.Blueprint(**elem)
            self._storage_manager.put(blueprint)

    def _restore_deployments(self):
        for line in open(self._deployments_path, 'r'):
            dep_dict = self._get_elem(line)
            blueprint = self._update_deployment(dep_dict)
            deployment = models.Deployment(**dep_dict)
            deployment.blueprint = blueprint
            self._storage_manager.put(deployment)

    def _restore_deployment_updates_and_modifications(self):
        for line in open(self._deployments_ex_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            node_type = elem['_type']
            self._update_deployment(node_data)
            if node_type == 'deployment_updates':
                dep_update = models.DeploymentUpdate(**node_data)
                self._storage_manager.put(dep_update)
                if 'steps' in node_data:
                    steps = node_data['steps']
                    for step in steps:
                        dep_step = models.DeploymentUpdateStep(**step)
                        self._storage_manager.put(dep_step)
            elif node_type == 'deployment_modifications':
                dep_modification = models.DeploymentModification(**node_data)
                self._storage_manager.put(dep_modification)
            else:
                logger.warning('Unknown node type: {0}'.format(node_type))

    def _restore_nodes(self):
        for line in open(self._nodes_path, 'r'):
            node_dict = self._get_elem(line)
            deployment = self._update_node(node_dict)
            node = models.Node(**node_dict)
            node.deployment = deployment
            self._storage_manager.put(node)

    def _restore_node_instances(self):
        for line in open(self._node_instances_path, 'r'):
            node_instance_dict = self._get_elem(line)
            node = self._update_node_instance(node_instance_dict)
            node_instance = models.NodeInstance(**node_instance_dict)
            node_instance.node = node
            self._storage_manager.put(node_instance)

    def _restore_executions(self):
        for line in open(self._executions_path, 'r'):
            execution_dict = self._get_elem(line)
            deployment = self._update_execution(execution_dict)
            execution = models.Execution(**execution_dict)
            if deployment:
                execution.deployment = deployment
            self._storage_manager.put(execution)

    def _restore_plugins(self):
        for line in open(self._plugins_path, 'r'):
            elem = json.loads(line)
            plugin = models.Plugin(**elem['_source'])
            self._storage_manager.put(plugin)

    def _restore_events(self):
        """Restore events to postgres."""
        for line in open(self._events_path, 'r'):
            es_document = json.loads(line)
            es_event = es_document['_source']
            execution_id = es_event['context']['execution_id']
            try:
                execution = self._storage_manager.get(
                    models.Execution,
                    execution_id,
                )
            except manager_exceptions.NotFoundError:
                logger.warning(
                    'Event *not* added to database: %s. '
                    'Execution not found: %s',
                    es_document['_id'],
                    execution_id,
                )
                continue

            pg_event = {
                'id': es_document['_id'],
                'timestamp': es_event['@timestamp'],
                'reported_timestamp': es_event['timestamp'],
                'message': es_event['message']['text'],
                'message_code': es_event['message_code'],
                'event_type': es_event['event_type'],
                'operation': es_event['context'].get('operation'),
                'node_id': es_event['context'].get('node_id'),
                'execution': execution,
            }
            event = models.Event(**pg_event)
            self._storage_manager.put(event)
            logger.debug('Event added to database: %s', pg_event['id'])

    def _restore_logs(self):
        """Restore logs to postgres."""
        for line in open(self._logs_path, 'r'):
            es_document = json.loads(line)
            es_log = es_document['_source']
            execution_id = es_log['context']['execution_id']
            try:
                execution = self._storage_manager.get(
                    models.Execution,
                    execution_id,
                )
            except manager_exceptions.NotFoundError:
                logger.warning(
                    'Log not inserted into database: %s. '
                    'Execution not found: %s',
                    es_document['_id'],
                    execution_id,
                )
                continue

            pg_log = {
                'id': es_document['_id'],
                'timestamp': es_log['@timestamp'],
                'reported_timestamp': es_log['timestamp'],
                'message': es_log['message']['text'],
                'message_code': es_log['message_code'],
                'logger': es_log['logger'],
                'level': es_log['level'],
                'operation': es_log['context'].get('operation'),
                'node_id': es_log['context'].get('node_id'),
                'execution': execution,
            }
            log = models.Log(**pg_log)
            self._storage_manager.put(log)
            logger.debug('Log added to database: %s', pg_log['id'])

    def _get_node(self, node_id, deployment_id):
        nodes = self._storage_manager.list(
            models.Node,
            filters={'deployment_id': deployment_id, 'id': node_id}
        )
        return nodes[0]

    def _split_dump(self):
        logger.debug('Splitting elastic search dump file..')
        dump_files = dict()
        dump_files['blueprints'] = open(self._blueprints_path, 'w')
        dump_files['deployments'] = open(self._deployments_path, 'w')
        dump_files['deployments_extra'] = open(self._deployments_ex_path, 'w')
        dump_files['nodes'] = open(self._nodes_path, 'w')
        dump_files['node_instances'] = open(self._node_instances_path, 'w')
        dump_files['executions'] = open(self._executions_path, 'w')
        dump_files['plugins'] = open(self._plugins_path, 'w')
        dump_files['events'] = open(self._events_path, 'w')
        dump_files['logs'] = open(self._logs_path, 'w')
        for line in open(self._es_dump_path, 'r'):
            try:
                elem = json.loads(line)
                assert '_type' in elem, 'missing _type'
                assert '_source' in elem, 'missing _source'
                node_type = elem['_type']
                if node_type == 'blueprint':
                    dump_files['blueprints'].write(line)
                elif node_type == 'deployment':
                    dump_files['deployments'].write(line)
                elif node_type in ['deployment_modifications',
                                   'deployment_update_steps',
                                   'deployment_updates']:
                    dump_files['deployments_extra'].write(line)
                elif node_type == 'node':
                    dump_files['nodes'].write(line)
                elif node_type == 'node_instance':
                    dump_files['node_instances'].write(line)
                elif node_type == 'execution':
                    dump_files['executions'].write(line)
                elif node_type == 'plugin':
                    dump_files['plugins'].write(line)
                elif node_type == 'cloudify_event':
                    dump_files['events'].write(line)
                elif node_type == 'cloudify_log':
                    dump_files['logs'].write(line)
                else:
                    raise Exception('Undefined type {0}'.format(node_type))
            except Exception as ex:
                logger.warning('Bad line: {0}, error: {1}'.format(line, ex))
                continue
        for index, dump_file in dump_files.items():
            dump_file.close()

    def _update_deployment(self, dep_dict):
        workflows = dep_dict['workflows']
        workflows.setdefault('install_new_agents', {
            'operation': 'cloudify.plugins.workflows.install_new_agents',
            'parameters': {
                'install_agent_timeout': {
                    'default': 300
                },
                'node_ids': {
                    'default': []
                },
                'node_instance_ids': {
                    'default': []
                }
            },
            'plugin': 'default_workflows'
        })
        dep_dict.setdefault('scaling_groups', {})
        blueprint_id = dep_dict.pop('blueprint_id')
        return self._storage_manager.get(models.Blueprint, blueprint_id)

    def _update_node_instance(self, node_instance_dict):
        node_instance_dict.setdefault('scaling_groups', [])
        deployment_id = node_instance_dict.pop('deployment_id')
        node_id = node_instance_dict.pop('node_id')
        return self._get_node(node_id, deployment_id)

    def _update_node(self, node_dict):
        node_dict.setdefault('min_number_of_instances', 0)
        node_dict.setdefault('max_number_of_instances', -1)
        type_hierarchy = node_dict.get('type_hierarchy', [])
        if COMPUTE_NODE_TYPE in type_hierarchy:
            plugins = node_dict.setdefault('plugins', [])
            if not any(p['name'] == 'agent' for p in plugins):
                plugins.append({
                    'source': None,
                    'executor': 'central_deployment_agent',
                    'name': 'agent',
                    'install': False,
                    'install_arguments': None
                })
            operations = node_dict['operations']
            create_amqp_op = 'cloudify.interfaces.cloudify_agent.create_amqp'
            create_agent = 'cloudify_agent.operations.create_agent_amqp'
            validate_amqp = 'cloudify.interfaces.cloudify_agent.validate_amqp'
            validate_agent = 'cloudify_agent.operations.validate_agent_amqp'
            self._add_operation(operations,
                                create_amqp_op,
                                {'install_agent_timeout': 300},
                                create_agent)
            self._add_operation(operations,
                                validate_amqp,
                                {'validate_agent_timeout': 20},
                                validate_agent)
        node_dict.pop('blueprint_id')
        deployment_id = node_dict.pop('deployment_id')
        return self._storage_manager.get(models.Deployment, deployment_id)

    def _update_execution(self, execution_dict):
        execution_dict.pop('blueprint_id')
        deployment_id = execution_dict.pop('deployment_id', None)
        if deployment_id:
            return self._storage_manager.get(models.Deployment, deployment_id)
        else:
            return None

    @staticmethod
    def _add_operation(operations, op_name, inputs, implementation):
        if op_name not in operations:
            operations[op_name] = {
                'inputs': inputs,
                'has_intrinsic_functions': False,
                'plugin': 'agent',
                'retry_interval': None,
                'max_retries': None,
                'executor': 'central_deployment_agent',
                'operation': implementation
            }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('es_dump_path', type=str)
    parser.add_argument('tenant_name', type=str)
    args = parser.parse_args()

    if not os.path.isfile(args.es_dump_path):
        raise Exception('Missing es dump file: {0}'.format(args.es_dump_path))

    es_to_pg = EsToPg(args.es_dump_path, args.tenant_name)
    es_to_pg.restore_es()
