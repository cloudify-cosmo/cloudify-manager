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

from datetime import datetime
import re

from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv import TestCase
from testenv import ElasticSearchProcess
from testenv.constants import LOG_INDICES_PREFIX


class EventsTest(TestCase):

    def setUp(self):
        super(EventsTest, self).setUp()
        timestamp = datetime.now()
        from testenv import testenv_instance
        index_name = '{0}{1}'.format(LOG_INDICES_PREFIX,
                                     timestamp.strftime('%Y.%m.%d'))
        testenv_instance.handle_logs_with_es(index_name)
        self.deployment_id = self._create_deployment()

    def tearDown(self):
        ElasticSearchProcess.remove_log_indices()
        super(EventsTest, self).tearDown()

    def test_events_without_logs(self):
        events = self.client.events.list(include_logs=False)
        for event in events:
            self.assertEqual(event['type'], 'cloudify_event',
                             'Expected events only')

    def test_timestamp_range(self):
        all_events = self.client.events.list(_sort='@timestamp')
        first_event = all_events[0]
        median_event = all_events[len(all_events) / 2 - 1]
        min_time = first_event['@timestamp']
        max_time = median_event['@timestamp']
        # get only half of the events by timestamp
        ranged_events = \
            self.client.events.list(from_datetime=min_time,
                                    to_datetime=max_time)
        self.assertEquals(len(ranged_events), len(all_events) / 2)

    def test_sorted_events(self):
        events = self.client.events.list(_sort='-@timestamp')
        self.assertGreater(len(events), 0, 'No events')
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
        events = self.client.events.list(**filters)

        self.assertGreater(len(events), 0, 'No events')
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
        events = self.client.events.list(_offset=offset, _size=size)
        pagination_info = events.metadata.pagination
        self.assertEquals(len(events), size)
        self.assertEquals(pagination_info.offset, offset)
        self.assertEquals(pagination_info.size, size)

    def test_query_with_reserved_characters(self):
        message = '+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /'
        self.client.events.list(message=message)

    def test_search_event_message_with_reserved_characters(self):
        from manager_rest.manager_elasticsearch import RESERVED_CHARS_REGEX

        # expecting to find a message containing 'dummy workflow'
        message = 'dum-my *low: ++**'
        searched_events = self.client.events.list(message=message,
                                                  include_logs=True)
        self.assertGreater(len(searched_events), 0, 'No events')
        message_without_reserved_chars = \
            re.sub(RESERVED_CHARS_REGEX, '', message)

        keywords = message_without_reserved_chars.lower().split()

        # assert some search results contain requested message
        for event in searched_events:
            text = event['message']['text'].lower()
            self.assertTrue(all([keyword in text for keyword in keywords]))

    def test_search_event_message(self):
        all_events = self.client.events.list()
        # checking partial word and case insensitivity ('sending')
        message = 'SeNdIN'
        searched_events = self.client.events.list(message=message)
        self.assertGreater(len(searched_events), 0, 'No events')
        # assert the search actually returned a partial result
        self.assertLess(len(searched_events), len(all_events))
        # assert all search results are relevant
        for event in searched_events:
            self.assertIn(message.lower(), event['message']['text'].lower())

    def test_list_with_include_option(self):
        _include = ['@timestamp', 'type']
        events = self.client.events.list(_include=_include)
        self.assertGreater(len(events), 0, 'No events')
        for event in events:
            self.assertListEqual(_include, event.keys(),
                                 'Expected only the following fields: {0},'
                                 ' received: {1}'
                                 .format(_include, event.keys()))

    def test_events_with_logs(self):
        events = self.client.events.list(include_logs=True)
        self.assertGreater(len(events), 0, 'No events')
        for event in events:
            if event['type'] == 'cloudify_log':
                break
        else:
            self.fail("Expected logs to be found")

    def _create_deployment(self):
        dsl_path = \
            resource('dsl/'
                     'basic_event_and_log.yaml')
        test_deployment, _ = deploy(dsl_path)
        return test_deployment.id
