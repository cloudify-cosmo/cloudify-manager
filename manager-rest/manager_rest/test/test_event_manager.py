#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
#

__author__ = 'idanmo'


import unittest
import tempfile
import shutil
import json
import os
from os import path
from events_manager import EventsManager


class EventManagerTests(unittest.TestCase):
    """Test EventManager functionality."""

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp()
        cls.events_manager = EventsManager(cls.tempdir)
        events = [{'key1': 'value1'}, {'key2': 'value2'}]
        deployment_id = 'deployment_0'
        cls.events_file = path.join(cls.tempdir, "{0}.log".format(deployment_id))
        cls.create_events_file(cls.events_file, events)

    @classmethod
    def tearDownClass(cls):
        if cls.tempdir:
            shutil.rmtree(cls.tempdir)

    @staticmethod
    def create_events_file(filename, events=[]):
        with open(filename, 'w') as f:
            for event in events:
                f.write("{0}{1}".format(json.dumps(event), os.linesep))

    def test_no_events(self):
        deployment_id = 'no_events'
        result = self.events_manager.get_deployment_events(deployment_id, only_bytes=True)
        self.assertEquals(0, result.deployment_events_bytes)
        result = self.events_manager.get_deployment_events(deployment_id, only_bytes=False)
        self.assertEquals(-1, result.first_event)
        self.assertEquals(-1, result.last_event)
        self.assertEquals(0, len(result.events))
        self.assertEquals(0, result.deployment_total_events)
        self.assertEquals(0, result.deployment_events_bytes)

    def test_get_deployment_events_bytes(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id, only_bytes=True)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(-1, result.first_event)
        self.assertEquals(-1, result.last_event)
        self.assertEquals(0, len(result.events))
        self.assertEquals(-1, result.deployment_total_events)

    def test_get_deployment_events(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(0, result.first_event)
        self.assertEquals(1, result.last_event)
        self.assertEquals(2, len(result.events))
        self.assertEquals(2, result.deployment_total_events)

    def test_get_deployment_events_with_from_event(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id, first_event=1)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(1, result.first_event)
        self.assertEquals(1, result.last_event)
        self.assertEquals(1, len(result.events))
        self.assertEquals(2, result.deployment_total_events)

    def test_get_deployment_events_from_event_count(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id, first_event=0, events_count=1)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(0, result.first_event)
        self.assertEquals(0, result.last_event)
        self.assertEquals(1, len(result.events))
        self.assertEquals(2, result.deployment_total_events)

    def test_get_deployment_events_from_not_in_range(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id, first_event=5)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(-1, result.first_event)
        self.assertEquals(-1, result.last_event)
        self.assertEquals(0, len(result.events))
        self.assertEquals(2, result.deployment_total_events)

    def test_get_deployment_events_zero_count(self):
        deployment_id = 'deployment_0'
        result = self.events_manager.get_deployment_events(deployment_id, first_event=0, events_count=0)
        self.assertEquals(path.getsize(self.events_file), result.deployment_events_bytes)
        self.assertEquals(-1, result.first_event)
        self.assertEquals(-1, result.last_event)
        self.assertEquals(0, len(result.events))
        self.assertEquals(2, result.deployment_total_events)
