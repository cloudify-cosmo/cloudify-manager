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


import tempfile
import shutil
import json
import os
from os import path
from base_test import BaseServerTestCase


class DeploymentsEventsTestCase(BaseServerTestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        events = [{'key1': 'value1'}, {'key2': 'value2'}, {'key3': 'value3'}]
        deployment_id = 'deployment_0'
        self.events_file = path.join(self.tempdir, "{0}.log".format(deployment_id))
        self.create_events_file(self.events_file, events)
        super(DeploymentsEventsTestCase, self).setUp()

    def tearDown(self):
        super(DeploymentsEventsTestCase, self).tearDown()
        shutil.rmtree(self.tempdir)

    def create_configuration(self):
        config = super(DeploymentsEventsTestCase, self).create_configuration()
        config.events_files_path = self.tempdir
        return config

    @staticmethod
    def create_events_file(filename, events=[]):
        with open(filename, 'w') as f:
            for event in events:
                f.write("{0}{1}".format(json.dumps(event), os.linesep))

    def assert_bytes(self, result, expected_bytes):
        self.assertEqual(expected_bytes, int(result.headers['Deployment-Events-Bytes']))

    def assert_result(self,
                      result,
                      deployment_id='deployment_0',
                      first_event=-1,
                      last_event=-1,
                      deployment_total_events=0):
        self.assertEqual(deployment_id, result.json['id'])
        self.assertEqual(first_event, result.json['firstEvent'])
        self.assertEqual(last_event, result.json['lastEvent'])
        self.assertEqual(deployment_total_events, result.json['deploymentTotalEvents'])
        if first_event != -1 and last_event != -1:
            self.assertEqual(last_event - first_event + 1, len(result.json['events']))
        else:
            self.assertEqual(0, len(result.json['events']))
        self.assert_bytes(result, path.getsize(self.events_file))

    def test_no_events_head(self):
        result = self.head('/deployments/some_id/events')
        self.assertEqual(200, result.status_code)
        self.assert_bytes(result, 0)

    def test_no_events(self):
        result = self.get('/deployments/some_id/events')
        self.assertEqual(200, result.status_code)
        self.assert_bytes(result, 0)

    def test_events(self):
        result = self.get('/deployments/deployment_0/events')
        self.assert_result(result,
                           first_event=0,
                           last_event=2,
                           deployment_total_events=3)

    def test_from_argument(self):
        result = self.get('/deployments/deployment_0/events?from=0')
        self.assert_result(result,
                           first_event=0,
                           last_event=2,
                           deployment_total_events=3)
        result = self.get('/deployments/deployment_0/events?from=1')
        self.assert_result(result,
                           first_event=1,
                           last_event=2,
                           deployment_total_events=3)

    def test_events_count_argument(self):
        result = self.get('/deployments/deployment_0/events?from=0&count=2')
        self.assert_result(result,
                           first_event=0,
                           last_event=1,
                           deployment_total_events=3)

    def test_from_argument_not_in_range(self):
        result = self.get('/deployments/deployment_0/events?from=5')
        self.assert_result(result,
                           first_event=-1,
                           last_event=-1,
                           deployment_total_events=3)

    def test_wrong_arguments(self):
        result = self.get('/deployments/deployment_0/events?from=-1')
        self.assertEqual(400, result.status_code)
        result = self.get('/deployments/deployment_0/events?from=0&count=-1')
        self.assertEqual(400, result.status_code)
        result = self.get('/deployments/deployment_0/events?from=abcd')
        self.assertEqual(400, result.status_code)
        result = self.get('/deployments/deployment_0/events?from=0&count=abcd')
        self.assertEqual(400, result.status_code)
