#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from nose.plugins.attrib import attr

from manager_rest import manager_exceptions
from manager_rest import resources_v2
from manager_rest.test import base_test
from cloudify_rest_client import exceptions
from manager_rest.blueprints_manager import \
    TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class ProviderContextTestCase(base_test.BaseServerTestCase):

    def initialize_provider_context(self):
        pass  # each test in this class creates its own provider context

    def test_post_provider_context(self):
        result = self.client.manager.create_context(
            'test_provider',
            {'key': 'value'})
        self.assertEqual('ok', result['status'])

    def test_get_provider_context(self):
        self.test_post_provider_context()
        result = self.get('/provider/context').json
        self.assertEqual(result['context']['key'], 'value')
        self.assertEqual(result['name'], 'test_provider')

    def test_post_provider_context_twice_fails(self):
        self.test_post_provider_context()
        try:
            self.test_post_provider_context()
            self.fail('Expected failure when trying to re-post provider '
                      'context')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(409, e.status_code)
            self.assertEqual(
                manager_exceptions.ConflictError.CONFLICT_ERROR_CODE,
                e.error_code)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_global_parallel_executions_limit(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {
                    'transient_deployment_workers_mode': {
                        'enabled': True,
                        'global_parallel_executions_limit': 50
                    }
                }
            })
        self.assertEqual('ok', result['status'])

        provider_ctx = self.client.manager.get_context()
        self.assertEquals(
            50,
            provider_ctx['context']['cloudify'][
                'transient_deployment_workers_mode'].get(
                'global_parallel_executions_limit'))

        provider_ctx_after_update = \
            self._set_global_parallel_executions_limit(5)

        # ensure that other fields haven't changed in the simplest way possible
        provider_ctx_after_update['context']['cloudify'][
            'transient_deployment_workers_mode'][
            'global_parallel_executions_limit'] = 50
        self.assertEquals(provider_ctx, provider_ctx_after_update)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_gpel_with_gpel_section_missing(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {
                    'transient_deployment_workers_mode': {
                        'enabled': True,
                    }
                }
            })
        self.assertEqual('ok', result['status'])

        provider_ctx = self.client.manager.get_context()
        self.assertNotIn(
            'global_parallel_executions_limit',
            provider_ctx['context']['cloudify'][
                'transient_deployment_workers_mode'])

        self._set_global_parallel_executions_limit(5)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_gpel_with_transient_deployment_workers_mode_disabled(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {
                    'transient_deployment_workers_mode': {
                        'enabled': False,
                        'global_parallel_executions_limit': 50
                    }
                }
            })
        self.assertEqual('ok', result['status'])

        self._set_global_parallel_executions_limit(5, is_expect_failure=True)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_gpel_with_transient_deployment_workers_mode_missing(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {}
            })
        self.assertEqual('ok', result['status'])

        self._set_global_parallel_executions_limit(
            5,
            is_expect_failure=not TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_gpel_with_transient_dep_workers_mode_enabled_missing(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {
                    'transient_deployment_workers_mode': {
                        'global_parallel_executions_limit': 50
                    }
                }
            })
        self.assertEqual('ok', result['status'])

        self._set_global_parallel_executions_limit(
            5,
            is_expect_failure=not TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_gpel_with_tdw_mode_missing_and_reversed_default(self):
        tdw_mode_enabled_default = \
            resources_v2.TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT
        resources_v2.TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT =\
            not tdw_mode_enabled_default
        try:
            result = self.client.manager.create_context(
                'test_provider',
                {
                    'cloudify': {}
                })
            self.assertEqual('ok', result['status'])

            # expecting failure when transient workers mode is disabled,
            # which is when it was enabled before reversing the default
            is_expect_failure = tdw_mode_enabled_default

            self._set_global_parallel_executions_limit(
                5,
                is_expect_failure=is_expect_failure)
        finally:
            resources_v2.TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT = \
                tdw_mode_enabled_default

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_modify_global_parallel_executions_limit_with_string_value(self):
        result = self.client.manager.create_context(
            'test_provider',
            {
                'cloudify': {
                    'transient_deployment_workers_mode': {
                        'enabled': True,
                        'global_parallel_executions_limit': 50
                    }
                }
            })
        self.assertEqual('ok', result['status'])

        self._set_global_parallel_executions_limit('5', is_expect_failure=True)

    def test_update_provider_context(self):
        self.test_post_provider_context()
        new_context = {'key': 'new-value'}
        self.client.manager.update_context(
            'test_provider', new_context)
        context = self.client.manager.get_context()
        self.assertEqual(context['context'], new_context)

    def test_update_empty_provider_context(self):
        try:
            self.client.manager.update_context(
                'test_provider',
                {'key': 'value'})
            self.fail('Expected failure due to nonexisting context')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(e.status_code, 404)
            self.assertEqual(e.message, 'Provider Context not found')

    def _set_global_parallel_executions_limit(self, new_limit,
                                              is_expect_failure=False):
        if not is_expect_failure:
            provider_ctx_after_update =\
                self.client.manager.set_global_parallel_executions_limit(
                    new_limit)
            self.assertEquals(
                new_limit,
                provider_ctx_after_update['context']['cloudify'][
                    'transient_deployment_workers_mode'][
                    'global_parallel_executions_limit'])
            return provider_ctx_after_update
        else:
            try:
                self.client.manager.set_global_parallel_executions_limit(
                    new_limit)
                self.fail('expected call for setting global parallel '
                          'executions limit to fail')
            except exceptions.CloudifyClientError as e:
                self.assertEqual(400, e.status_code)
                error = manager_exceptions.BadParametersError
                self.assertEquals(error.BAD_PARAMETERS_ERROR_CODE,
                                  e.error_code)
