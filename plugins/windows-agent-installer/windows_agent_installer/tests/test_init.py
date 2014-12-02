#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import unittest

from cloudify.context import BootstrapContext
from cloudify.exceptions import NonRecoverableError
from cloudify.mocks import MockCloudifyContext

from windows_agent_installer import constants, init_worker_installer


@init_worker_installer
def init_cloudify_agent_configuration(*args, **kwargs):
    if 'cloudify_agent' in kwargs:
        return kwargs['cloudify_agent']
    else:
        raise ValueError("'cloudify_agent' not set by init_worker_installer")


class InitTest(unittest.TestCase):

    def test_cloudify_agent_config_duplication(self):
        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'cloudify_agent':
                                              {'user': 'prop_user',
                                               'password': 'prop_password'},
                                              'ip': 'dummy_ip'},
                                  operation='create')
        expected_message = "'cloudify_agent' is configured both as a node " \
                           "property and as an invocation input parameter" \
                           " for operation 'create'"
        self.assertRaisesRegexp(NonRecoverableError, expected_message,
                                init_cloudify_agent_configuration, ctx,
                                cloudify_agent={'user': 'input_user',
                                                'password': 'input_password'})

    def test_cloudify_agent_set_as_property(self):

        try:
            from windows_agent_installer import winrm_runner
            real_test_connectivity = winrm_runner.WinRMRunner.test_connectivity

            def mock_test_connectivity(self):
                pass

            winrm_runner.WinRMRunner.test_connectivity = mock_test_connectivity
            ctx = MockCloudifyContext(
                node_id='node_id',
                properties={'cloudify_agent': {'user': 'prop_user',
                                               'password': 'prop_password'},
                            'ip': 'ip'})
            cloudify_agent = init_cloudify_agent_configuration(ctx)
        finally:
            winrm_runner.WinRMRunner.test_connectivity = real_test_connectivity

        self.assertEqual(cloudify_agent['user'], 'prop_user')
        self.assertEqual(cloudify_agent['password'], 'prop_password')

    def test_cloudify_agent_set_as_input(self):

        try:
            from windows_agent_installer import winrm_runner
            real_test_connectivity = winrm_runner.WinRMRunner.test_connectivity

            def mock_test_connectivity(self):
                pass
            winrm_runner.WinRMRunner.test_connectivity = mock_test_connectivity

            ctx = MockCloudifyContext(node_id='node_id',
                                      properties={'ip': 'ip'})
            cloudify_agent = init_cloudify_agent_configuration(
                ctx, cloudify_agent={'user': 'input_user',
                                     'password': 'input_password'})
        finally:
            winrm_runner.WinRMRunner.test_connectivity = real_test_connectivity

        self.assertEqual(cloudify_agent['user'], 'input_user')
        self.assertEqual(cloudify_agent['password'], 'input_password')

    def test_cloudify_agent_not_set(self):
        ctx = MockCloudifyContext(node_id='node_id', properties={'ip': 'ip'})
        expected_message = "Missing user in session_config"
        self.assertRaisesRegexp(NonRecoverableError, expected_message,
                                init_cloudify_agent_configuration, ctx)

    def test_set_service_configuration_parameters_with_empty_service(self):  # NOQA

        from windows_agent_installer \
            import set_service_configuration_parameters

        # cloudify agent does not contain any
        # service configuration parameters.
        # this means all parameters should be the default ones.
        cloudify_agent = {'service': {}}
        set_service_configuration_parameters(cloudify_agent)
        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY],
            60)
        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESTART_DELAY_KEY],
            5000)

    def test_set_service_configuration_parameters_no_service(self):  # NOQA

        from windows_agent_installer \
            import set_service_configuration_parameters

        # cloudify agent does not contain the 'service' key.
        # this means all parameters should be the default ones.
        cloudify_agent = {}
        set_service_configuration_parameters(cloudify_agent)
        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY],
            60)
        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESTART_DELAY_KEY],
            5000)

    def test_set_service_configuration_parameters_with_full_service(self):  # NOQA

        from windows_agent_installer \
            import set_service_configuration_parameters

        # cloudify agent does contains all service configuration parameters.
        # this means all parameters should be the ones we specify.
        cloudify_agent = {'service': {
            constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY: 1,
            constants.SERVICE_FAILURE_RESTART_DELAY_KEY: 1
        }}
        set_service_configuration_parameters(cloudify_agent)

        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY],
            1)
        self.assertEqual(
            cloudify_agent['service']
            [constants.SERVICE_FAILURE_RESTART_DELAY_KEY],
            1)

    def test_set_service_configuration_parameters_digit_validation(self):  # NOQA

        from windows_agent_installer \
            import set_service_configuration_parameters

        cloudify_agent = {'service': {
            constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY: "Hello"
        }}
        try:
            set_service_configuration_parameters(cloudify_agent)
            self.fail('Expected NonRecoverableError since {0} is not a number'
                      .format(constants.SERVICE_FAILURE_RESET_TIMEOUT_KEY))
        except NonRecoverableError:
            pass

    def test_set_autoscale_parameters_with_empty_bootstrap_context_and_empty_cloudify_agent(self):  # NOQA

        from windows_agent_installer import set_bootstrap_context_parameters

        # cloudify agent does not contain any
        # auto scale configuration parameters.
        # bootstrap_context does not contain any
        # auto scale configuration parameters.
        # this means all parameters should be the default ones.
        cloudify_agent = {}
        ctx = MockCloudifyContext(bootstrap_context={})
        set_bootstrap_context_parameters(
            ctx.bootstrap_context,
            cloudify_agent)
        self.assertEqual(cloudify_agent[constants.MAX_WORKERS_KEY], 5)
        self.assertEqual(cloudify_agent[constants.MIN_WORKERS_KEY], 2)

    def test_set_autoscale_parameters_with_bootstrap_context_and_empty_cloudify_agent(self):  # NOQA

        from windows_agent_installer import set_autoscale_parameters

        # cloudify agent does not contain any
        # auto scale configuration parameters.
        # bootstrap_context does contain auto
        # scale configuration parameters.
        # this means all parameters should be the ones
        # specified by the bootstrap_context.
        cloudify_agent = {}
        bootstrap_context = BootstrapContext({'cloudify_agent': {
            constants.MAX_WORKERS_KEY: 10,
            constants.MIN_WORKERS_KEY: 5
        }})
        ctx = MockCloudifyContext(bootstrap_context=bootstrap_context)
        set_autoscale_parameters(
            ctx.bootstrap_context,
            cloudify_agent)
        self.assertEqual(cloudify_agent[constants.MAX_WORKERS_KEY], 10)
        self.assertEqual(cloudify_agent[constants.MIN_WORKERS_KEY], 5)

    def test_set_autoscale_parameters_with_bootstrap_context_zero_min(self):  # NOQA

        from windows_agent_installer import set_autoscale_parameters

        cloudify_agent = {}
        bootstrap_context = BootstrapContext({'cloudify_agent': {
            constants.MAX_WORKERS_KEY: 10,
            constants.MIN_WORKERS_KEY: 0
        }})
        ctx = MockCloudifyContext(bootstrap_context=bootstrap_context)
        set_autoscale_parameters(
            ctx.bootstrap_context,
            cloudify_agent)
        self.assertEqual(cloudify_agent[constants.MAX_WORKERS_KEY], 10)
        self.assertEqual(cloudify_agent[constants.MIN_WORKERS_KEY], 0)

    def test_set_autoscale_parameters_with_bootstrap_context_cloudify_agent(self):  # NOQA

        from windows_agent_installer import set_autoscale_parameters

        # cloudify agent does contain auto scale configuration parameters.
        # bootstrap_context does contain auto scale configuration parameters.
        # this means all parameters should be
        # the ones specified by the cloudify_agent.
        cloudify_agent = {
            constants.MAX_WORKERS_KEY: 10,
            constants.MIN_WORKERS_KEY: 5
        }
        bootstrap_context = BootstrapContext({'cloudify_agent': {
            constants.MAX_WORKERS_KEY: 2,
            constants.MIN_WORKERS_KEY: 3
        }})
        set_autoscale_parameters(bootstrap_context, cloudify_agent)
        self.assertEqual(cloudify_agent[constants.MAX_WORKERS_KEY], 10)
        self.assertEqual(cloudify_agent[constants.MIN_WORKERS_KEY], 5)

    def test_set_autoscale_parameters_validate_max_bigger_than_min(self):  # NOQA

        from windows_agent_installer import set_autoscale_parameters

        cloudify_agent = {
            constants.MAX_WORKERS_KEY: 10,
            constants.MIN_WORKERS_KEY: 20
        }
        try:
            set_autoscale_parameters({}, cloudify_agent)
            self.fail('Expected NonRecoverableError since {0} is bigger than'
                      .format(constants.MIN_WORKERS_KEY,
                              constants.MAX_WORKERS_KEY))
        except NonRecoverableError:
            pass

    def set_agent_configuration_parameters_with_empty_cloudify_agent(self):

        from windows_agent_installer import set_agent_configuration_parameters

        # cloudify agent does not contain any agent configuration parameters.
        # this means all parameters should be the default ones.
        cloudify_agent = {}
        set_agent_configuration_parameters(cloudify_agent)
        self.assertEqual(cloudify_agent[constants.AGENT_START_TIMEOUT_KEY], 15)
        self.assertEqual(cloudify_agent[constants.AGENT_START_INTERVAL_KEY], 1)

    def set_agent_configuration_parameters_with_full_cloudify_agent(self):

        from windows_agent_installer import set_agent_configuration_parameters

        # cloudify agent does contain agent configuration parameters.
        # this means all parameters should be the ones specified.
        cloudify_agent = {
            constants.AGENT_START_TIMEOUT_KEY: 60,
            constants.AGENT_START_INTERVAL_KEY: 5
        }
        set_agent_configuration_parameters(cloudify_agent)
        self.assertEqual(cloudify_agent[constants.AGENT_START_TIMEOUT_KEY], 60)
        self.assertEqual(cloudify_agent[constants.AGENT_START_INTERVAL_KEY], 5)
