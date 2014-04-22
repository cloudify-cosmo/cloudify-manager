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

__author__ = 'idanmo'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy


class TestMultiInstanceApplication(TestCase):

    def test_deploy_multi_instance_application(self):
        dsl_path = resource("dsl/multi_instance.yaml")
        deploy(dsl_path)

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = set(result.get(timeout=10))
        self.assertEquals(2, len(machines))

        from plugins.testmockoperations.tasks import get_state as get_state
        apps_state = self.send_task(get_state).get(timeout=10)
        machines_with_apps = set([])
        for app_state in apps_state:
            host_id = app_state['capabilities'].keys()[0]
            machines_with_apps.add(host_id)
        self.assertEquals(machines, machines_with_apps)

    def test_deploy_multi_instance_many_different_hosts(self):
        dsl_path = resource('dsl/multi_instance_many_different_hosts.yaml')
        deploy(dsl_path, timeout=36000)

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = set(result.get(timeout=10))
        self.assertEquals(15, len(machines))

        self.assertEquals(5, len(filter(lambda ma: ma.startswith('host1'),
                                        machines)))
        self.assertEquals(5, len(filter(lambda ma: ma.startswith('host2'),
                                        machines)))
        self.assertEquals(5, len(filter(lambda ma: ma.startswith('host3'),
                                        machines)))
