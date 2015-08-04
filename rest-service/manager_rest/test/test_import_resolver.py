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

from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser import constants
from dsl_parser.import_resolver.abstract_import_resolver import \
    AbstractImportResolver
from dsl_parser.import_resolver.default_import_resolver import \
    DefaultImportResolver

from manager_rest import utils
from manager_rest.test.base_test import BaseServerTestCase


def _get_instance_class_path(instance):
    return "%s:%s" % (instance.__module__, instance.__class__.__name__)


class CustomResolver(AbstractImportResolver):
    def __init__(self, param1=None):
        self.params = {'param1': param1}

    def resolve(self, import_url):
        pass


class ResolverTests(BaseServerTestCase):

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
    def _test_resolver(self,
                       mock_parse_dsl,
                       resolver_section,
                       expected_resolver_impl,
                       expected_params,
                       err_msg_contains=None):

        original_get_class_instance = utils.get_class_instance
        get_class_instance_inputs = []

        def mock_get_class_instance(class_path, properties):
            get_class_instance_inputs.append(class_path)
            get_class_instance_inputs.append(properties)
            resolver = original_get_class_instance(class_path, properties)
            get_class_instance_inputs.append(resolver)
            return resolver

        try:
            mock_parse_dsl.return_value = None
            with mock.patch(
                    'manager_rest.blueprints_manager.get_class_instance',
                    new=mock_get_class_instance):
                self._update_provider_context(resolver_section)
                self.put_file(*self.put_blueprint_args())

            if err_msg_contains:
                self.fail("Excpected CloudifyClientError ({0})"
                          .format(err_msg_contains))
            # asserts
            mock_parse_dsl.assert_called_once_with(
                mock.ANY, mock.ANY, mock.ANY)
            resolver = mock_parse_dsl.call_args[0][2]
            self.assertEqual(_get_instance_class_path(resolver),
                             expected_resolver_impl)
            if resolver_section and resolver_section.get(
                    constants.RESOLVER_IMPLEMENTATION_KEY):
                self.assertEqual(
                    get_class_instance_inputs[0], expected_resolver_impl)
                self.assertEqual(get_class_instance_inputs[1], expected_params)
                self.assertEqual(get_class_instance_inputs[2], resolver)

        except CloudifyClientError, ex:
            if err_msg_contains:
                self.assertIn(err_msg_contains, str(ex))
            else:
                raise ex

    def test_implicit_default_resolver(self):
        # import_resolver section is not specified in provider context
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        self._test_resolver(resolver_section=None,
                            expected_resolver_impl=resolver_impl,
                            expected_params=None)

    def test_custom_rules_no_resolver_implementation(self):
        # only the rules are specified in the import_resolver section
        # in the provider context
        params = {
            'rules': [
                {'prefix1': 'prefix2'}
            ]
        }
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_params=params)
        self._test_resolver(resolver_section=resolver_section,
                            expected_resolver_impl=resolver_impl,
                            expected_params=params)

    def test_explicit_default_resolver(self):
        # import_resolver section is specified in provider context
        # points to the default resolver with no rules specified
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_impl=resolver_impl)
        self._test_resolver(resolver_section=resolver_section,
                            expected_resolver_impl=resolver_impl,
                            expected_params=None)

    def test_explicit_default_resolver_and_rules(self):
        # import_resolver section is specified in provider context
        # points to the default resolver with different rules specified
        params = {
            'rules': [
                {'prefix1': 'prefix2'}
            ]
        }
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_impl=resolver_impl,
            resolver_params=params)
        self._test_resolver(resolver_section=resolver_section,
                            expected_resolver_impl=resolver_impl,
                            expected_params=params)

    def test_custom_resolver(self):
        # import_resolver section is specified in provider context
        # points to some custom resolver
        params = {
            'param1': 'value1'
        }
        resolver_impl = _get_instance_class_path(CustomResolver())
        resolver_section = self._create_resolver_section(
            resolver_impl=resolver_impl,
            resolver_params=params)
        self._test_resolver(resolver_section=resolver_section,
                            expected_resolver_impl=resolver_impl,
                            expected_params=params)

    def test_resolver_already_in_app(self):
        params = {
            'param1': 'value1'
        }
        resolver_impl = _get_instance_class_path(CustomResolver())

        resolver_section = self._create_resolver_section(
            resolver_impl=resolver_impl,
            resolver_params=params)

        # update provider context with resolver and
        self._test_resolver(resolver_section=resolver_section,
                            expected_resolver_impl=resolver_impl,
                            expected_params=params)

        # upload blueprint again and check that
        # the expected resolver passed to the parser
        with mock.patch('dsl_parser.tasks.parse_dsl') as mock_parse_dsl:
            self.put_file(*self.put_blueprint_args())
            mock_parse_dsl.assert_called_once_with(
                mock.ANY, mock.ANY, mock.ANY)
            self.assertEqual('CustomResolver',
                             mock_parse_dsl.call_args[0][2].__class__.__name__)
            self.assertDictEqual(mock_parse_dsl.call_args[0][2].params, params)

    def test_illegal_default_resolver_rule(self):
        # wrong rule configuration
        params = {
            'rules': [{'only': 'one', 'pair': 'allowed'}]
        }
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_params=params)
        self._test_resolver(
            resolver_section=resolver_section,
            expected_resolver_impl=resolver_impl,
            expected_params=params,
            err_msg_contains='Each rule must be a '
                             'dictionary with one (key,value) pair')

    def test_illegal_default_resolver_rules_type(self):
        # wrong rules configurations
        params = {
            'rules': 'this should be a list'
        }
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_params=params)
        self._test_resolver(
            resolver_section=resolver_section,
            expected_resolver_impl=resolver_impl,
            expected_params=params,
            err_msg_contains='The `rules` parameter must be a list')

    def test_illegal_default_resolver_rule_type(self):
        # wrong rules configurations
        params = {
            'rules': ['this should be a dict']
        }
        resolver_impl = _get_instance_class_path(DefaultImportResolver())
        resolver_section = self._create_resolver_section(
            resolver_params=params)
        self._test_resolver(
            resolver_section=resolver_section,
            expected_resolver_impl=resolver_impl,
            expected_params=params,
            err_msg_contains='Each rule must be a dictionary')

    def test_illegal_custom_resolver(self):
        # wrong rules configurations
        params = {
            'wrong_param_name': ''
        }
        resolver_impl = _get_instance_class_path(CustomResolver())
        resolver_section = self._create_resolver_section(
            resolver_impl=resolver_impl,
            resolver_params=params)
        self._test_resolver(
            resolver_section=resolver_section,
            expected_resolver_impl=resolver_impl,
            expected_params=params,
            err_msg_contains='Failed to instantiate {0}'
            .format(resolver_impl))
