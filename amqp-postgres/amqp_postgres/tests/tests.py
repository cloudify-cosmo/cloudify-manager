########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

import time
import threading
from uuid import uuid4
from datetime import datetime

from cloudify.amqp_client import create_events_publisher

from manager_rest import utils
from manager_rest.storage import models
from manager_rest.config import instance
from manager_rest.amqp_manager import AMQPManager
from manager_rest.utils import get_formatted_timestamp
from manager_rest.test.base_test import BaseServerTestCase


from amqp_postgres.main import main


permitted_roles = ['sys_admin', 'manager', 'user', 'operations', 'viewer']
auth_dict = {
    'roles': [
        {'name': 'sys_admin', 'description': ''},
        {'name': 'manager', 'description': ''},
        {'name': 'user', 'description': ''},
        {'name': 'viewer', 'description': ''},
        {'name': 'default', 'description': ''}
    ],
    'permissions': {
        'all_tenants': ['sys_admin', 'manager'],
        'administrators': ['sys_admin', 'manager'],
        'create_global_resource': ['sys_admin'],
        'execution_list': permitted_roles,
        'deployment_list': permitted_roles,
        'blueprint_list': permitted_roles
    }
}


class AMQPPostgresTest(BaseServerTestCase):

    def create_configuration(self):
        """
        Override here to allow using postgresql instead of sqlite
        """
        config = super(AMQPPostgresTest, self).create_configuration()
        config.postgresql_host = 'localhost'
        config.postgresql_db_name = 'cloudify_db'
        config.postgresql_username = 'cloudify'
        config.postgresql_password = 'cloudify'
        return config

    def _create_config_and_reset_app(self, server):
        """
        Override here to allow using postgresql instead of sqlite
        """
        self.server_configuration = self.create_configuration()
        utils.copy_resources(self.server_configuration.file_server_root)
        server.reset_app(self.server_configuration)

    @staticmethod
    def _run_amqp_postgres():
        thread = threading.Thread(target=main)
        thread.daemon = True
        thread.start()
        return thread

    def test(self):
        main_thread = self._run_amqp_postgres()

        time.sleep(5)

        execution_id = str(uuid4())
        self._create_execution(execution_id)

        log = self._get_log(execution_id)
        event = self._get_event(execution_id)

        events_publisher = create_events_publisher()

        events_publisher.publish_message(log, message_type='log')
        events_publisher.publish_message(event, message_type='event')

        main_thread.join(3)

        db_log = self._get_db_element(models.Log)
        db_event = self._get_db_element(models.Event)

        self._assert_log(log, db_log)
        self._assert_event(event, db_event)

    @staticmethod
    def _get_amqp_manager():
        return AMQPManager(
            host=instance.amqp_management_host,
            username=instance.amqp_username,
            password=instance.amqp_password,
            verify=instance.amqp_ca_path
        )

    def _create_execution(self, execution_id):
        new_execution = models.Execution(
            id=execution_id,
            status='terminated',
            created_at=get_formatted_timestamp(),
            workflow_id='test',
            error='',
            parameters={},
            is_system_workflow=False
        )
        self.sm.put(new_execution)

    def _get_db_element(self, model):
        items = self.sm.list(model)
        self.assertEqual(len(items), 1)
        return items[0]

    def _assert_log(self, log, db_log):
        self.assertEqual(len(db_log), 14)

        db_timestamp = '{0}Z'.format(
            db_log.reported_timestamp.isoformat()[:-3]
        )

        self.assertEqual(db_log.id, None)
        self.assertEqual(type(db_log.timestamp), datetime)
        self.assertEqual(db_log.message, log['message']['text'])
        self.assertEqual(db_log.message_code, None)
        self.assertEqual(db_log.logger, log['logger'])
        self.assertEqual(db_log.level, log['level'])
        self.assertEqual(db_log.operation, log['context']['operation'])
        self.assertEqual(db_log.node_id, log['context']['node_id'])
        self.assertEqual(db_log.execution.id, 0)
        self.assertEqual(db_log.creator.id, 0)
        self.assertEqual(db_log.tenant.id, 0)
        self.assertEqual(db_timestamp, log['timestamp'])
        self.assertEqual(db_log.private_resource, None)
        self.assertEqual(db_log.visibility, None)

    def _assert_event(self, event, db_event):
        self.assertEqual(len(db_event), 14)

        db_timestamp = '{0}Z'.format(
            db_event.reported_timestamp.isoformat()[:-3]
        )

        self.assertEqual(db_event.id, None)
        self.assertEqual(type(db_event.timestamp), datetime)
        self.assertEqual(db_event.message, event['message']['text'])
        self.assertEqual(db_event.message_code, None)
        self.assertEqual(db_event.event_type, event['event_type'])
        self.assertEqual(db_event.error_causes, None)
        self.assertEqual(db_event.operation, event['context']['operation'])
        self.assertEqual(db_event.node_id, event['context']['node_id'])
        self.assertEqual(db_event.execution.id, 0)
        self.assertEqual(db_event.creator.id, 0)
        self.assertEqual(db_event.tenant.id, 0)
        self.assertEqual(db_timestamp, event['timestamp'])
        self.assertEqual(db_event.private_resource, None)
        self.assertEqual(db_event.visibility, None)

    @staticmethod
    def now():
        return '{0}Z'.format(datetime.utcnow().isoformat()[:-3])

    def _get_log(self, execution_id):
        return {
            'context': {
                'blueprint_id': 'bp',
                'deployment_id': 'dep',
                'execution_id': execution_id,
                'node_id': 'vm_7j36my',
                'node_name': 'vm',
                'operation': 'cloudify.interfaces.cloudify_agent.create',
                'plugin': 'agent',
                'task_id': 'a13973d5-3866-4054-baa1-479e242fff75',
                'task_name': 'cloudify_agent.installer.operations.create',
                'task_queue': 'cloudify.management',
                'task_target': 'cloudify.management',
                'workflow_id': 'install'
            },
            'level': 'debug',
            'logger': 'ctx.a13973d5-3866-4054-baa1-479e242fff75',
            'message': {
                'text': 'Test log'
            },
            'timestamp': self.now()
        }

    def _get_event(self, execution_id):
        return {
            'message': {
                'text': "Starting 'install' workflow execution",
                'arguments': None
            },
            'event_type': 'workflow_started',
            'context': {
                'deployment_id': 'dep',
                'workflow_id': 'install',
                'execution_id': execution_id,
                'blueprint_id': 'bp'
            },
            'timestamp': self.now()
        }
