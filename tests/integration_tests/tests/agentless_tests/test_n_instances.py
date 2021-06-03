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

import time
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class TestMultiInstanceApplication(AgentlessTestCase):

    @pytest.mark.group_deployments
    def test_deploy_multi_instance_application(self):
        dsl_path = resource("dsl/multi_instance.yaml")
        deployment, _ = self.deploy_application(dsl_path)

        machines = set()
        for host_ni in self.client.node_instances.list(node_id='host'):
            machines.update(
                host_id for host_id, state
                in host_ni.runtime_properties.get('machines', {}).items()
                if state == 'running'
            )
        machines_with_apps = set()
        for app_ni in self.client.node_instances.list(node_id='app_module'):
            machines_with_apps.update(
                app_ni.runtime_properties.get('capabilities', {})
            )
        assert machines == machines_with_apps

    @pytest.mark.group_deployments
    def test_deploy_multi_instance_many_different_hosts(self):
        dsl_path = resource('dsl/multi_instance_many_different_hosts.yaml')
        deployment, _ = self.deploy_application(dsl_path, timeout_seconds=180)
        machines = set()
        for host_ni in self.client.node_instances.list():
            machines.update(
                host_id for host_id, state
                in host_ni.runtime_properties.get('machines', {}).items()
                if state == 'running'
            )
        self.assertEqual(15, len(machines))
        self.assertEqual(
            5, len([ma for ma in machines if ma.startswith('host1')]))
        self.assertEqual(
            5, len([ma for ma in machines if ma.startswith('host2')]))
        self.assertEqual(
            5, len([ma for ma in machines if ma.startswith('host3')]))

    @pytest.mark.group_deployments_large_scale
    def test_deploy_multi_large_scale(self):
        dsl_path = resource('dsl/multi_instance_large_scale.yaml')
        start = time.time()
        deployment, _ = self.deploy_application(dsl_path, timeout_seconds=3600)
        self.logger.info('All done! execution took %s seconds',
                         time.time() - start)
