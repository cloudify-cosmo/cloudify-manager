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
from random import choice
from unittest import TestCase

from faker import Faker
from flask import Flask
from mock import patch
from nose.plugins.attrib import attr

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.rest.resources_v1 import Events
from manager_rest.test import base_test
from manager_rest.storage import db
from manager_rest.storage.resource_models import (
    Blueprint,
    Deployment,
    Event,
    Execution,
    Log,
)


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
class SelectEventsBaseTest(TestCase):

    """Select events test case base with database."""

    BLUEPRINT_COUNT = 2
    DEPLOYMENT_COUNT = 4
    EXECUTION_COUNT = 8
    EVENT_COUNT = 100

    EVENT_TYPES = [
        'workflow_started',
        'workflow_succeeded',
        'workflow_failed',
        'workflow_cancelled',
        'sending_task',
        'task_started',
        'task_succeeded',
        'task_rescheduled',
        'task_failed',
    ]

    LOG_LEVELS = [
        'INFO',
        'WARN',
        'WARNING',
        'ERROR',
        'FATAL',
    ]

    def setUp(self):
        """Initialize mock application with in memory sql database."""
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        context = app.app_context()
        context.push()
        self.addCleanup(context.pop)

        db.init_app(app)
        db.create_all()

        self._populate_db()

    def _populate_db(self):
        """Populate database with events and logs."""
        fake = Faker()
        session = db.session

        blueprints = [
            Blueprint(
                id=fake.uuid4(),
                created_at=fake.date_time(),
                main_file_name=fake.file_name(),
                plan='<plan>',
                _tenant_id=fake.uuid4(),
                _creator_id=fake.uuid4(),
            )
            for _ in xrange(self.BLUEPRINT_COUNT)
        ]
        session.add_all(blueprints)
        session.commit()

        deployments = [
            Deployment(
                id=fake.uuid4(),
                created_at=fake.date_time(),
                _blueprint_fk=choice(blueprints)._storage_id,
                _creator_id=fake.uuid4(),
            )
            for _ in xrange(self.DEPLOYMENT_COUNT)
        ]
        session.add_all(deployments)
        session.commit()

        executions = [
            Execution(
                id=fake.uuid4(),
                created_at=fake.date_time(),
                is_system_workflow=False,
                workflow_id=fake.uuid4(),
                _tenant_id=fake.uuid4(),
                _creator_id=fake.uuid4(),
                _deployment_fk=choice(deployments)._storage_id,
            )
            for _ in xrange(self.EXECUTION_COUNT)
        ]
        session.add_all(executions)
        session.commit()

        def create_event():
            """Create new event using the execution created above."""
            return Event(
                id=fake.uuid4(),
                timestamp=fake.date_time(),
                _execution_fk=choice(executions)._storage_id,
                node_id=fake.uuid4(),
                operation='<operation>',
                event_type=choice(self.EVENT_TYPES),
                message=fake.sentence(),
                message_code='<message_code>',
            )

        def create_log():
            """Create new log using the execution created above."""
            return Log(
                id=fake.uuid4(),
                timestamp=fake.date_time(),
                _execution_fk=choice(executions)._storage_id,
                node_id=fake.uuid4(),
                operation='<operation>',
                logger='<logger>',
                level=choice(self.LOG_LEVELS),
                message=fake.sentence(),
                message_code='<message_code>',
            )

        events = [
            choice([create_event, create_log])()
            for _ in xrange(self.EVENT_COUNT)
        ]
        sorted_events = sorted(events, key=lambda event: event.timestamp)
        session.add_all(sorted_events)
        session.commit()

        self.blueprints = blueprints
        self.deployments = deployments
        self.executions = executions
        self.events = sorted_events


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class SelectEventsFilterTest(SelectEventsBaseTest):

    """Filter events by deployment/execution."""

    DEFAULT_SORT = {
        'timestamp': 'asc'
    }
    DEFAULT_RANGE_FILTERS = {}
    DEFAULT_PAGINATION = {
        'limit': 100,
        'offset': 0,
    }

    def test_filter_by_blueprint(self):
        """Filter events by blueprint."""
        blueprint = choice(self.blueprints)
        filters = {
            'blueprint_id': [blueprint.id],
            'type': ['cloudify_event', 'cloudify_log']
        }
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_ids = [
            event.id
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_deployment_ids = [
            deployment._storage_id
            for deployment in self.deployments
            if deployment._blueprint_fk == blueprint._storage_id
        ]
        expected_executions_id = [
            execution._storage_id
            for execution in self.executions
            if execution._deployment_fk in expected_deployment_ids
        ]
        expected_event_ids = [
            event.id
            for event in self.events
            if event._execution_fk in expected_executions_id
        ]
        self.assertListEqual(event_ids, expected_event_ids)

    def test_filter_by_deployment(self):
        """Filter events by deployment."""
        deployment = choice(self.deployments)
        filters = {
            'deployment_id': [deployment.id],
            'type': ['cloudify_event', 'cloudify_log']
        }
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        events = query.params(**self.DEFAULT_PAGINATION).all()
        self.assertTrue(all(
            event.deployment_id == deployment.id
            for event in events
        ))

    def test_filter_by_execution(self):
        """Filter events by execution."""
        execution = choice(self.executions)
        filters = {
            'execution_id': [execution.id],
            'type': ['cloudify_event', 'cloudify_log']
        }
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        events = query.params(**self.DEFAULT_PAGINATION).all()
        self.assertTrue(all(
            event.execution_id == execution.id
            for event in events
        ))

    def test_filter_by_event_type(self):
        """Filter events by event_type."""
        event_type = choice(self.EVENT_TYPES)
        filters = {
            'event_type': [event_type],
            'type': ['cloudify_event', 'cloudify_log']
        }
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_ids = [
            event.id
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_event_ids = [
            event.id
            for event in self.events
            if getattr(event, 'event_type', None) == event_type
        ]
        self.assertListEqual(event_ids, expected_event_ids)

    def test_filter_by_level(self):
        """Filter events by level."""
        level = choice(self.LOG_LEVELS)
        filters = {
            'level': [level],
            'type': ['cloudify_event', 'cloudify_log']
        }
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_ids = [
            event.id
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_event_ids = [
            event.id
            for event in self.events
            if getattr(event, 'level', None) == level
        ]
        self.assertListEqual(event_ids, expected_event_ids)

    def test_filter_by_unknown(self):
        """Filter events by an unknown field."""
        filters = {
            'unknown': ['<value>'],
            'type': ['cloudify_event', 'cloudify_log']
        }
        with self.assertRaises(BadParametersError):
            Events._build_select_query(
                filters,
                self.DEFAULT_SORT,
                self.DEFAULT_RANGE_FILTERS,
            )


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class SelectEventsFilterTypeTest(SelectEventsBaseTest):

    """Filter events by type."""

    DEFAULT_SORT = {
        'timestamp': 'asc'
    }
    DEFAULT_RANGE_FILTERS = {}
    DEFAULT_PAGINATION = {
        'limit': 100,
        'offset': 0,
    }

    TYPE_TO_MODEL = {
        'cloudify_log': Log,
        'cloudify_event': Event,
    }

    def _get_events_by_type(self, event_types):
        """Get events by type

        :param event_types:
            Type filter ('cloudify_event' and/or 'cloudify_log')
        :type event_types: list(str)

        """
        event_classes = tuple([
            self.TYPE_TO_MODEL[event_type]
            for event_type in event_types
        ])

        filters = {'type': event_types}
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_ids = [
            event.id
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_event_ids = [
            event.id
            for event in self.events
            if isinstance(event, event_classes)
        ]
        self.assertListEqual(event_ids, expected_event_ids)

    def test_get_events_and_logs_explicit(self):
        """Get both events and logs explicitly by passing filters."""
        self._get_events_by_type(['cloudify_event', 'cloudify_log'])

    def test_get_events_and_logs_implicit(self):
        """Get both events and logs implicitly without passing any filter."""
        filters = {}
        query = Events._build_select_query(
            filters,
            self.DEFAULT_SORT,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_ids = [
            event.id
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_event_ids = [event.id for event in self.events]
        self.assertListEqual(event_ids, expected_event_ids)

    def test_get_events(self):
        """Get only events."""
        self._get_events_by_type(['cloudify_event'])

    def test_get_logs(self):
        """Get only logs."""
        self._get_events_by_type(['cloudify_log'])


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class SelectEventsSortTest(SelectEventsBaseTest):

    """Sort events by timestamp ascending/descending."""

    DEFAULT_FILTERS = {
        'type': ['cloudify_event', 'cloudify_log']
    }
    DEFAULT_RANGE_FILTERS = {}
    DEFAULT_PAGINATION = {
        'limit': 100,
        'offset': 0,
    }

    def _sort_by_timestamp(self, field, direction):
        """Sort by a given field.

        :param field: Field name (timestamp/@timestamp)
        :type field: str
        :param direction: Sorting direction (asc/desc)
        :type direction: str

        """
        sort = {field: direction}
        query = Events._build_select_query(
            self.DEFAULT_FILTERS,
            sort,
            self.DEFAULT_RANGE_FILTERS,
        )
        event_timestamps = [
            event.timestamp
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        expected_events = sorted(
            self.events,
            key=lambda event: event.timestamp,
            reverse=direction == 'desc',
        )
        expected_event_timestamps = [
            event.timestamp
            for event in expected_events
        ]
        self.assertListEqual(event_timestamps, expected_event_timestamps)

    def test_sort_by_timestamp_ascending(self):
        """Sort by timestamp ascending."""
        self._sort_by_timestamp('timestamp', 'asc')

    def test_sort_by_timestamp_descending(self):
        """Sort by timestamp descending."""
        self._sort_by_timestamp('timestamp', 'desc')

    def test_sort_at_by_timestamp_ascending(self):
        """Sort by @timestamp ascending.

        This is to verify compatibility with the old Elasticsearch based
        implementation.

        """
        self._sort_by_timestamp('@timestamp', 'asc')

    def test_sort_by_at_timestamp_descending(self):
        """Sort by @timestamp descending.

        This is to verify compatibility with the old Elasticsearch based
        implementation.

        """
        self._sort_by_timestamp('@timestamp', 'desc')


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class SelectEventsRangeFilterTest(SelectEventsBaseTest):

    """Filter out events not included in a range."""

    DEFAULT_FILTERS = {
        'type': ['cloudify_event', 'cloudify_log']
    }
    DEFAULT_SORT = {
        'timestamp': 'asc'
    }
    DEFAULT_PAGINATION = {
        'limit': 100,
        'offset': 0,
    }

    def _filter_by_timestamp_range(
            self, field, include_from=True, include_to=True):
        """Filter by timestamp range.

        :param field: Field name to use (timestamp/@timestamp)
        :type field: str
        :param include_from: Whether to include from field in range filter
        :type include_from: bool
        :param include_to: Whether to include from field in range filter
        :type include_to: bool

        """
        fake = Faker()
        from_datetime, to_datetime = sorted(
            [fake.date_time(), fake.date_time()])

        range_filter = {}
        if include_from:
            range_filter['from'] = from_datetime
        if include_to:
            range_filter['to'] = to_datetime
        range_filters = {field: range_filter}

        query = Events._build_select_query(
            self.DEFAULT_FILTERS,
            self.DEFAULT_SORT,
            range_filters,
        )
        event_timestamps = [
            event.timestamp
            for event in query.params(**self.DEFAULT_PAGINATION).all()
        ]
        events = sorted(
            self.events,
            key=lambda event: event.timestamp,
        )

        from_timestamp = '{}Z'.format(from_datetime.isoformat()[:-3])
        to_timestamp = '{}Z'.format(to_datetime.isoformat()[:-3])
        expected_event_timestamps = [
            event.timestamp
            for event in events
            if (
                (not include_from or from_timestamp <= event.timestamp) and
                (not include_to or event.timestamp <= to_timestamp)
            )
        ]

        self.assertListEqual(event_timestamps, expected_event_timestamps)

    def test_filter_by_timestamp_range(self):
        """Filter by timestamp range."""
        self._filter_by_timestamp_range('timestamp')

    def test_filter_by_at_timestamp_range(self):
        """Filter by @timestamp range."""
        self._filter_by_timestamp_range('@timestamp')

    def test_filter_by_unknown_range(self):
        """Filter by unknown field range."""
        with self.assertRaises(BadParametersError):
            Events._build_select_query(
                self.DEFAULT_FILTERS,
                self.DEFAULT_SORT,
                {'unknown': {'from': 'a', 'to': 'b'}},
            )

    def test_filter_do_not_include_from(self):
        """Filter by timestamp without including from field."""
        self._filter_by_timestamp_range('timestamp', include_from=False)

    def test_filter_do_not_include_to(self):
        """Filter by timestamp without including to field."""
        self._filter_by_timestamp_range('timestamp', include_to=False)


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class BuildSelectQueryTest(TestCase):

    """Event retrieval query."""

    # Parameters passed ot the _build_select_query_method
    # Each tests overwrites different fields as needed.
    DEFAULT_PARAMS = {
        'filters': {
            'type': ['cloudify_event'],
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
        with self.assertRaises(AssertionError):
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
        with self.assertRaises(AssertionError):
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
