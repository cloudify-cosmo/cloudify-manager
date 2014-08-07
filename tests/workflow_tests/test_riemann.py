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


import bernhard
from os import path

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import undeploy_application as undeploy


class RiemannTest(TestCase):

    def test_riemann(self):
        dsl_path = resource("dsl/riemann_basic.yaml")

        # create deployment is the important part here
        # we call the riemann.create task
        deployment, _ = deploy(dsl_path)

        # fetch port
        with open(path.join(self.riemann_workdir, deployment.id, 'port')) as f:
            port = int(f.read())

        # new riemann core should be running on port
        self._send_riemann_event(port)

        # undeploy so we can safely delete
        undeploy(deployment.id)

        # wait for ES to actually reflect the fact that the uninstall
        # execution terminated
        def assertion():
            executions = self.client.executions.list(deployment.id)
            terminated = all([e.status == 'terminated' for e in executions])
            self.assertTrue(terminated)
            node_instances = self.client.node_instances.list(deployment.id)
            deleted = all([ni.state == 'deleted' for ni in node_instances])
            self.assertTrue(deleted)
        self.do_assertions(assertion)

        # we call the riemann.delete task
        self.client.deployments.delete(deployment.id)

        # riemann core should no longer be running on port
        def assertion():
            self.assertRaises(bernhard.TransportError,
                              self._send_riemann_event,
                              port)
        self.do_assertions(assertion)

    def _send_riemann_event(self, port):
        client = bernhard.Client(port=port)
        client.send({
            'service': 'testing',
            'state': 'notsogood'
        })
