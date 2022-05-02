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

from manager_rest import manager_exceptions
from manager_rest.test import base_test
from manager_rest.storage import models

from cloudify_rest_client.exceptions import CloudifyClientError


class ManagerConfigTestCase(base_test.BaseServerTestCase):
    def _put_config(self, **kwargs):
        config = {
            'name': 'x',
            'value': 5,
            '_updater_id': self.user.id,
            'scope': 'rest'
        }
        config.update(kwargs)
        instance = self.sm.put(models.Config(**config))
        self.addCleanup(self.sm.delete, instance)

    def test_get_config(self):
        self._put_config()
        result = self.client.manager.get_config()
        expected = {
            'name': 'x',
            'value': 5,
            'updater_name': self.user.username,
            'is_editable': True,
            'scope': 'rest'
        }
        actual = [item for item in result if item['name'] == 'x'][0]
        actual = {k: actual[k] for k in expected}
        self.assertEqual(actual, expected)

    def test_get_by_name(self):
        self._put_config()
        result = self.client.manager.get_config(name='x')
        self.assertEqual(result.name, 'x')
        self.assertEqual(result.value, 5)

    def test_get_by_scope(self):
        self._put_config(scope='rest')
        self._put_config(name='y', value=6, scope='new-scope')
        result = self.client.manager.get_config(scope='new-scope')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'y')
        self.assertEqual(result[0].value, 6)

    def test_get_by_name_missing(self):
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.manager.get_config(name='x')
        self.assertEqual(cm.exception.status_code, 404)

    def test_put_config(self):
        self._put_config()
        result = self.client.manager.put_config('x', 6)
        expected = {
            'name': 'x',
            'value': 6,
            'updater_name': self.user.username,
            'is_editable': True
        }
        actual = {k: result[k] for k in expected}
        self.assertEqual(actual, expected)

    def test_put_missing(self):
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.manager.put_config('x', 6)
        self.assertEqual(cm.exception.status_code, 404)

    def test_put_config_schema(self):
        self._put_config(schema={'type': 'number', 'maximum': 10})
        self.client.manager.put_config('x', 6)

    def test_put_config_schema_invalid(self):
        self._put_config(schema={'type': 'number', 'maximum': 5})
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.manager.put_config('x', 6)
        self.assertEqual(cm.exception.status_code, 409)

    def test_put_config_noneditable(self):
        self._put_config(is_editable=False)
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.manager.put_config('x', 6)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn('is not editable', cm.exception.args[0])

    def test_put_config_noneditable_force(self):
        self._put_config(is_editable=False)
        self.client.manager.put_config('x', 6, force=True)

    def test_get_ambiguous_name(self):
        self._put_config(name='x', scope='rest', value=5)
        self._put_config(name='x', scope='agent', value=6)
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.manager.get_config(name='x')
        self.assertEqual(
            cm.exception.error_code,
            manager_exceptions.AmbiguousName.error_code)
        self.assertIn('Expected 1 value, but found 2', str(cm.exception))

        result = self.client.manager.get_config(name='rest.x')
        self.assertEqual(result.value, 5)
        result = self.client.manager.get_config(name='agent.x')
        self.assertEqual(result.value, 6)

    def test_update_ambiguous_name(self):
        self._put_config(name='x', scope='rest', value=5)
        self._put_config(name='x', scope='agent', value=6)
        with self.assertRaises(CloudifyClientError):
            self.client.manager.put_config('x', 7)
        self.client.manager.put_config('agent.x', 7)

        self.assertEqual(
            self.client.manager.get_config(name='rest.x').value, 5)
        self.assertEqual(
            self.client.manager.get_config(name='agent.x').value, 7)
