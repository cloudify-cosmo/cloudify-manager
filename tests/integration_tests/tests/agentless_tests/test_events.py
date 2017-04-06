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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class EventsTest(AgentlessTestCase):

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
        all_events = self._events_list(_sort='@timestamp')
        min_time = all_events[0]['timestamp']

        expected_event_count, max_time = next(
            (index, event['timestamp'])
            for index, event in enumerate(all_events)
            if event['timestamp'] > min_time
        )

        # get only half of the events by timestamp
        ranged_events = self._events_list(
            from_datetime=min_time, to_datetime=max_time)
        self.assertEquals(len(ranged_events), expected_event_count)

    def test_sorted_events(self):
        events = self._events_list(_sort='-@timestamp')
        sorted_events = \
            sorted(events, key=lambda x: x.get('@timestamp'), reverse=True)
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
        self.assertEquals(len(events), size)
        self.assertEquals(pagination_info.offset, offset)
        self.assertEquals(pagination_info.size, size)

    def test_query_with_reserved_characters(self):
        message = '+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /'
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
        _include = ['@timestamp', 'type']
        events = self._events_list(_include=_include)
        for event in events:
            self.assertListEqual(_include, event.keys(),
                                 'Expected only the following fields: {0},'
                                 ' received: {1}'
                                 .format(_include, event.keys()))

    def test_events_with_logs(self):
        events = self._events_list(include_logs=True)
        for event in events:
            if event['type'] == 'cloudify_log':
                break
        else:
            self.fail("Expected logs to be found")

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
