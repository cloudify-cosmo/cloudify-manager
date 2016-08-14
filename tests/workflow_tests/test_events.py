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

import re

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy


class EventsTest(TestCase):

    def setUp(self):
        super(EventsTest, self).setUp()
        self.deployment_id = self._create_deployment()

    def test_events_without_logs(self):
        events = self._events_list(include_logs=False)
        for event in events:
            self.assertEqual(event['type'], 'cloudify_event',
                             'Expected events only')

    def test_timestamp_range(self):
        all_events = self._events_list(_sort='@timestamp')
        first_event = all_events[0]
        median_event = all_events[len(all_events) / 2 - 1]
        min_time = first_event['@timestamp']
        max_time = median_event['@timestamp']
        # get only half of the events by timestamp
        ranged_events = self._events_list(from_datetime=min_time,
                                          to_datetime=max_time)
        self.assertEquals(len(ranged_events), len(all_events) / 2)

    def test_sorted_events(self):
        events = self._events_list(_sort='-@timestamp')
        sorted_events = \
            sorted(events, key=lambda x: x.get('@timestamp'), reverse=True)
        self.assertListEqual(events.items, sorted_events)

    def test_filtered_events(self):
        # create multiple deployments
        deployment_ids = []
        for i in range(3):
            deployment_ids.append(self._create_deployment())

        # filter a subset of the deployments
        expected_deployment_ids = deployment_ids[:2]
        filters = {'deployment_id': expected_deployment_ids}
        events = self._events_list(**filters)

        deployments_with_events = \
            {event['context']['deployment_id'] for event in events}
        self.assertEquals(sorted(deployments_with_events),
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

    def test_search_event_message_with_reserved_characters(self):
        from manager_rest.storage.manager_elasticsearch import \
            RESERVED_CHARS_REGEX

        # expecting to find a message containing 'dummy workflow'
        message = 'dum-my *low: ++**'
        searched_events = self._events_list(message=message,
                                            include_logs=True)
        message_without_reserved_chars = \
            re.sub(RESERVED_CHARS_REGEX, '', message)

        keywords = message_without_reserved_chars.lower().split()

        # assert some search results contain requested message
        for event in searched_events:
            text = event['message']['text'].lower()
            self.assertTrue(all([keyword in text for keyword in keywords]))

    def test_search_event_message(self):
        all_events = self._events_list()
        # checking partial word and case insensitivity ('sending')
        message = 'SeNdIN'
        searched_events = self._events_list(message=message)
        # assert the search actually returned a partial result
        self.assertLess(len(searched_events), len(all_events))
        # assert all search results are relevant
        for event in searched_events:
            self.assertIn(message.lower(), event['message']['text'].lower())

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

    @staticmethod
    def _create_deployment():
        dsl_path = resource('dsl/basic_event_and_log.yaml')
        test_deployment, _ = deploy(dsl_path)
        return test_deployment.id
