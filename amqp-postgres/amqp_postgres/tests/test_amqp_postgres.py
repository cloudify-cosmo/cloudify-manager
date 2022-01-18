########
# Copyright (c) 2014 Cloudify Platform Ltd. All rights reserved
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

import mock
from uuid import uuid4
from time import sleep
from dateutil import parser as date_parser

from cloudify.models_states import VisibilityState

from manager_rest.storage import models
from manager_rest.config import instance
from manager_rest.amqp_manager import AMQPManager
from manager_rest.utils import get_formatted_timestamp
from manager_rest.test.base_test import BaseServerTestCase

from amqp_postgres.postgres_publisher import BATCH_DELAY, DBLogEventPublisher

LOG_MESSAGE = 'cloudify-logs'
EVENT_MESSAGE = 'cloudify-events-topic'


class TestAMQPPostgres(BaseServerTestCase):
    def setUp(self):
        super(TestAMQPPostgres, self).setUp()
        self._mock_amqp_conn = mock.Mock()
        self.db_publisher = DBLogEventPublisher(
            self.server_configuration, self._mock_amqp_conn)
        self.db_publisher.start()

    def publish_messages(self, messages):
        for message, message_type in messages:
            self.db_publisher.process(message, message_type, 0)

        # The messages are dumped to the DB every BATCH_DELAY seconds, so
        # we should wait before trying to query SQL
        sleep(BATCH_DELAY * 2)

    def test_insert(self):
        execution_id = str(uuid4())
        self._create_execution(execution_id)

        log = self._get_log(execution_id)
        event = self._get_event(execution_id)

        self.publish_messages([
            (event, EVENT_MESSAGE),
            (log, LOG_MESSAGE)
        ])

        db_log = self._get_db_element(models.Log)
        db_event = self._get_db_element(models.Event)

        self._assert_log(log, db_log)
        self._assert_event(event, db_event)

    def test_missing_execution(self):
        execution_id = str(uuid4())
        self._create_execution(execution_id)
        execution_id_2 = str(uuid4())
        self._create_execution(execution_id_2)

        # insert a log for execution 1 so that the execution gets cached
        log = self._get_log(execution_id)
        self.publish_messages([
            (log, LOG_MESSAGE)
        ])
        db_log = self._get_db_element(models.Log)
        self._assert_log(log, db_log)

        # delete execution 1, and insert logs for both execution 1 and 2
        # 1 was deleted, so the log will be lost, but we still expect that
        # the log for execution 2 will be stored
        self._delete_execution(execution_id)

        log = self._get_log(execution_id)
        log_2 = self._get_log(execution_id_2)
        self.publish_messages([
            (log, LOG_MESSAGE),
            (log_2, LOG_MESSAGE)
        ])

        execution_2_logs = self.sm.list(
            models.Log, filters={'execution_id': execution_id_2})

        self.assertEqual(len(execution_2_logs), 1)

        self._assert_log(log_2, execution_2_logs[0])

    @staticmethod
    def _get_amqp_manager():
        return AMQPManager(
            host=instance.amqp_management_host,
            username=instance.amqp_username,
            password=instance.amqp_password,
            cadata=instance.amqp_ca,
        )

    def _create_execution(self, execution_id):
        admin_user = self.sm.get(models.User, 0)
        default_tenant = self.sm.get(models.Tenant, 0)

        new_execution = models.Execution(
            id=execution_id,
            status='terminated',
            created_at=get_formatted_timestamp(),
            workflow_id='test',
            error='',
            parameters={},
            is_system_workflow=False
        )
        new_execution.creator = admin_user
        new_execution.tenant = default_tenant

        self.sm.put(new_execution)

    def _delete_execution(self, execution_id):
        execution = self.sm.get(models.Execution, execution_id)
        self.sm.delete(execution)

    def _get_db_element(self, model):
        items = self.sm.list(model)
        self.assertEqual(len(items), 1)
        return items[0]

    def _assert_timestamp(self, elem):
        timestamp = date_parser.parse(elem.timestamp)
        reported_timestamp = date_parser.parse(elem.reported_timestamp)

        # timestamp comes from `postgres_publisher` when creating the new
        # element, while `reported_timestamp` comes from the message object,
        # which should be created beforehand
        self.assertGreaterEqual(timestamp, reported_timestamp)

    def _assert_log(self, log, db_log):
        self._assert_timestamp(db_log)

        self.assertEqual(db_log.message, log['message']['text'])
        self.assertEqual(db_log.message_code, None)
        self.assertEqual(db_log.logger, log['logger'])
        self.assertEqual(db_log.level, log['level'])
        self.assertEqual(db_log.operation, log['context']['operation'])
        self.assertEqual(db_log.node_id, log['context']['node_id'])
        self.assertEqual(db_log.execution.id, log['context']['execution_id'])
        self.assertEqual(db_log.creator.id, 0)
        self.assertEqual(db_log.tenant.id, 0)
        self.assertEqual(db_log.reported_timestamp, log['timestamp'])
        self.assertEqual(db_log.visibility, VisibilityState.TENANT)

    def _assert_event(self, event, db_event):
        self._assert_timestamp(db_event)

        self.assertEqual(db_event.message, event['message']['text'])
        self.assertEqual(db_event.message_code, None)
        self.assertEqual(db_event.event_type, event['event_type'])
        self.assertEqual(db_event.error_causes, None)
        self.assertEqual(db_event.operation, None)
        self.assertEqual(db_event.node_id, None)
        self.assertEqual(db_event.execution.id,
                         event['context']['execution_id'])
        self.assertEqual(db_event.creator.id, 0)
        self.assertEqual(db_event.tenant.id, 0)
        self.assertEqual(db_event.reported_timestamp, event['timestamp'])
        self.assertEqual(db_event.visibility, VisibilityState.TENANT)

    @staticmethod
    def _get_log(execution_id, message='Test log'):
        return {
            'context': {
                'execution_id': execution_id,
                'node_id': 'vm_7j36my',
                'operation': 'cloudify.interfaces.cloudify_agent.create',
            },
            'level': 'debug',
            'logger': 'ctx.a13973d5-3866-4054-baa1-479e242fff75',
            'message': {
                'text': message
            },
            'timestamp': get_formatted_timestamp()
        }

    @staticmethod
    def _get_event(execution_id,
                   message="Starting 'install' workflow execution"):
        return {
            'message': {
                'text': message,
                'arguments': None
            },
            'event_type': 'workflow_started',
            'context': {
                'execution_id': execution_id,
            },
            'timestamp': get_formatted_timestamp()
        }
