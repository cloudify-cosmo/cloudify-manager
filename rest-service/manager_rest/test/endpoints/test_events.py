# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from collections import namedtuple
from copy import deepcopy
from datetime import datetime
from unittest import TestCase

from mock import patch
from nose.plugins.attrib import attr

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.rest.resources_v1 import Events
from manager_rest.test import base_test


EventResultTuple = namedtuple(
    'EventResult',
    [
        'timestamp',
        'deployment_id',
        'message',
        'message_code',
        'event_type',
        'operation',
        'node_id',
        'level',
        'logger',
        'type',
    ],
)


class EventResult(EventResultTuple):

    """Event result.

    This is a data structure similar to:
    :class:`sqlalchemy.util._collections.result`
    so that it can be used for testing

    """

    def keys(self):
        """Return event fields."""
        return self._fields


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class BuildSelectQueryTest(TestCase):

    """Event retrieval query."""

    # Parameters passed ot the _build_select_query_method
    # Each tests overwrites different fields as needed.
    DEFAULT_PARAMS = {
        'filters': {
            'type': ['cloudify_event'],
        },
        'pagination': {
            'offset': 0,
            'size': 100,
        },
        'sort': {
            '@timestamp': 'asc',
        },
        'range_filters': {},
    }

    def setUp(self):
        """Patch flask application.

        The application is only used to write to logs, so it can be patched for
        unit testing.

        """
        db_patcher = patch('manager_rest.rest.resources_v1.events.db')
        self.db = db_patcher.start()

        # Set column descriptions (used by sorting functionality)
        column_descriptions = [
                {'name': 'timestamp'},
        ]
        self.db.session.query().filter().column_descriptions = (
            column_descriptions)
        self.db.session.query().filter().union().column_descriptions = (
            column_descriptions)
        self.addCleanup(db_patcher.stop)

    def test_from_events(self):
        """Query against events table."""
        Events._build_select_query(**self.DEFAULT_PARAMS)
        self.assertLessEqual(
            self.db.session.query().filter().union.call_count,
            1,
        )

    def test_from_logs(self):
        """Query against both events and logs tables."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['filters']['type'].append('cloudify_log')
        Events._build_select_query(**params)
        self.assertGreater(
            self.db.session.query().filter().union.call_count,
            1,
        )

    def test_filter_required(self):
        """Filter parameter is expected to be dictionary."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['filters'] = None
        with self.assertRaises(BadParametersError):
            Events._build_select_query(**params)

    def test_filter_type_required(self):
        """Filter by type is expected."""
        params = deepcopy(self.DEFAULT_PARAMS)
        del params['filters']['type']
        with self.assertRaises(BadParametersError):
            Events._build_select_query(**params)

@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class BuildCountQueryTest(TestCase):

    """Event count query."""

    def setUp(self):
        """Patch flask application.

        The application is only used to write to logs, so it can be patched for
        unit testing.

        """
        db_patcher = patch('manager_rest.rest.resources_v1.events.db')
        self.db = db_patcher.start()
        self.addCleanup(db_patcher.stop)

    def test_from_events(self):
        """Query against events table."""
        filters = {'type': ['cloudify_event']}
        range_filters = {}
        Events._build_count_query(filters, range_filters)
        self.assertEqual(
            self.db.session.query().filter().subquery.call_count, 1)

    def test_from_logs(self):
        """Query against both events and logs tables."""
        filters = {'type': ['cloudify_event', 'cloudify_log']}
        range_filters = {}
        Events._build_count_query(filters, range_filters)
        self.assertEqual(
            self.db.session.query().filter().subquery.call_count, 2)

    def test_filter_required(self):
        """Filter parameter is expected to be dictionary."""
        filters = None
        range_filters = {}
        with self.assertRaises(BadParametersError):
            Events._build_count_query(filters, range_filters)

    def test_filter_type_required(self):
        """Filter by type is expected."""
        filters = {}
        range_filters = {}
        with self.assertRaises(BadParametersError):
            Events._build_count_query(filters, range_filters)


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class MapEventToEsTest(TestCase):

    """Map event information to elasticsearch format."""

    def test_map_event(self):
        """Map event as returned by SQL query to elasticsearch style output."""
        sql_event = EventResult(
            timestamp=datetime(2016, 12, 9),
            deployment_id='<deployment_id>',
            message='<message>',
            message_code=None,
            event_type='<event_type>',
            operation='<operation>',
            node_id='<node_id>',
            logger=None,
            level=None,
            type='cloudify_event',
        )
        expected_es_event = {
            'context': {
                'deployment_id': '<deployment_id>',
                'operation': '<operation>',
                'node_id': '<node_id>',
            },
            'event_type': '<event_type>',
            'timestamp': '2016-12-09T00:00Z',
            '@timestamp': '2016-12-09T00:00Z',
            'message': {
                'arguments': None,
                'text': '<message>',
            },
            'message_code': None,
            'type': 'cloudify_event',
        }

        es_event = Events._map_event_to_es(None, sql_event)
        self.assertDictEqual(es_event, expected_es_event)

    def test_map_log(self):
        """Map log as returned by SQL query to elasticsearch style output."""
        sql_log = EventResult(
            timestamp=datetime(2016, 12, 9),
            deployment_id='<deployment_id>',
            message='<message>',
            message_code=None,
            event_type=None,
            operation='<operation>',
            node_id='<node_id>',
            level='<level>',
            logger='<logger>',
            type='cloudify_log',
        )
        expected_es_log = {
            'context': {
                'deployment_id': '<deployment_id>',
                'operation': '<operation>',
                'node_id': '<node_id>',
            },
            'level': '<level>',
            'timestamp': '2016-12-09T00:00Z',
            '@timestamp': '2016-12-09T00:00Z',
            'message': {'text': '<message>'},
            'message_code': None,
            'type': 'cloudify_log',
            'logger': '<logger>',
        }

        es_log = Events._map_event_to_es(None, sql_log)

        self.assertDictEqual(es_log, expected_es_log)
