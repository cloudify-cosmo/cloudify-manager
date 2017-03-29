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

from datetime import datetime
from unittest import TestCase

from nose.plugins.attrib import attr

from manager_rest.rest.resources_v3 import Events as EventsV3
from manager_rest.test import base_test
from manager_rest.test.endpoints.test_events import EventResult


@attr(client_min_version=3, client_max_version=base_test.LATEST_API_VERSION)
class MapEventToDictTestV3(TestCase):

    """Map event v3 information to a dictionary."""

    def test_map_event(self):
        """Map event as returned by SQL query to elasticsearch style output."""
        sql_event = EventResult(
            timestamp=datetime(2016, 12, 9),
            deployment_id='<deployment_id>',
            execution_id='<execution_id>',
            workflow_id='<workflow_id>',
            message='<message>',
            message_code=None,
            event_type='<event_type>',
            operation='<operation>',
            node_id='<node_id>',
            node_instance_id='<node_instance_id>',
            node_name='<node_name>',
            logger=None,
            level=None,
            type='cloudify_event',
        )
        expected_es_event = {
            'deployment_id': '<deployment_id>',
            'execution_id': '<execution_id>',
            'workflow_id': '<workflow_id>',
            'operation': '<operation>',
            'node_instance_id': '<node_instance_id>',
            'node_name': '<node_name>',
            'event_type': '<event_type>',
            'timestamp': '2016-12-09T00:00Z',
            'reported_timestamp': '2016-12-09T00:00Z',
            'message': '<message>',
            'type': 'cloudify_event',
        }

        es_event = EventsV3._map_event_to_dict(None, sql_event)
        self.assertDictEqual(es_event, expected_es_event)

    def test_map_log(self):
        """Map log as returned by SQL query to elasticsearch style output."""
        sql_log = EventResult(
            timestamp=datetime(2016, 12, 9),
            deployment_id='<deployment_id>',
            execution_id='<execution_id>',
            workflow_id='<workflow_id>',
            message='<message>',
            message_code=None,
            event_type=None,
            operation='<operation>',
            node_id='<node_id>',
            node_instance_id='<node_instance_id>',
            node_name='<node_name>',
            level='<level>',
            logger='<logger>',
            type='cloudify_log',
        )
        expected_es_log = {
            'deployment_id': '<deployment_id>',
            'execution_id': '<execution_id>',
            'workflow_id': '<workflow_id>',
            'operation': '<operation>',
            'node_instance_id': '<node_instance_id>',
            'node_name': '<node_name>',
            'level': '<level>',
            'timestamp': '2016-12-09T00:00Z',
            'reported_timestamp': '2016-12-09T00:00Z',
            'message': '<message>',
            'type': 'cloudify_log',
            'logger': '<logger>',
        }

        es_log = EventsV3._map_event_to_dict(None, sql_log)

        self.assertDictEqual(es_log, expected_es_log)
