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

import copy
import requests

from cloudify.models_states import BlueprintUploadState
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import wait_for_blueprint_upload


class BlueprintUploadTest(AgentlessTestCase):
    def test_blueprint_upload(self):
        blueprint_id = 'bp'
        blueprint_filename = 'empty_blueprint.yaml'
        self.client.blueprints.upload(
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id
        )
        self._verify_blueprint_uploaded(blueprint_id, blueprint_filename)

    def test_blueprint_upload_from_url(self):
        blueprint_id = 'bp-url'
        blueprint_filename = 'blueprint.yaml'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/the-not-blueprint-master.zip'
        self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id)
        self._verify_blueprint_uploaded(blueprint_id, blueprint_filename)

    def test_blueprint_upload_from_unavailable_url(self):
        blueprint_id = 'bp-url-unavailable'
        archive_url = 'http://www.fake.url/does/not/exist'
        self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id)
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_UPLOADING,
            'Max retries exceeded with url'
        )

    def test_blueprint_upload_from_malformed_url(self):
        blueprint_id = 'bp-url-malformed'
        archive_url = 'malformed/url_is.bad'
        requests.put(
            'http://{0}/api/v3.1/blueprints/{1}'.format(self.get_manager_ip(),
                                                        blueprint_id),
            headers=self.client._client.headers,
            params={'blueprint_archive_url': archive_url},
            verify=False
        )
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_UPLOADING,
            "Invalid URL '{}': No schema supplied".format(archive_url)
        )

    def test_blueprint_upload_from_url_bad_archive_format(self):
        blueprint_id = 'bp-url-bad-format'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/index.html'
        self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id)
        # This is caught at `upload_archive_to_file_server`, before extracting
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_UPLOADING,
            'Blueprint archive is of an unrecognized format'
        )

    def test_blueprint_upload_from_url_invalid_archive_structure(self):
        blueprint_id = 'bp-url-bad-structure'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/not-a-valid-archive.zip'
        self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id)
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_EXTRACTING,
            "Archive must contain exactly 1 directory"
        )

    def test_blueprint_upload_from_url_missing_yaml(self):
        blueprint_id = 'bp-url-missing-yaml'
        blueprint_filename = 'fancy_name.yaml'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/the-not-blueprint-master.zip'
        self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id,
            blueprint_filename=blueprint_filename
        )
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_EXTRACTING,
            '{0} does not exist in the application '
            'directory'.format(blueprint_filename)
        )

    def test_blueprint_reupload_after_fail(self):
        blueprint_id = 're-bp'
        self.client.blueprints.upload(resource('dsl/basic.yaml'),
                                      entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, False)
        blueprint = self.client.blueprints.get(blueprint_id)

        # this should fail due to cloudmock plugin not uploaded
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)
        self.assertEqual(blueprint.plan, None)
        self.assertRegexpMatches(blueprint['error'],
                                 'Plugin cloudmock .* not found')
        original_creation_time = blueprint['created_at']

        self.client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                      entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, False)
        blueprint = self.client.blueprints.get(blueprint_id)

        self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)
        self.assertNotEqual(blueprint.plan, None)
        self.assertNotEqual(blueprint['created_at'], original_creation_time)

    def test_blueprint_upload_batch(self):
        blueprint_filename = 'empty_blueprint.yaml'
        for i in range(5):
            self.client.blueprints.upload(
                resource('dsl/{}'.format(blueprint_filename)),
                entity_id='bp_{}'.format(i)
            )
        for i in range(5):
            blueprint_id = 'bp_{}'.format(i)
            wait_for_blueprint_upload(blueprint_id, self.client, False)
            blueprint = self.client.blueprints.get(blueprint_id)
            self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)
            self.assertEqual(blueprint.main_file_name, blueprint_filename)
            self.assertNotEqual(blueprint.plan, None)

    def test_blueprint_upload_bad_import_resolver(self):
        provider_context = \
            copy.deepcopy(self.client.manager.get_context()['context'])

        cloudify_section = {
            'import_resolver': {
                'implementation':
                    'dsl_parser.import_resolver.default_import_resolver:'
                    'DefaultImportResolver'
            }
        }
        self.client.manager.update_context(self.id(),
                                           {'cloudify': cloudify_section})

        blueprint_id = 'bp-resolver-error'
        self.client.blueprints.upload(resource('dsl/basic.yaml'),
                                      entity_id=blueprint_id)
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.FAILED_PARSING,
            'Failed to instantiate resolver'
        )
        # restore provider context
        self.client.manager.update_context(self.id(), provider_context)

    def test_blueprint_upload_malformed_dsl(self):
        blueprint_id = 'bp-malformed-dsl'
        self.client.blueprints.upload(resource('dsl/invalid_dsl.yaml'),
                                      entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, False)
        self._verify_blueprint_failed_uploading_and_assert_error(
            blueprint_id, BlueprintUploadState.INVALID,
            "Expected 'dict' type but found 'string' type"
        )

    def _verify_blueprint_uploaded(self, blueprint_id, blueprint_filename):
        wait_for_blueprint_upload(blueprint_id, self.client, False)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)
        self.assertEqual(blueprint.main_file_name, blueprint_filename)
        self.assertNotEqual(blueprint.plan, None)
        self._verify_blueprint_files(blueprint_id, blueprint_filename)

    def _verify_blueprint_failed_uploading_and_assert_error(
            self, blueprint_id, state, error):
        wait_for_blueprint_upload(blueprint_id, self.client, False)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], state)
        self.assertRegexpMatches(blueprint['error'], error)

    def _verify_blueprint_files(self, blueprint_id, blueprint_filename):
        # blueprint available in manager resources
        admin_headers = self.client._client.headers
        resp = requests.get(
            'https://{0}:53333/resources/blueprints/default_tenant/'
            '{1}/{2}'.format(self.get_manager_ip(),
                             blueprint_id,
                             blueprint_filename),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code, requests.status_codes.codes.ok)
        # blueprint archive available in uploaded blueprints
        resp = requests.get(
            'https://{0}:53333/uploaded-blueprints/default_tenant/'
            '{1}/{1}.tar.gz'.format(
                self.get_manager_ip(),
                blueprint_id),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code, requests.status_codes.codes.ok)


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
