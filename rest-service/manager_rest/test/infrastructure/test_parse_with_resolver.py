#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

import os
import mock

from dsl_parser import tasks, constants
from dsl_parser.utils import ResolverInstantiationError

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test.attribute import attr
from manager_rest.test.base_test import (BaseServerTestCase,
                                         LATEST_API_VERSION)
from manager_rest.resolver_with_catalog_support import \
    ResolverWithCatalogSupport


TEST_PACKAGE_NAME = 'cloudify-diamond-plugin'
TEST_PACKAGE_VERSION = '1.3'
TEST_PACKAGE_YAML_FILE = 'mock_blueprint/plugin-cloudify-diamond-plugin.yaml'


@attr(client_min_version=LATEST_API_VERSION,
      client_max_version=LATEST_API_VERSION)
class TestParseWithResolver(BaseServerTestCase):
    def setUp(self):
        super(TestParseWithResolver, self).setUp()
        self.resolver = ResolverWithCatalogSupport()

    def test_successful_plugin_import_resolver(self):
        self.upload_plugin(TEST_PACKAGE_NAME,
                           TEST_PACKAGE_VERSION,
                           TEST_PACKAGE_YAML_FILE)

        dsl_location = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint_with_plugin_import.yaml')

        tasks.parse_dsl(dsl_location=dsl_location,
                        resources_base_path=self.tmpdir,
                        resolver=self.resolver)

    def test_success_with_blueprint_import_resolver(self):
        blueprint_id = 'imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint.yaml', blueprint_id)

        dsl_location = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint_with_blueprint_import.yaml')

        plan = tasks.parse_dsl(dsl_location=dsl_location,
                               resources_base_path=self.tmpdir,
                               resolver=self.resolver)

        nodes = {node["name"] for node in plan[constants.NODES]}

        self.assertEqual(nodes, {"test", "ns--vm", "ns--http_web_server"})


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class UploadBlueprintsWithImportResolverTests(BaseServerTestCase):

    def _update_provider_context(self, resolver_section=None):
        cloudify_section = {}
        if resolver_section:
            cloudify_section[constants.IMPORT_RESOLVER_KEY] = resolver_section
        self.client.manager.update_context(self.id(),
                                           {'cloudify': cloudify_section})

    @mock.patch('dsl_parser.tasks.parse_dsl')
    def test_upload_blueprint_with_resolver(self, mock_parse_dsl):

        resolver_section = {'rules': ['mock resolver section']}
        create_import_resolver_inputs = []

        def mock_create_import_resolver(resolver_section):
            create_import_resolver_inputs.append(resolver_section)
            return 'mock expected import resolver'

        mock_parse_dsl.return_value = dict()
        with mock.patch(
                'dsl_parser.utils.create_import_resolver',
                new=mock_create_import_resolver):
            self._update_provider_context(resolver_section)
            self.put_file(*self.put_blueprint_args())

        # asserts
        mock_parse_dsl.assert_called_once_with(
            mock.ANY, mock.ANY,
            resolver='mock expected import resolver',
            validate_version=mock.ANY)

        # just check one key - additional keys might have been added
        # when creating the parser context
        self.assertEqual(create_import_resolver_inputs[0]['rules'],
                         resolver_section['rules'])

        self.assertEqual(self.app.application.parser_context['resolver'],
                         'mock expected import resolver')

    def test_resolver_update_in_app(self):
        # upload blueprint
        self.test_upload_blueprint_with_resolver()
        # update current app
        self.app.application.parser_context = {
            'resolver': 'mock resolver',
            'validate_version': True
        }
        # upload blueprint again and check that
        # the expected resolver passed to the parser
        with mock.patch(
                'dsl_parser.tasks.parse_dsl',
                mock.MagicMock(return_value={})
        ) as mock_parse_dsl:
            self.put_file(*self.put_blueprint_args(blueprint_id='bp-2'))
            mock_parse_dsl.assert_called_once_with(
                mock.ANY, mock.ANY,
                resolver='mock resolver',
                validate_version=mock.ANY)

    def test_failed_to_initialize_resolver(self):

        err_msg = 'illegal default resolve initialization'

        def mock_create_import_resolver(_):
            raise ResolverInstantiationError(err_msg)

        with mock.patch('dsl_parser.utils.create_import_resolver',
                        new=mock_create_import_resolver):
            try:
                self._update_provider_context()
                self.fail('CloudifyClientError expected')
            except CloudifyClientError as ex:
                self.assertIn(err_msg, str(ex))
