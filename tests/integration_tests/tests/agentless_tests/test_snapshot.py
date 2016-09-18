########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import tempfile
import requests

from integration_tests import utils
from integration_tests import AgentlessTestCase
from cloudify_rest_client.executions import Execution

SNAPSHOTS = 'http://cloudify-tests-files.s3-eu-west-1.amazonaws.com/snapshots/'


class TestSnapshot(AgentlessTestCase):

    def test_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_4.0.zip')
        self._upload_and_restore_snapshot(snapshot_path)
        response = self.client.blueprints.list()
        self.assertEquals(1, len(response), 'expecting 1 blueprints, '
                                            ' got {0}'.format(len(response)))
        response = self.client.deployments.list()
        self.assertEquals(1, len(response), 'expecting 1 deployment, '
                                            ' got {0}'.format(len(response)))

    def test_prev_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_3.4.zip')
        self._upload_and_restore_snapshot(snapshot_path)
        response = self.client.blueprints.list()
        self.assertEquals(1, len(response), 'expecting 1 blueprints, '
                                            ' got {0}'.format(len(response)))
        response = self.client.deployments.list()
        self.assertEquals(1, len(response), 'expecting 1 deployment, '
                                            ' got {0}'.format(len(response)))

    def _get_snapshot(self, name):
        snapshot_url = os.path.join(SNAPSHOTS, name)
        self.logger.info('Retrieving snapshot: {0}'.format(snapshot_url))
        response = requests.get(snapshot_url, stream=True)
        destination_file = tempfile.NamedTemporaryFile(delete=False)
        destination = destination_file.name
        with destination_file as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return destination

    def _upload_and_restore_snapshot(self, snapshot_path):
        snapshot_id = '0'
        self.client.snapshots.upload(snapshot_path, snapshot_id)
        response = self.client.snapshots.list()
        self.assertEqual(1, len(response), 'expecting 1 snapshot results,'
                                           ' got {0}'.format(len(response)))
        snapshot = response[0]
        self.assertEquals(snapshot['id'], snapshot_id)
        self.assertEquals(snapshot['status'], 'uploaded')
        execution = self.client.snapshots.restore(snapshot_id)
        execution = utils.wait_for_execution_to_end(execution,
                                                    timeout_seconds=30)
        if execution.status == Execution.FAILED:
            self.logger.error('Execution error: {0}'.format(execution.error))
        self.assertEqual(Execution.TERMINATED, execution.status)
