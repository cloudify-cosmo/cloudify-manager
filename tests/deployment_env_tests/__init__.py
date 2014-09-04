########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'ran'


from testenv import TestEnvironment
from testenv import TestEnvironmentScope
from testenv import TestCase
from mock_plugins.worker_installer.tasks import (
    setup_plugin as setup_worker_installer,
    teardown_plugin as teardown_worker_installer)
from mock_plugins.plugin_installer.tasks import (
    setup_plugin as setup_plugin_installer,
    teardown_plugin as teardown_plugin_installer)


def setUp():
    TestEnvironment.create(use_mock_deployment_environment_workflows=False)


def tearDown():
    TestEnvironment.destroy()


class DeploymentEnvTestCase(TestCase):
    """
    A test case for cosmo workers tests.
    """

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS, False)

    def setUp(self):
        super(DeploymentEnvTestCase, self).setUp()
        setup_plugin_installer()
        setup_worker_installer()

    def tearDown(self):
        teardown_worker_installer()
        teardown_plugin_installer()
        super(DeploymentEnvTestCase, self).tearDown()
