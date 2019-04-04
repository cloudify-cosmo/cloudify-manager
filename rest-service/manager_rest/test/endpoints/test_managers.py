#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import mock

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.storage import models

from manager_rest.manager_exceptions import NotFoundError
from cloudify_rest_client.exceptions import CloudifyClientError


_manager1 = {
    'hostname': 'manager1.test.domain',
    'private_ip': '172.17.0.1',
    'public_ip': '192.168.0.1',
    'version': '5.0.dev1',
    'edition': 'premium',
    'distribution': 'centos',
    'distro_release': 'Core',
    'fs_sync_node_id': 'P56IOI7-MZJNU2Y-IQGDREY-DM2MGTI-'
                       'MGL3BXN-PQ6W5BM-TBBZ4TJ-XZWICQ2'
}
_manager2 = {
    'hostname': 'manager2.test.domain',
    'private_ip': '172.17.0.2',
    'public_ip': '192.168.0.2',
    'version': '5.0.dev1',
    'edition': 'premium',
    'distribution': 'centos',
    'distro_release': 'Core'
}


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class ManagersTableTestCase(base_test.BaseServerTestCase):
    def setUp(self):
        super(ManagersTableTestCase, self).setUp()
        self._add_managers()

    def tearDown(self):
        self._remove_managers()
        super(ManagersTableTestCase, self).tearDown()

    def _add_managers(self, manager1=None, manager2=None):
        if manager1:
            _manager1.update(manager1)
        if manager2:
            _manager2.update(manager2)
        self.sm.put(models.Manager(**_manager1))
        self.sm.put(models.Manager(**_manager2))

    def _remove_managers(self):
        try:
            manager1 = self.sm.get(
                models.Manager,
                None,
                filters={'hostname': _manager1['hostname']}
            )
            self.sm.delete(manager1)
            manager2 = self.sm.get(
                models.Manager,
                None,
                filters={'hostname': _manager2['hostname']}
            )
            self.sm.delete(manager2)
        except NotFoundError:
            # May be already deleted by tests...
            pass

    def test_get_managers(self):
        result = self.client.manager.get_managers()
        self.assertEqual(len(result.items), 2)

    def test_get_specific_manager(self):
        result = self.client.manager.get_managers('manager2.test.domain')
        del result.items[0]['id']               # value unknown
        del result.items[0]['fs_sync_node_id']  # value is None
        self.assertEqual(_manager2, result.items[0])

    def test_get_nonexisting_manager(self):
        result = self.client.manager.get_managers('managerBLABLA.test.domain')
        self.assertEqual(len(result.items), 0)

    def test_add_manager(self):
        new_manager = {
            'hostname': 'manager3.test.domain',
            'private_ip': '172.17.0.3',
            'public_ip': '192.168.0.3',
            'version': '5.0.dev1',
            'edition': 'premium',
            'distribution': 'centos',
            'distro_release': 'Core',
            'fs_sync_node_id': 'I56IOI7-MZJNU2Y-IQGDREY-DM2MGTI-'
                               'MGL3BXN-PQ6W5BM-TBBZ4TJ-XZWICQ2'
        }
        with mock.patch('manager_rest.rest.resources_v3_1.manager.'
                        'add_manager') as add_manager:
            add_manager.return_value = None
            result = self.client.manager.add_manager(**new_manager)
            del result['id']
            self.assertEqual(result, new_manager)

    def test_add_same_manager_twice(self):
        new_manager = {
            'hostname': 'manager2.test.domain',
            'private_ip': '172.17.0.2',
            'public_ip': '192.168.0.2',
            'version': '5.0.dev1',
            'edition': 'premium',
            'distribution': 'centos',
            'distro_release': 'Core',
            'fs_sync_node_id': 'G56IOI7-MZJNU2Y-IQGDREY-DM2MGTI-'
                               'MGL3BXN-PQ6W5BM-TBBZ4TJ-XZWICQ2'
        }
        with self.assertRaises(CloudifyClientError) as error:
            self.client.manager.add_manager(**new_manager)
        self.assertEqual(error.exception.status_code, 409)

    def test_add_manager_with_same_hostname(self):
        new_manager = _manager2.copy()
        new_manager.update({
            'private_ip': '172.17.0.3',
            'public_ip': '192.168.0.3'
        })
        with self.assertRaises(CloudifyClientError) as error:
            self.client.manager.add_manager(**new_manager)
        self.assertEqual(error.exception.status_code, 409)

    def test_add_manager_with_same_private_ip(self):
        new_manager = _manager2.copy()
        new_manager.update({
            'hostname': 'manager3.test.domain',
            'public_ip': '192.168.0.3'
        })
        with self.assertRaises(CloudifyClientError) as error:
            self.client.manager.add_manager(**new_manager)
        self.assertEqual(error.exception.status_code, 409)

    def test_add_manager_with_same_public_ip(self):
        new_manager = _manager2.copy()
        new_manager.update({
            'hostname': 'manager3.test.domain',
            'private_ip': '172.17.0.3'
        })
        with self.assertRaises(CloudifyClientError) as error:
            self.client.manager.add_manager(**new_manager)
        self.assertEqual(error.exception.status_code, 409)

    def test_remove_manager(self):
        with mock.patch('manager_rest.rest.resources_v3_1.manager.'
                        'remove_manager') as remove_manager:
            remove_manager.return_value = None
            result = self.client.manager.remove_manager('manager2.test.domain')
            del result['id']               # value unknown
            del result['fs_sync_node_id']  # value is None
            self.assertEqual(result, _manager2)

    def test_remove_nonexisting_manager(self):
        new_manager = 'manager3.test.domain'
        with self.assertRaises(CloudifyClientError) as error:
            self.client.manager.remove_manager(new_manager)
        self.assertEqual(error.exception.status_code, 404)

    def test_update_manager(self):
        new_fs_sync_node_id = \
            'G56IOI7-MZJNU2Y-IQGDREY-DM2MGTI-MGL3BXN-PQ6W5BM-TBBZ4TJ-XZWICQ2'
        result = self.client.manager.update_manager(_manager2['hostname'],
                                                    new_fs_sync_node_id,
                                                    bootstrap_cluster=True)
        expected_new_manager = _manager2.copy()
        expected_new_manager['fs_sync_node_id'] = new_fs_sync_node_id
        del result['id']
        self.assertEqual(result, expected_new_manager)
