#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import mock
from nose.plugins.attrib import attr

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser import constants
from dsl_parser.utils import ResolverInstantiationError


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class UploadBlueprtinsWithImportResolverTests(base_test.BaseServerTestCase):

    def _create_resolver_section(self, resolver_impl=None, resolver_params=[]):
        resolver_section = {}
        if resolver_impl:
            resolver_section[constants.RESOLVER_IMPLEMENTATION_KEY] = \
                resolver_impl
        if resolver_params:
            resolver_section[constants.RESLOVER_PARAMETERS_KEY] = \
                resolver_params
        return resolver_section

    def _update_provider_context(self, resolver_section=None):
        cloudify_section = {}
        if resolver_section:
            cloudify_section[constants.IMPORT_RESOLVER_KEY] = resolver_section
        self.client.manager.update_context(self.id(),
                                           {'cloudify': cloudify_section})

    @mock.patch('dsl_parser.tasks.parse_dsl')
    def test_upload_blueprint_with_resolver(self, mock_parse_dsl):

        resolver_section = 'mock resolver section'
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
        self.assertEqual(create_import_resolver_inputs[0],
                         resolver_section)
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
        with mock.patch('dsl_parser.tasks.parse_dsl') as mock_parse_dsl:
            self.put_file(*self.put_blueprint_args())
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
            except CloudifyClientError, ex:
                self.assertIn(err_msg, str(ex))
