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

from dateutil import tz
from mock import patch
from nose.plugins.attrib import attr

from manager_rest.storage.models_base import LocalDateTime


@attr(client_min_version=1, client_max_version=1)
class LocalDateTimeTest(TestCase):

    """Verify local datetime serialization."""

    def _test_datetime(self, timezone, db_value, expected_value):
        """Test datetime serialization helper."""
        local_date_time = LocalDateTime()

        with patch('manager_rest.storage.models_base.tz.tzlocal') as tz_local:
            tz_local.return_value = timezone
            value = local_date_time.process_result_value(db_value, None)
        self.assertEqual(value, expected_value)

    def test_utc(self):
        """UTC datetime is serialized using Z for the timezone."""
        self._test_datetime(
            tz.gettz('UTC'),
            datetime(2016, 12, 9, 8, 12, 34, 567890),
            '2016-12-09T08:12:34.567Z',
        )

    def test_utc_zero_milliseconds(self):
        """UTC datetime with zero milliseconds is serialized."""
        self._test_datetime(
            tz.gettz('UTC'),
            datetime(2016, 12, 9, 8, 12, 34, 0),
            '2016-12-09T08:12:34.000Z',
        )

    def test_asia_jerusalem(self):
        """Jerusalem datetime is serialized using time zone offset."""
        self._test_datetime(
            tz.gettz('Asia/Jerusalem'),
            datetime(2016, 12, 9, 8, 12, 34, 567890),
            '2016-12-09T10:12:34.567+02:00',
        )

    def test_asia_jerusalem_zero_milliseconds(self):
        """Jerusalem datetime with zero milliseconds is serialized."""
        self._test_datetime(
            tz.gettz('Asia/Jerusalem'),
            datetime(2016, 12, 9, 8, 12, 34, 0),
            '2016-12-09T10:12:34.000+02:00',
        )
