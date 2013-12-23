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

__author__ = 'eitany'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import undeploy_application as undeploy


class TestUninstallApplication(TestCase):

    def test_uninstall_application_single_node_no_host(self):
        dsl_path = resource("dsl/single_node_no_host.yaml")
        print('starting deploy process')
        deployment_id = deploy(dsl_path).id
        print('deploy completed')
        print('starting undeploy process')
        undeploy(deployment_id)
        print('undeploy completed')

        from cosmo.testmockoperations.tasks import is_unreachable_called
        result = is_unreachable_called.apply_async()
        self.assertTrue(result.get(timeout=10))

    def test_uninstall_application_single_host_node(self):
        dsl_path = resource("dsl/basic.yaml")
        print('starting deploy process')
        deployment_id = deploy(dsl_path)
        print('deploy completed')
        print('starting undeploy process')
        undeploy(deployment_id)
        print('undeploy completed')

        from cosmo.cloudmock.tasks import get_machines
        result = get_machines.apply_async()
        machines = result.get(timeout=10)

        self.assertEquals(0, len(machines))

    def test_uninstall_not_calling_unreachable_nodes(self):
        dsl_path = resource("dsl/single_node_no_host.yaml")
        print('starting deploy process')
        deployment_id = deploy(dsl_path)
        print('deploy completed')
        print('making node unreachable from test')
        #make node unreachable
        from cosmo.testmockoperations.tasks import get_state as testmock_get_state
        from cosmo.events import set_unreachable
        states = testmock_get_state.apply_async().get(timeout=10)
        node_id = states[0]['id']
        set_unreachable(node_id)
        import time
        time.sleep(10)
        print('starting undeploy process')
        undeploy(deployment_id)
        print('undeploy completed')
        #Checking that uninstall wasn't called on unreachable node
        from cosmo.testmockoperations.tasks import is_unreachable_called
        result = is_unreachable_called.apply_async()
        self.assertFalse(result.get(timeout=10))

    def test_uninstall_not_calling_node_within_host(self):
        dsl_path = resource("dsl/two_nodes_one_host.yaml")
        print('starting deploy process')
        deployment_id = deploy(dsl_path)
        print('deploy completed')
        print('starting undeploy process')
        undeploy(deployment_id)
        print('undeploy completed')
        #Checking that uninstall wasn't called on the contained node
        from cosmo.testmockoperations.tasks import is_unreachable_called
        result = is_unreachable_called.apply_async()
        self.assertFalse(result.get(timeout=10))
