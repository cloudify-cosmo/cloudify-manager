#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import json
from uuid import uuid4

from cloudify.cluster_status import MANAGER_STATUS_REPORTER

from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql
from integration_tests.tests.utils import get_resource
from integration_tests.tests.constants import MANAGER_PYTHON


class TestManagerStatusReporter(AgentlessTestCase):
    def test_status_reporter_has_correct_key_after_snapshot_restore(self):
        snapshot_id = "test_" + str(uuid4())
        initial_token_key, _ = self._get_reporter_token_key()

        self._update_reporter_token_key('a' * 32)

        execution = self.client.snapshots.create(snapshot_id, False)
        self.wait_for_execution_to_end(execution)

        self._update_reporter_token_key(initial_token_key)

        execution = self.client.snapshots.restore(snapshot_id)
        self.client.maintenance_mode.activate()
        self.wait_for_snapshot_restore_to_end(execution.id)
        self.client.maintenance_mode.deactivate()
        self.wait_for_execution_to_end(execution)

        current_token_key, reporter_id = self._get_reporter_token_key()
        self.assertEqual(initial_token_key, current_token_key)

        reporter_configuration = self._get_reporter_configuration()
        encoded_id = self._get_reporter_encoded_user_id(reporter_id)
        full_token = '{0}{1}'.format(encoded_id, initial_token_key)
        self.assertEqual(reporter_configuration['token'], full_token)

        reporter_service_status = self.execute_on_manager(
            "sh -c 'systemctl is-active cloudify-status-reporter || :'"
        ).stdout.strip()
        self.assertEqual(reporter_service_status, 'active')

    def _get_reporter_encoded_user_id(self, reporter_id):
        update_script = get_resource('scripts/getencodeduser.py')
        script_dst = '/tmp/getencodeduser.py'
        self.copy_file_to_manager(update_script, script_dst)
        encoded_id = self.execute_on_manager(
            '{0} {1} --user-id {2}'
            ''.format(MANAGER_PYTHON, script_dst, reporter_id)).stdout.strip()
        return encoded_id

    def _get_reporter_configuration(self):
        reporter_configuration_json = self.execute_on_manager(
            "cfy_manager status-reporter show-configuration --json").stdout
        reporter_configuration = json.loads(reporter_configuration_json)
        return reporter_configuration

    def _get_reporter_token_key(self):
        query = """
        SELECT
            json_build_object(
                'id', id,
                'username', username,
                'api_token_key', api_token_key
            )
        FROM users
        WHERE username = '{0}';
        """.format(MANAGER_STATUS_REPORTER)
        result = postgresql.run_query(query)
        if result['status'] != 'ok':
            self.fail("Failed to fetch reporter token key. Error msg: '{0}'."
                      "".format(result['status']))

        reporter = result['all'][0][0]
        return reporter['api_token_key'], reporter['id']

    def _update_reporter_token_key(self, new_token_key):
        query = """
        UPDATE users
        SET api_token_key = '{0}'
        WHERE username = '{1}';
        """.format(new_token_key, MANAGER_STATUS_REPORTER)
        result = postgresql.run_query(query, fetch_results=False)
        if result['status'] != 'ok':
            self.fail("Failed to update reporter token key. Error msg: '{0}'."
                      "".format(result['status']))
