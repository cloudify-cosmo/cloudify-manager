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

import re

from copy import deepcopy
from unittest import TestCase

from mock import patch
from nose.plugins.attrib import attr
from werkzeug.exceptions import BadRequest

from manager_rest.rest.resources import Events
from manager_rest.test import base_test


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class BuildSelectQueryTest(TestCase):

    """Event retrieval query."""

    # Parametesr passed ot the _build_select_query_method
    # Each tests overwrites different fields as needed.
    DEFAULT_PARAMS = {
        '_include': None,
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
    }

    def setUp(self):
        """Patch flask application.

        The application is only used to write to logs, so it can be patched for
        unit testing.

        """
        patcher = patch('manager_rest.rest.resources.current_app')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_from_events(self):
        """Query against events table."""
        query = str(Events._build_select_query(**self.DEFAULT_PARAMS))
        match = re.search(r'FROM\s+events', query)
        self.assertTrue(match)

    def test_from_logs(self):
        """Query against both events and logs tables."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['filters']['type'].append('cloudify_log')
        query = str(Events._build_select_query(**params))
        events_match = re.search(r'FROM\s+events', query)
        self.assertTrue(events_match)
        logs_match = re.search(r'FROM\s+logs', query)
        self.assertTrue(logs_match)

    def test_include_set_to_none(self):
        """Include parameter is expected to be set to None."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['_include'] = '<invalid>'
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_filter_required(self):
        """Filter parameter is expected to be dictionary."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['filters'] = None
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_filter_type_required(self):
        """Filter by type is expected."""
        params = deepcopy(self.DEFAULT_PARAMS)
        del params['filters']['type']
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_filter_type_event(self):
        """Filter is set at least to cloudify_event."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['filters'] = {'type': ['cloudify_log']}
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_sort_required(self):
        """Sort parameter is expected to be a dictionary."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['sort'] = None
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_sort_by_timestamp_required(self):
        """Ordering by timestamp expected."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['sort'] = {'<field>': 'asc'}
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_pagination_required(self):
        """Pagination is expected to be a dictionary."""
        params = deepcopy(self.DEFAULT_PARAMS)
        params['pagination'] = None
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_pagination_size_required(self):
        """Size pagination parameter is expected."""
        params = deepcopy(self.DEFAULT_PARAMS)
        del params['pagination']['size']
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)

    def test_pagination_offset_required(self):
        """Offset pagination parameter is expected."""
        params = deepcopy(self.DEFAULT_PARAMS)
        del params['pagination']['offset']
        with self.assertRaises(BadRequest):
            Events._build_select_query(**params)
