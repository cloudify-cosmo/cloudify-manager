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

import uuid
import time
import pytest

from datetime import datetime, timedelta
from integration_tests.framework import docker
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import run_postgresql_command
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_events_logs

CREATE_SNAPSHOT_SUCCESS_MSG =\
    "'create_snapshot' workflow execution succeeded"
RESTORE_SNAPSHOT_SUCCESS_MSG =\
    "'restore_snapshot' workflow execution succeeded"


@pytest.mark.usefixtures('testmockoperations_plugin')
class EventsTest(AgentlessTestCase):

    """Events test cases using the default database timezone (UTC)."""

    def setUp(self):
        super(EventsTest, self).setUp()
        self.deployment_id = self._create_deployment()

    def test_events_without_logs(self):
        events = self._events_list(include_logs=False)
        for event in events:
            self.assertEqual(event['type'], 'cloudify_event',
                             'Expected events only')

    def test_timestamp_range(self):
        """Filter events by timestamp range."""
        all_events = self._events_list(
            _sort='@timestamp',
            include_logs=True,
        )
        all_timestamps = [event['timestamp'] for event in all_events]

        min_time = all_timestamps[0]
        max_time = next(
            timestamp
            for timestamp in all_timestamps
            if timestamp > min_time
        )
        expected_event_count = sum([
            min_time <= timestamp < max_time
            for timestamp in all_timestamps
        ])

        ranged_events = self._events_list(
            _sort='@timestamp',
            include_logs=True,
            from_datetime=min_time,
            to_datetime=max_time,
            skip_assertion=True,
        )

        self.assertEqual(len(ranged_events), expected_event_count)

    def test_sorted_events(self):
        events = self._events_list(_sort='-@timestamp')
        sorted_events = \
            sorted(events, key=lambda x: x.get('@timestamp', ''), reverse=True)
        self.assertListEqual(events.items, sorted_events)

    def test_filtered_events(self):
        """Filter events by deployment."""
        # create multiple deployments
        deployment_ids = [self._create_deployment() for _ in range(3)]

        # filter a subset of the deployments
        expected_deployment_ids = deployment_ids[:2]
        filters = {'deployment_id': expected_deployment_ids}
        events = self._events_list(**filters)

        deployments_with_events = {event['deployment_id'] for event in events}
        self.assertListEqual(
            sorted(deployments_with_events),
            sorted(expected_deployment_ids),
            'Expected events of deployment ids {0} exactly, '
            'received deployment ids {1} instead'
            .format(expected_deployment_ids,
                    deployments_with_events))

    def test_paginated_events(self):
        size = 5
        offset = 3
        events = self._events_list(_offset=offset, _size=size)
        pagination_info = events.metadata.pagination
        self.assertEqual(len(events), size)
        self.assertEqual(pagination_info.offset, offset)
        self.assertEqual(pagination_info.size, size)

    def test_query_with_reserved_characters(self):
        message = '+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \\ /'
        self._events_list(message=message,
                          skip_assertion=True)

    def test_search_event_message(self):
        """Filter events by message pattern."""
        all_events = self._events_list()
        # checking partial word and case insensitivity ('sending')
        raw_message = 'SeNdIN'
        message = '%{}%'.format(raw_message)
        searched_events = self._events_list(message=message)
        # assert the search actually returned a partial result
        self.assertLess(len(searched_events), len(all_events))
        # assert all search results are relevant
        for event in searched_events:
            self.assertIn(raw_message.lower(), event['message'].lower())

    def test_list_with_include_option(self):
        """Include only desired fields."""
        _include = ['timestamp', 'type']
        events = self._events_list(_include=_include)
        for event in events:
            self.assertListEqual(_include, list(event.keys()),
                                 'Expected only the following fields: {0},'
                                 ' received: {1}'
                                 .format(_include, list(event.keys())))

    def test_events_with_logs(self):
        events = self._events_list(include_logs=True)
        for event in events:
            if event['type'] == 'cloudify_log':
                break
        else:
            self.fail("Expected logs to be found")

    @pytest.mark.skip(reason='causes the DB deadlock in snapshot')
    def test_snapshots_events(self):
        """ Make sure snapshots events appear when using the
         'cfy events list' command """
        # Make sure 'snapshots create' events appear
        snapshot_id = 's{0}'.format(uuid.uuid4())
        execution = self.client.snapshots.create(snapshot_id, False, False)
        self.wait_for_event(execution, CREATE_SNAPSHOT_SUCCESS_MSG)

        # Make sure 'snapshots restore' events appear
        self.undeploy_application(
            self.deployment_id, is_delete_deployment=True)
        execution = self.client.snapshots.restore(snapshot_id, force=True)
        # give the database some time to downgrade/upgrade before running
        # requests to avoid the deadlock described in CY-1455
        time.sleep(10)

        self.wait_for_event(execution, RESTORE_SNAPSHOT_SUCCESS_MSG)

    def _events_list(self, **kwargs):
        if 'deployment_id' not in kwargs:
            kwargs['deployment_id'] = self.deployment_id
        skip_assertion = kwargs.pop('skip_assertion', False)

        def elist():
            events = self.client.events.list(**kwargs)
            if skip_assertion:
                return events
            self.assertGreater(len(events), 0, 'No events')
            return events
        return self.do_assertions(elist, timeout=120)

    def _create_deployment(self):
        dsl_path = resource('dsl/basic_event_and_log.yaml')
        test_deployment, _ = self.deploy_application(dsl_path)
        return test_deployment.id


