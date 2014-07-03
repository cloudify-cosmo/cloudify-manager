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
from cloudify.context import BootstrapContext
from cloudify.mocks import MockCloudifyContext

__author__ = 'elip'


import unittest

from windows_agent_installer import *


class InitTest(unittest.TestCase):

    def test_set_service_configuration_parameters_with_empty_service(self):

        # cloudify agent does not contain any service configuration parameters.
        # this means all parameters should be the default ones.
        cloudify_agent = {}
        set_service_configuration_parameters(cloudify_agent)
        self.assertEqual(cloudify_agent['service'][SERVICE_FAILURE_RESET_TIMEOUT_KEY], 60)
        self.assertEqual(cloudify_agent['service'][SERVICE_STATUS_TRANSITION_SLEEP_INTERVAL_KEY], 5)
        self.assertEqual(cloudify_agent['service'][SERVICE_SUCCESSFUL_CONSECUTVE_STATUS_QUERIES_COUNT_KEY], 3)
        self.assertEqual(cloudify_agent['service'][SERVICE_STOP_TIMEOUT_KEY], 30)
        self.assertEqual(cloudify_agent['service'][SERVICE_START_TIMEOUT_KEY], 30)
        self.assertEqual(cloudify_agent['service'][SERVICE_FAILURE_RESTART_DELAY_KEY], 5000)

    def test_set_service_configuration_parameters_with_full_service(self):

        cloudify_agent = {'service': {
            SERVICE_FAILURE_RESET_TIMEOUT_KEY: 1,
            SERVICE_STATUS_TRANSITION_SLEEP_INTERVAL_KEY: 1,
            SERVICE_SUCCESSFUL_CONSECUTVE_STATUS_QUERIES_COUNT_KEY: 1,
            SERVICE_STOP_TIMEOUT_KEY: 1,
            SERVICE_START_TIMEOUT_KEY: 1,
            SERVICE_FAILURE_RESTART_DELAY_KEY: 1
        }}
        set_service_configuration_parameters(cloudify_agent)

        self.assertEqual(cloudify_agent['service'][SERVICE_FAILURE_RESET_TIMEOUT_KEY], 1)
        self.assertEqual(cloudify_agent['service'][SERVICE_STATUS_TRANSITION_SLEEP_INTERVAL_KEY], 1)
        self.assertEqual(cloudify_agent['service'][SERVICE_SUCCESSFUL_CONSECUTVE_STATUS_QUERIES_COUNT_KEY], 1)
        self.assertEqual(cloudify_agent['service'][SERVICE_STOP_TIMEOUT_KEY], 1)
        self.assertEqual(cloudify_agent['service'][SERVICE_START_TIMEOUT_KEY], 1)
        self.assertEqual(cloudify_agent['service'][SERVICE_FAILURE_RESTART_DELAY_KEY], 1)

    def test_set_service_configuration_parameters_digit_validation(self):

        cloudify_agent = {'service':{
            SERVICE_FAILURE_RESET_TIMEOUT_KEY: "Hello"
        }}
        try:
            set_service_configuration_parameters(cloudify_agent)
            self.fail('Expected NonRecoverableError since {0} is not a number'.format(SERVICE_FAILURE_RESET_TIMEOUT_KEY))
        except NonRecoverableError:
            pass

    def test_set_autoscale_parameters_with_empty_bootstrap_context_and_no_parameters(self):

        # Default values should be populated.

        cloudify_agent = {}
        ctx = MockCloudifyContext(bootstrap_context={})
        set_bootstrap_context_parameters(ctx.bootstrap_context, cloudify_agent)
        self.assertEqual(cloudify_agent[MAX_WORKERS_KEY], 5)
        self.assertEqual(cloudify_agent[MIN_WORKERS_KEY], 2)

    def test_set_autoscale_parameters_with_bootstrap_context_and_no_parameters(self):

        # Bootstrap context values should be populated.

        cloudify_agent = {}
        bootstrap_context = BootstrapContext({'cloudify_agent': {
            MAX_WORKERS_KEY: 10,
            MIN_WORKERS_KEY: 5
        }})
        ctx = MockCloudifyContext(bootstrap_context=bootstrap_context)
        set_autoscale_parameters(ctx.bootstrap_context, cloudify_agent)
        self.assertEqual(cloudify_agent[MAX_WORKERS_KEY], 10)
        self.assertEqual(cloudify_agent[MIN_WORKERS_KEY], 5)

    def test_set_autoscale_parameters_with_bootstrap_context_and_parameters(self):

        # Cloudify agent configuration parameters should be populated.
        cloudify_agent = {
            MAX_WORKERS_KEY: 10,
            MIN_WORKERS_KEY: 5
        }
        set_autoscale_parameters({}, cloudify_agent)
        self.assertEqual(cloudify_agent[MAX_WORKERS_KEY], 10)
        self.assertEqual(cloudify_agent[MIN_WORKERS_KEY], 5)

    def test_set_autoscale_parameters_validate_max_bigger_than_min(self):

        # Cloudify agent configuration parameters should be populated.
        cloudify_agent = {
            MAX_WORKERS_KEY: 10,
            MIN_WORKERS_KEY: 20
        }
        try:
            set_autoscale_parameters({}, cloudify_agent)
            self.fail('Expected NonRecoverableError since {0} is bigger than'
                      .format(MIN_WORKERS_KEY, MAX_WORKERS_KEY))
        except NonRecoverableError:
            pass
