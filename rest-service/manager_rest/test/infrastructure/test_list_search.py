#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from manager_rest.test.infrastructure.base_list_test import BaseListTest


NUM_OF_RESOURCES = 2


class ResourceListSearchTestCase(BaseListTest):

    def setUp(self):
        super(ResourceListSearchTestCase, self).setUp()

        self._put_n_plugins(NUM_OF_RESOURCES)
        self._put_n_deployments('test', NUM_OF_RESOURCES)
        self._put_n_snapshots(NUM_OF_RESOURCES, 'test', '_snapshot')
        self._put_n_secrets(NUM_OF_RESOURCES)

        self.resources = {
            'blueprint': self.client.blueprints,
            'deployment': self.client.deployments,
            'secret': self.client.secrets,
            'snapshot': self.client.snapshots
        }

    def test_search_resource(self):
        # test general resources
        for resource in self.resources:
            list_ = self.resources[resource].list(_search='')
            list_est = self.resources[resource].list(_search='est')
            list_est0 = self.resources[resource].list(_search='est0')
            list_est_bla = self.resources[resource].list(_search='est-bla')
            # validate lists sizes
            self.assertEqual(NUM_OF_RESOURCES, len(list_))
            self.assertEqual(NUM_OF_RESOURCES, len(list_est))
            self.assertEqual(1, len(list_est0))
            self.assertEqual(0, len(list_est_bla))
            # validate specific resource (r), by key/id
            r = list_est0[0].key if resource == 'secret' else list_est0[0].id
            self.assertEqual('test0_{0}'.format(resource), r)

        # test nodes and node_instances
        for resource in [self.client.nodes, self.client.node_instances]:
            list_ = resource.list(_search='')
            list_v = resource.list(_search='v')
            list_server = resource.list(_search='server')
            list_server_bla = resource.list(_search='server-bla')
            # validate lists sizes
            self.assertEqual(2 * NUM_OF_RESOURCES, len(list_))
            self.assertEqual(2 * NUM_OF_RESOURCES, len(list_v))
            self.assertEqual(NUM_OF_RESOURCES, len(list_server))
            self.assertEqual(0, len(list_server_bla))
            # validate specific resource by id
            for i in range(NUM_OF_RESOURCES):
                self.assertIn('http_web_server', list_server[i].id)

        # test plugins - simpler test because they have the same package name
        self.assertEqual(NUM_OF_RESOURCES,
                         len(self.client.plugins.list(_search='')))
        self.assertEqual(NUM_OF_RESOURCES,
                         len(self.client.plugins.list(_search='script')))
        self.assertEqual(0, len(self.client.plugins.list(_search='bla')))