class _SetAlternateTimezone(object):
    TIMEZONE = 'Asia/Jerusalem'

    def setUp(self):
        """Update postgres timezone and create a deployment."""
        self.original_tz = run_postgresql_command(
            self.env.container_id, 'SHOW TIME ZONE').split('\n')[2].strip()
        run_postgresql_command(
            self.env.container_id,
            "ALTER DATABASE cloudify_db  SET TIME ZONE '{}'"
            .format(self.TIMEZONE)
        )
        # restart all users of the db so that they get a new session which
        # uses the just-set timezone
        docker.execute(
            self.env.container_id,
            self.get_service_management_command() +
            ' restart cloudify-amqp-postgres cloudify-restservice '
            'cloudify-execution-scheduler'
        )
        # Make sure that database timezone is correctly set
        query_result = run_postgresql_command(self.env.container_id,
                                              'SHOW TIME ZONE')
        self.assertEqual(query_result.split('\n')[2].strip(), self.TIMEZONE)

        time.sleep(1)   # give time for services to restart
        self.start_timestamp = datetime.utcnow().isoformat()
        super().setUp()
        # log storing is async, add a few seconds to allow for that
        self.stop_timestamp = \
            (datetime.utcnow() + timedelta(seconds=3)).isoformat()

    def tearDown(self):
        super().tearDown()
        run_postgresql_command(
            self.env.container_id,
            "ALTER DATABASE cloudify_db SET TIME ZONE '{}'"
            .format(self.original_tz)
        )
        docker.execute(
            self.env.container_id,
            self.get_service_management_command() +
            ' restart cloudify-amqp-postgres cloudify-restservice '
            'cloudify-execution-scheduler'
        )


class EventsAlternativeTimezoneTest(_SetAlternateTimezone, EventsTest):
    """Events test cases using an alternative timezone (Asia/Jerusalem)."""

    def test_timestamp_in_utc(self):
        """Make sure events timestamp field is in UTC."""
        events = self._events_list()
        timestamps = [event['timestamp'] for event in events]
        out_of_range_timestamps = [
            timestamp
            for timestamp in timestamps
            if not self.start_timestamp < timestamp < self.stop_timestamp
        ]
        self.assertFalse(
            out_of_range_timestamps,
            'Timestamp values out of range [{} - {}]: {}'
            .format(
                self.start_timestamp,
                self.stop_timestamp,
                out_of_range_timestamps,
            )
        )

    def test_reported_timestamp_in_utc(self):
        """Make sure events reported_timestamp field is in UTC."""
        events = self._events_list()
        reported_timestamps = [event['reported_timestamp'] for event in events]
        self.assertTrue(all(
            self.start_timestamp < reported_timestamp < self.stop_timestamp
            for reported_timestamp in reported_timestamps
        ))
