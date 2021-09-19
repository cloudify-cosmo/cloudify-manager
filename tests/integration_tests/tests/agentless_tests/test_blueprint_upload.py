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
import os.path
import time
import pytest
import requests

from cloudify.models_states import BlueprintUploadState
from cloudify.utils import ipv6_url_compat
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import (wait_for_blueprint_upload,
                                           get_executions,
                                           get_events)

pytestmark = pytest.mark.group_deployments


class BlueprintUploadTest(AgentlessTestCase):

    def test_blueprint_upload(self):
        blueprint_id = 'bp'
        blueprint_filename = 'empty_blueprint.yaml'
        blueprint = self.client.blueprints.upload(
            resource('dsl/{}'.format(blueprint_filename)),
            entity_id=blueprint_id
        )
        self._verify_blueprint_uploaded(blueprint, blueprint_filename)

    def test_blueprint_upload_from_url(self):
        blueprint_id = 'bp-url'
        blueprint_filename = 'blueprint.yaml'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/the-not-blueprint-master.zip'
        blueprint = self.client.blueprints.publish_archive(
            archive_url,
            blueprint_id)
        self._verify_blueprint_uploaded(blueprint, blueprint_filename)

    def test_blueprint_upload_from_unavailable_url(self):
        blueprint_id = 'bp-url-unavailable'
        archive_url = 'http://www.fake.url/does/not/exist'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'failed uploading.* Max retries exceeded with url',
            self.client.blueprints.publish_archive,
            archive_url,
            blueprint_id)

    def test_blueprint_upload_from_malformed_url(self):
        blueprint_id = 'bp-url-malformed'
        archive_url = 'malformed/url_is.bad'
        response = requests.put(
            'https://{0}/api/v3.1/blueprints/{1}'.format(
                ipv6_url_compat(self.get_manager_ip()), blueprint_id),
            headers=self.client._client.headers,
            params={'blueprint_archive_url': archive_url},
            verify=False
        )
        self.assertEqual(response.status_code, 400)
        self.assertRegexpMatches(
            response.json()['message'],
            "failed uploading.* "
            "Invalid URL '{}': No schema supplied".format(archive_url))

    def test_blueprint_upload_from_url_bad_archive_format(self):
        blueprint_id = 'bp-url-bad-format'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/index.html'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'failed uploading.* '
            'Blueprint archive is of an unrecognized format',
            self.client.blueprints.publish_archive,
            archive_url,
            blueprint_id)

    def test_blueprint_upload_from_url_invalid_archive_structure(self):
        blueprint_id = 'bp-url-bad-structure'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/not-a-valid-archive.zip'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'failed extracting.* '
            'Archive must contain exactly 1 directory',
            self.client.blueprints.publish_archive,
            archive_url,
            blueprint_id)

    def test_blueprint_upload_from_url_missing_yaml(self):
        blueprint_id = 'bp-url-missing-yaml'
        blueprint_filename = 'fancy_name.yaml'
        archive_url = 'https://cloudify-tests-files.s3-eu-west-1.amazonaws' \
                      '.com/blueprints/the-not-blueprint-master.zip'
        self.assertRaisesRegexp(
            CloudifyClientError,
            'failed extracting.* {0} does not exist in the application '
            'directory'.format(blueprint_filename),
            self.client.blueprints.publish_archive,
            archive_url,
            blueprint_id,
            blueprint_filename=blueprint_filename)

    def test_blueprint_reupload_after_fail(self):
        blueprint_id = 're-bp'
        # this should fail due to cloudmock plugin not uploaded
        self.assertRaisesRegexp(CloudifyClientError,
                                'Couldn\'t find plugin "cloudmock"',
                                self.client.blueprints.upload,
                                resource('dsl/basic.yaml'),
                                entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.INVALID)
        self.assertEqual(blueprint.plan, None)
        original_creation_time = blueprint['created_at']

        self.client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                      entity_id=blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint['state'], BlueprintUploadState.UPLOADED)
        self.assertNotEqual(blueprint.plan, None)
        self.assertNotEqual(blueprint['created_at'], original_creation_time)

    def test_blueprint_upload_batch_async(self):
        blueprint_filename = 'empty_blueprint.yaml'
        for i in range(5):
            self.client.blueprints.upload(
                resource('dsl/{}'.format(blueprint_filename)),
                entity_id='bp_{}'.format(i),
                async_upload=True
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
        self.assertRaisesRegexp(
            CloudifyClientError,
            'failed parsing.* Failed to instantiate resolver',
            self.client.blueprints.upload,
            resource('dsl/basic.yaml'),
            entity_id=blueprint_id)

        # restore provider context
        self.client.manager.update_context(self.id(), provider_context)

    def test_blueprint_upload_malformed_dsl(self):
        blueprint_id = 'bp-malformed-dsl'
        self.assertRaisesRegexp(
            CloudifyClientError,
            "invalid.* Expected 'dict' type but found 'string' type",
            self.client.blueprints.upload,
            resource('dsl/invalid_dsl.yaml'),
            entity_id=blueprint_id)

    def _verify_blueprint_uploaded(self, blueprint, blueprint_filename):
        self.assertEqual(blueprint.state, BlueprintUploadState.UPLOADED)
        self.assertEqual(blueprint.main_file_name, blueprint_filename)
        self.assertNotEqual(blueprint.plan, None)
        self._verify_blueprint_files(blueprint.id, blueprint_filename)

    def _verify_blueprint_files(self, blueprint_id, blueprint_filename):
        # blueprint available in manager resources
        admin_headers = self.client._client.headers
        resp = requests.get(
            'https://{0}:53333/resources/blueprints/default_tenant/'
            '{1}/{2}'.format(ipv6_url_compat(self.get_manager_ip()),
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
                ipv6_url_compat(self.get_manager_ip()),
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
        time.sleep(3)
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
            'default_tenant/{1}'.format(ipv6_url_compat(self.get_manager_ip()),
                                        blueprint_id),
            headers=admin_headers,
            verify=False
        )
        self.assertEqual(resp.status_code,
                         requests.status_codes.codes.not_found)


class BlueprintImportedTest(AgentlessTestCase):

    def test_blueprints_separate_delete_success(self):
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'simple_deployment.yaml')),
            entity_id='first')
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'simple_deployment.yaml')),
            entity_id='second',
            async_upload=True)
        self.client.blueprints.delete('first')
        wait_for_blueprint_upload('second', self.client)
        self.wait_for_all_executions_to_end()
        self.client.blueprints.delete('second')

    def test_blueprints_imported_upload_success(self):
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'simple_deployment.yaml')),
            entity_id='imported')
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'deployment_with_import.yaml')),
            entity_id='main')
        self.client.blueprints.delete('main')
        self.client.blueprints.delete('imported')

    def test_blueprints_imported_upload_failure(self):
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'simple_deployment.yaml')),
            entity_id='imported')
        self.client.blueprints.upload(
            resource(os.path.join('dsl', 'deployment_with_import.yaml')),
            entity_id='main',
            async_upload=True)
        self.client.blueprints.delete('imported')
        wait_for_blueprint_upload('main', self.client, require_success=False)
        self.wait_for_all_executions_to_end(require_success=False)

        message = ''
        for execution in get_executions(self.client,
                                        workflow_id='upload_blueprint',
                                        parameters__blueprint_id='main'):
            assert execution['status'] == 'failed'
            for event in get_events(self.client,
                                    execution_id=execution['id'],
                                    event_type='workflow_failed'):
                message = event['message']
        assert "Requested blueprint import `imported` was not found" in message
        self.client.blueprints.delete('main')
