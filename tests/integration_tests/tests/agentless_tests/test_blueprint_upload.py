########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import requests
import requests.status_codes

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class BlueprintValidateTest(AgentlessTestCase):
    def test_blueprint_validate(self):
        blueprint_id = 'bp-validate'
        blueprint_filename = 'empty_blueprint.yaml'
        self._verify_blueprint_validation_with_message(
            blueprint_id,
            resource('dsl/{}'.format(blueprint_filename)),
            'Blueprint validated.')

    def test_blueprint_validate_from_url(self):
        blueprint_id = 'bp-url-validate'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/the-not-blueprint-master.zip'
        self._verify_blueprint_validation_with_message(
            blueprint_id,
            archive_url,
            'Blueprint validated.')

    def test_blueprint_validate_invalid_blueprint(self):
        blueprint_id = 'bp-bad-schema'
        blueprint_filename = 'invalid_blueprint.yaml'
        self._verify_blueprint_validation_with_message(
            blueprint_id,
            resource('dsl/{}'.format(blueprint_filename)),
            "Invalid blueprint - 'foo' is not in schema.")

    def _verify_blueprint_validation_with_message(
            self, blueprint_id, blueprint_resource, message):
        self.client.blueprints.validate(
            blueprint_resource,
            entity_id=blueprint_id
        )
        temp_blueprint_id = self._assert_blueprint_validation_message(
            blueprint_id, message)
        self._assert_cleanup(temp_blueprint_id)

    def _assert_blueprint_validation_message(self, blueprint_id, message):
        execution = [
            ex for ex in
            self.client.executions.list(workflow_id='upload_blueprint') if
            blueprint_id in ex['parameters']['blueprint_id']
        ][-1]   # get latest upload execution for blueprint
        try:
            self.wait_for_execution_to_end(execution)
        except RuntimeError as e:
            if 'Workflow execution failed' not in str(e):
                raise e
        event_messages = [ev for ev in self.client.events.list(execution.id)
                          if message in ev['message']]
        self.assertNotEqual(0, len(event_messages))
        return execution['parameters']['blueprint_id']

    def _assert_cleanup(self, blueprint_id):
        # blueprint entry deleted
        self.assertRaisesRegexp(CloudifyClientError,
                                '404: .* not found',
                                self.client.blueprints.get,
                                blueprint_id)
        admin_headers = self.client._client.headers
        # blueprint folder deleted from uploaded blueprints
        resp = requests.get(
            'https://{0}:53333/resources/uploaded-blueprints/'
            'default_tenant/{1}'.format(self.get_manager_ip(), blueprint_id),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code,
                         requests.status_codes.codes.not_found)
