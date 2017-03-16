#########
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


from unittest import TestCase


from mock import Mock, patch, MagicMock
from nose.plugins.attrib import attr
from voluptuous import Invalid

from manager_rest.rest.rest_decorators import (
    paginate,
    rangeable,
    sortable,
)
from manager_rest.test import base_test


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class PaginateTest(TestCase):

    """Paginate decorator test cases."""

    def test_defaults(self):
        """Size and offset set to zero by default."""
        def verify(pagination):
            self.assertDictEqual(pagination, {})
            return Mock()

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args = {}
            paginate(verify)()

    def test_coercion(self):
        """Values passed as strings are coerced to integers."""
        def verify(pagination):
            self.assertEqual(pagination['size'], 1)
            self.assertEqual(pagination['offset'], 2)
            return Mock()

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args = {
                '_size': '1',
                '_offset': '2',
            }
            paginate(verify)()

    def test_negative(self):
        """Exception raised when negative value is passed."""
        def verify(pagination):
            return Mock()

        with patch('manager_rest.rest.rest_decorators.request') as request:
            for args in [{'_size': '-1', '_offset': '-1'}]:
                request.args = args
                with self.assertRaises(Invalid):
                    paginate(verify)()


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class RangeableTest(TestCase):

    """Rangeable decorator test cases."""

    def test_empty(self):
        """No range arguments mapped to an empty dictionary."""
        def verify(range_filters):
            self.assertDictEqual(range_filters, {})
            return Mock()

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args.getlist.return_value = []
            rangeable(verify)()

    def test_invalid(self):
        """Exception is raised for invalid values."""
        with patch('manager_rest.rest.rest_decorators.request') as request:
            invalid_values = [
                'invalid',
                ',,',  # parameter must be a string
                'field,,',  # one of from or to must be present
                'field,from,to',  # from and to should be datetimes
            ]
            for invalid_value in invalid_values:
                request.args.getlist.return_value = [invalid_value]
                with self.assertRaises(Invalid):
                    rangeable(Mock)()

    def test_valid(self):
        """Valid value should pass validation as expected."""

        valid_datetime = '2016-09-12T00:00:00.0Z'

        def verify(expected_value):
            def verify_helper(range_filters):
                self.assertDictEqual(range_filters, expected_value)
                return Mock()
            return verify_helper

        with patch('manager_rest.rest.rest_decorators.request') as request:
            data = [
                (
                    'field,{0},{0}'.format(valid_datetime),
                    {'field': {'from': valid_datetime, 'to': valid_datetime}},
                ),
                (
                    'field,,{0}'.format(valid_datetime),
                    {'field': {'to': valid_datetime}},
                ),
                (
                    'field,{0},'.format(valid_datetime),
                    {'field': {'from': valid_datetime}},
                ),
            ]

            for (valid_value, expected_value) in data:
                request.args.getlist.return_value = [valid_value]
                rangeable(verify(expected_value))()


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class SortableTest(TestCase):

    """Sortable decorator test cases."""

    def test_defaults(self):
        """Sort is an empty dictionary by default."""
        def verify(sort):
            self.assertDictEqual(sort, {})
            return Mock()

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args.getlist.return_value = []
            sortable()(verify)()

    def test_sort_order(self):
        """Prefix can be used to set sort order."""
        def verify(sort):
            self.assertDictEqual(
                sort,
                {
                    'a': 'asc',
                    'b': 'asc',
                    'c': 'desc',
                },
            )
            return Mock()

        sort_mock = MagicMock()
        sort_mock.resource_fields = ['a', 'b', 'c']

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args.getlist.return_value = ['a', '+b', '-c']
            sortable(sort_mock)(verify)()

    def test_invalid(self):
        """Exception raised when invalid value is passed."""

        with patch('manager_rest.rest.rest_decorators.request') as request:
            request.args.getlist.return_value = [None]
            with self.assertRaises(Invalid):
                sortable()(Mock)()
