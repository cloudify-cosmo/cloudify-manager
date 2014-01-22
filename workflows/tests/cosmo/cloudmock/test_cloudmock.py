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

import unittest
import tasks as t


class CloudMockTest(unittest.TestCase):
    """
    Tests cloud mock plugin.
    """
    def setUp(self):
        def dummy(arg, **kwargs):
            return None
        t.reachable = dummy
        t.unreachable = dummy
        t.machines = {}
        from cloudify import decorators
        decorators.get_node_state = dummy
        decorators.update_node_state = dummy

    def test_provision(self):
        machine_id = "machine1"
        t.provision(__cloudify_id=machine_id)
        machines = t.get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(t.NOT_RUNNING, machines[machine_id])

    def test_start(self):
        machine_id = "machine1"
        t.provision(__cloudify_id=machine_id)
        t.start(__cloudify_id=machine_id)
        machines = t.get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(t.RUNNING, machines[machine_id])

    def test_stop(self):
        machine_id = "machine1"
        t.provision(__cloudify_id=machine_id)
        t.start(__cloudify_id=machine_id)
        t.stop(__cloudify_id=machine_id)
        machines = t.get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(t.NOT_RUNNING, machines[machine_id])

    def test_terminate(self):
        machine_id = "machine1"
        t.provision(__cloudify_id=machine_id)
        t.terminate(__cloudify_id=machine_id)
        machines = t.get_machines()
        self.assertEqual(0, len(machines))
