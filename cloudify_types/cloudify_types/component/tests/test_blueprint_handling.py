# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from cloudify.state import current_ctx
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from ..constants import EXTERNAL_RESOURCE
from ..operations import upload_blueprint
from .base_test_suite import ComponentTestBase, REST_CLIENT_EXCEPTION


class TestBlueprint(ComponentTestBase):

    def setUp(self):
        super(TestBlueprint, self).setUp()
        self.resource_config = dict()
        self.resource_config['resource_config'] = {}
        self.archive = 'sample_file.zip'

        self._ctx._resources = {self.archive: 'Sample Blueprint'}
        current_ctx.set(self._ctx)

    def test_upload_blueprint_rest_client_error(self):
        self.cfy_mock_client.blueprints._upload = REST_CLIENT_EXCEPTION

        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['blueprint_id'] = 'blu_name'
        blueprint_params['blueprint']['blueprint_archive'] = self.archive
        self.resource_config['resource_config'] = blueprint_params

        error = self.assertRaises(NonRecoverableError,
                                  upload_blueprint,
                                  operation='upload_blueprint',
                                  **self.resource_config)

        self.assertIn('action "_upload" failed', str(error))

    def test_successful_upload_existing_blueprint(self):
        self.cfy_mock_client.blueprints._upload = (
            mock.MagicMock(
                side_effect=CloudifyClientError('already exists')))

        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['id'] = 'blu_name'
        blueprint_params['blueprint']['blueprint_archive'] = self.archive
        self.resource_config['resource_config'] = blueprint_params

        output = upload_blueprint(operation='upload_blueprint',
                                  **self.resource_config)
        self.assertTrue(output)

    def test_upload_blueprint_success(self):
        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['id'] = 'blu_name'
        blueprint_params['blueprint']['blueprint_archive'] = self.archive
        self.resource_config['resource_config'] = blueprint_params

        output = upload_blueprint(operation='upload_blueprint',
                                  **self.resource_config)
        self.assertTrue(output)

    def test_upload_blueprint_fail_missing_archive(self):
        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['id'] = 'blu_name'
        self.resource_config['resource_config'] = blueprint_params

        error = self.assertRaises(NonRecoverableError,
                                  upload_blueprint,
                                  operation='upload_blueprint',
                                  **self.resource_config)

        self.assertIn('No blueprint_archive supplied, but '
                      'external_resource is False', str(error))

    def test_uploading_existing_blueprint_id_when_using_external(self):
        self.cfy_mock_client.blueprints.set_existing_objects(
            [{'id': 'blu'}])

        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['id'] = 'blu_name'
        blueprint_params['blueprint']['blueprint_archive'] = self.archive
        blueprint_params['blueprint'][EXTERNAL_RESOURCE] = False
        self.resource_config['resource_config'] = blueprint_params

        output = upload_blueprint(operation='upload_blueprint',
                                  **self.resource_config)
        self.assertTrue(output)

    def test_upload_blueprint_use_not_existing_external(self):
        blueprint_params = dict()
        blueprint_params['blueprint'] = {}
        blueprint_params['blueprint']['id'] = 'test'
        blueprint_params['blueprint'][EXTERNAL_RESOURCE] = True
        self.resource_config['resource_config'] = blueprint_params

        error = self.assertRaises(NonRecoverableError,
                                  upload_blueprint,
                                  operation='upload_blueprint',
                                  **self.resource_config)

        self.assertIn('Blueprint ID \"{0}\" does not exist'.format(
            'test'), str(error))
