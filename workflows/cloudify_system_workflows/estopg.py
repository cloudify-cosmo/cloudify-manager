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
import shlex
import logging
import subprocess

from flask import Flask
from shutil import move

from manager_rest.storage.sql_models import db
from manager_rest.storage.storage_manager import get_storage_manager

format_str = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=format_str)
logger = logging.getLogger('estopg')

COMPUTE_NODE_TYPE = 'cloudify.nodes.Compute'
TYPES_TO_RESTORE = ['blueprint',
                    'deployment',
                    'execution',
                    'node',
                    'node_instance',
                    'plugin']


class EsToPg(object):
    def __init__(self, es_data_path):
        self._storage_manager = self._setup_server()
        self._blueprints_path = '{0}.blueprints'.format(es_data_path)
        self._deployments_path = '{0}.deployments'.format(es_data_path)
        self._deployments_ex_path = '{0}.deployments_ex'.format(es_data_path)
        self._nodes_path = '{0}.nodes'.format(es_data_path)
        self._node_instances_path = '{0}.node_instances'.format(es_data_path)
        self._plugins_path = '{0}.plugins'.format(es_data_path)
        self._executions_path = '{0}.executions'.format(es_data_path)
        self._events_path = '{0}.events'.format(es_data_path)

    @staticmethod
    def _setup_server():
        logger.debug('Connecting to PG db..')
        app = Flask(__name__)
        db_uri = 'postgresql://cloudify:cloudify@localhost/cloudify_db'
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        app.app_context().push()
        return get_storage_manager()

    def restore_es(self, es_data_path):
        logger.debug('Restoring elastic search..')
        self._split_dump(es_data_path)

        for line in open(self._blueprints_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._update_blueprint(node_data)
            self._storage_manager.put_blueprint(node_data)

        for line in open(self._deployments_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._update_deployment(node_data)
            self._storage_manager.put_deployment(node_data)

        for line in open(self._deployments_ex_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            node_type = elem['_type']
            self._update_deployment(node_data)
            if node_type == 'deployment_updates':
                self._storage_manager.put_deployment_updates(node_data)
                if 'steps' in node_data:
                    steps = node_data['steps']
                    for step in steps:
                        self._storage_manager.put_deployment_update_step(step)
            elif node_type == 'deployment_modifications':
                self._storage_manager.put_deployment_modification(node_data)
            else:
                logger.warning('Unknown node type: {0}'.format(node_type))

        for line in open(self._nodes_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._update_node(node_data)
            self._storage_manager.put_node(node_data)

        for line in open(self._node_instances_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._update_node_instance(node_data)
            self._storage_manager.put_node_instance(node_data)

        for line in open(self._executions_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._storage_manager.put_execution(node_data)

        for line in open(self._plugins_path, 'r'):
            elem = json.loads(line)
            node_data = elem['_source']
            self._storage_manager.put_plugin(node_data)

        logger.debug('Restoring elastic search completed..')

    def _split_dump(self, es_data_path):
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
        for line in open(es_data_path, 'r'):
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
                elif node_type in ['cloudify_event',
                                   'cloudify_log']:
                    dump_files['events'].write(line)
                else:
                    raise Exception('Undefined type {0}'.format(node_type))
            except Exception as ex:
                logger.warning('Bad line: {0}, error: {1}'.format(line, ex))
                continue
        for index, dump_file in dump_files.items():
            dump_file.close()
        self._move(es_data_path, '{0}.backup'.format(es_data_path))
        self._move(self._events_path, es_data_path)

    def _update_blueprint(self, node_data):
        node_data.setdefault('description', '')
        node_data.setdefault('main_file_name', '')

    def _update_deployment(self, node_data):
        workflows = node_data['workflows']
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
        node_data.setdefault('scaling_groups', {})
        node_data.setdefault('description', None)

    def _update_node_instance(self, node_data):
        node_data.setdefault('scaling_groups', [])

    def _update_node(self, node_data):
        node_data.setdefault('min_number_of_instances', 0)
        node_data.setdefault('max_number_of_instances', -1)
        type_hierarchy = node_data.get('type_hierarchy', [])
        if COMPUTE_NODE_TYPE in type_hierarchy:
            plugins = node_data.setdefault('plugins', [])
            if not any(p['name'] == 'agent' for p in plugins):
                plugins.append({
                    'source': None,
                    'executor': 'central_deployment_agent',
                    'name': 'agent',
                    'install': False,
                    'install_arguments': None
                })
            operations = node_data['operations']
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

    def _add_operation(self, operations, op_name, inputs, implementation):
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

    def _move(self, source, destination):
        move(source, destination)

    def _run(self, command, ignore_failures=False):
        if isinstance(command, str):
            command = shlex.split(command)
        logger.debug('Running command: {0}'.format(' '.join(command)))
        stderr = subprocess.PIPE
        stdout = subprocess.PIPE
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        proc.aggr_stdout, proc.aggr_stderr = proc.communicate()
        if proc and proc.returncode != 0:
            command_str = ' '.join(command)
            if not ignore_failures:
                msg = 'Failed running command: {0} ({1}).'.format(
                    command_str, proc.aggr_stderr)
                raise RuntimeError(msg)
        return proc

if __name__ == "__main__":
    es_dump_path = sys.argv[1]
    if not os.path.isfile(es_dump_path):
        raise Exception('Missing es dump file: {0}'.format(es_dump_path))
    es_to_pg = EsToPg(es_dump_path)
    es_to_pg.restore_es(es_dump_path)
