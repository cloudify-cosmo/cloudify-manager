# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from mock import patch

from manager_rest.test.attribute import attr

from manager_rest.test import base_test


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class EventsTest(base_test.BaseServerTestCase):

    def test_obsolete_post_request(self):
        response = self.post('/events', {})
        self.assertEqual(405, response.status_code)

    def test_list_events(self):
        response = self.client.events.list(
            execution_id='<execution_id>',
            _sort='@timestamp',
            _size=100,
            _offset=0,
        )

        # TBD: Add events to the database to check results
        total = 0
        hits = []
        self.assertEqual(total, response.metadata.pagination.total)
        self.assertEqual(len(hits), len(response.items))

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_events(self):
        response = self.client.events.delete(
            '<deployment_id>', include_logs=True)
        self.assertEqual(response.items, [0])

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_events_timestamp_range(self):
        response = self.client.events.delete(
            '<deployment_id>', include_logs=True,
            from_datetime='2020-01-01', to_datetime='2020-02-02')
        self.assertEqual(response.items, [0])

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    @patch('manager_rest.rest.resources_v2.events.Events._store_log_entries')
    def test_delete_events_store_before(self, store_log_entries):
        response = self.client.events.delete(
            '<deployment_id>', include_logs=False,
            store_before='true')
        self.assertEqual(store_log_entries.call_count, 1)
        self.assertEqual(response.items, [0])
        response = self.client.events.delete(
            '<deployment_id>', include_logs=True,
            store_before='true')
        self.assertEqual(store_log_entries.call_count, 3)
        self.assertEqual(response.items, [0])
