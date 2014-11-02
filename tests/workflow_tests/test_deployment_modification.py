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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow


class TestDeploymentModification(TestCase):

    def test_deployment_modification_add_compute(self):
        nodes = {'compute': {'instances': 2}}
        return self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 1,
                              'modification': 1,
                              'relationships': 0},
            expected_db={'existence': 1,
                         'modification': 1,
                         'relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1},
            expected_total=5)

    def test_deployment_modification_add_db(self):
        nodes = {'db': {'instances': 2}}
        self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 1,
                              'modification': 0,
                              'relationships': 0},
            expected_db={'existence': 1,
                         'modification': 1,
                         'relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1},
            expected_total=4)

    def test_deployment_modification_add_webserver(self):
        nodes = {'webserver': {'instances': 2}}
        self._test_deployment_modification(
            modification_type='added',
            modified_nodes=nodes,
            expected_compute={'existence': 0,
                              'modification': 0,
                              'relationships': 0},
            expected_db={'existence': 1,
                         'modification': 0,
                         'relationships': 0},
            expected_webserver={'existence': 1,
                                'modification': 1,
                                'relationships': 1},
            expected_total=4)

    def test_deployment_modification_remove_compute(self):
        deployment_id = self.test_deployment_modification_add_compute()
        self.clear_plugin_data('testmockoperations')
        nodes = {'compute': {'instances': 1}}
        self._test_deployment_modification(
            deployment_id=deployment_id,
            modification_type='removed',
            modified_nodes=nodes,
            expected_compute={'existence': 1,
                              'modification': 1,
                              'relationships': 0},
            expected_db={'existence': 1,
                         'modification': 1,
                         'relationships': 1},
            expected_webserver={'existence': 1,
                                'modification': 0,
                                'relationships': 1},
            expected_total=3)

    def _test_deployment_modification(self,
                                      modified_nodes,
                                      expected_compute,
                                      expected_db,
                                      expected_webserver,
                                      modification_type,
                                      expected_total,
                                      deployment_id=None):
        if not deployment_id:
            dsl_path = resource("dsl/deployment_modification.yaml")
            deployment, _ = deploy(dsl_path)
            deployment_id = deployment.id
        execute_workflow('deployment_modification', deployment_id,
                         parameters={'nodes': modified_nodes})
        state = self.get_plugin_data('testmockoperations',
                                     deployment_id)['state']

        compute_instances = self._get_instances(state, 'compute')
        db_instances = self._get_instances(state, 'db')
        webserver_instances = self._get_instances(state, 'webserver')

        # existence
        self.assertEqual(expected_compute['existence'], len(compute_instances))
        self.assertEqual(expected_db['existence'], len(db_instances))
        self.assertEqual(expected_webserver['existence'],
                         len(webserver_instances))

        # modification
        self.assertEqual(expected_compute['modification'],
                         len([i for i in compute_instances
                             if i['modification'] == modification_type]))
        self.assertEqual(expected_db['modification'],
                         len([i for i in db_instances
                             if i['modification'] == modification_type]))
        self.assertEqual(expected_webserver['modification'],
                         len([i for i in webserver_instances
                             if i['modification'] == modification_type]))

        # relationships
        if compute_instances:
            self.assertEqual(expected_compute['relationships'],
                             len(compute_instances[0]['relationships']))
        if db_instances:
            self.assertEqual(expected_db['relationships'],
                             len(db_instances[0]['relationships']))
        if webserver_instances:
            self.assertEqual(expected_webserver['relationships'],
                             len(webserver_instances[0]['relationships']))

        def assertion():
            self.assertEqual(
                expected_total,
                len(self.client.node_instances.list(deployment_id)))
        self.do_assertions(assertion)

        return deployment_id

    def _get_instances(self, state, node_id):
        return [i for i in state.values() if i['node_id'] == node_id]