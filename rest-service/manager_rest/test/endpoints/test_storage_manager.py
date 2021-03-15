#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from datetime import datetime
from unittest import TestCase
import mock

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions, utils
from manager_rest.test import base_test
from manager_rest.storage import models, db
from manager_rest.storage.storage_manager import SQLStorageManager
from manager_rest.test.attribute import attr


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class StorageManagerTests(base_test.BaseServerTestCase):

    def test_store_load_delete_blueprint(self):
        now = utils.get_formatted_timestamp()
        blueprint = models.Blueprint(id='blueprint-id',
                                     created_at=now,
                                     updated_at=now,
                                     description=None,
                                     plan={'name': 'my-bp'},
                                     main_file_name='aaa')
        self.sm.put(blueprint)
        blueprint_from_list = self.sm.list(models.Blueprint)[0]
        blueprint_restored = self.sm.get(models.Blueprint, 'blueprint-id')
        bp_from_delete = self.sm.delete(blueprint_restored)
        self.assertEqual(blueprint.to_dict(), blueprint_from_list.to_dict())
        self.assertEqual(blueprint.to_dict(), blueprint_restored.to_dict())
        # in bp returned from delete operation only 'id' is guaranteed to
        # return
        self.assertEqual(blueprint.id, bp_from_delete.id)
        blueprints_list = self.sm.list(models.Blueprint)
        self.assertEqual(0, len(blueprints_list))

    def test_get_blueprint_deployments(self):
        now = utils.get_formatted_timestamp()

        blueprint = models.Blueprint(id='blueprint-id',
                                     created_at=now,
                                     updated_at=now,
                                     description=None,
                                     plan={'name': 'my-bp'},
                                     main_file_name='aaa')
        another_blueprint = models.Blueprint(id='another-blueprint-id',
                                             created_at=now,
                                             updated_at=now,
                                             description=None,
                                             plan={'name': 'my-bp'},
                                             main_file_name='aaa')
        self.sm.put(blueprint)
        self.sm.put(another_blueprint)

        deployment1 = models.Deployment(id='dep-1',
                                        created_at=now,
                                        updated_at=now,
                                        permalink=None,
                                        description=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        deployment1.blueprint = blueprint
        self.sm.put(deployment1)

        deployment2 = models.Deployment(id='dep-2',
                                        created_at=now,
                                        updated_at=now,
                                        permalink=None,
                                        description=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        deployment2.blueprint = blueprint
        self.sm.put(deployment2)

        deployment3 = models.Deployment(id='dep-3',
                                        created_at=now,
                                        updated_at=now,
                                        description=None,
                                        permalink=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        deployment3.blueprint = another_blueprint
        self.sm.put(deployment3)

        filters_bp = {'blueprint_id': 'blueprint-id'}
        blueprint_deployments = \
            self.sm.list(models.Deployment, filters=filters_bp)

        self.assertEqual(2, len(blueprint_deployments))
        if blueprint_deployments[0].id == deployment1.id:
            self.assertEqual(deployment1.to_dict(),
                             blueprint_deployments[0].to_dict())
            self.assertEqual(deployment2.to_dict(),
                             blueprint_deployments[1].to_dict())
        else:
            self.assertEqual(deployment2.to_dict(),
                             blueprint_deployments[0].to_dict())
            self.assertEqual(deployment1.to_dict(),
                             blueprint_deployments[1].to_dict())

    def test_model_serialization(self):
        now = utils.get_formatted_timestamp()
        blueprint = models.Blueprint(id='blueprint-id',
                                     created_at=now,
                                     updated_at=now,
                                     description=None,
                                     plan={'name': 'my-bp'},
                                     main_file_name='aaa')
        self.sm.put(blueprint)

        now2 = utils.get_formatted_timestamp()
        dep = models.Deployment(id='dep-id',
                                created_at=now2,
                                updated_at=now2,
                                permalink=None,
                                description=None,
                                workflows={},
                                inputs={},
                                policy_types={},
                                policy_triggers={},
                                groups={},
                                scaling_groups={},
                                outputs={},
                                capabilities={})

        dep.blueprint = blueprint
        self.sm.put(dep)

        serialized_dep = dep.to_response()
        self.assertEqual(27, len(serialized_dep))
        self.assertEqual(dep.id, serialized_dep['id'])
        self.assertEqual(dep.created_at, serialized_dep['created_at'])
        self.assertEqual(dep.updated_at, serialized_dep['updated_at'])
        self.assertEqual(dep.blueprint_id, serialized_dep['blueprint_id'])
        self.assertEqual(dep.permalink, serialized_dep['permalink'])
        self.assertEqual(dep.tenant.name, serialized_dep['tenant_name'])
        self.assertEqual(dep.description, None)

        # `blueprint_id` isn't a regular column, but a relationship
        serialized_dep.pop('blueprint_id')
        serialized_dep.pop('tenant_name')
        serialized_dep.pop('created_by')
        serialized_dep.pop('site_name')
        serialized_dep.pop('latest_execution_status')

        # Deprecated columns, for backwards compatibility -
        # was added to the response
        serialized_dep.pop('resource_availability')
        serialized_dep.pop('private_resource')

        deserialized_dep = models.Deployment(**serialized_dep)
        self.assertEqual(dep.id, deserialized_dep.id)
        self.assertEqual(dep.created_at, deserialized_dep.created_at)
        self.assertEqual(dep.updated_at, deserialized_dep.updated_at)
        self.assertEqual(dep.permalink, deserialized_dep.permalink)
        self.assertEqual(dep.description, deserialized_dep.description)

    def test_fields_query(self):
        now = utils.get_formatted_timestamp()
        blueprint = models.Blueprint(id='blueprint-id',
                                     created_at=now,
                                     updated_at=now,
                                     description=None,
                                     plan={'name': 'my-bp'},
                                     main_file_name='aaa')
        self.sm.put(blueprint)

        blueprint_restored = self.sm.get(
            models.Blueprint,
            'blueprint-id',
            include=['id', 'created_at']
        )
        self.assertEqual('blueprint-id', blueprint_restored.id)
        self.assertEqual(now, blueprint_restored.created_at)
        self.assertFalse(hasattr(blueprint_restored, 'updated_at'))
        self.assertFalse(hasattr(blueprint_restored, 'plan'))
        self.assertFalse(hasattr(blueprint_restored, 'main_file_name'))

    @mock.patch('manager_rest.storage.storage_manager.'
                'config.instance.default_page_size',
                10)
    def test_all_results_query(self):
        now = utils.get_formatted_timestamp()
        for i in range(20):
            secret = models.Secret(id='secret_{}'.format(i),
                                   value='value',
                                   created_at=now,
                                   updated_at=now,
                                   visibility=VisibilityState.TENANT)
            self.sm.put(secret)

        secret_list = self.sm.list(
            models.Secret,
            include=['id'],
        )
        self.assertEqual(10, len(secret_list))

        secret_list = self.sm.list(
            models.Secret,
            include=['id'],
            get_all_results=True
        )
        self.assertEqual(20, len(secret_list))


class TestTransactions(base_test.BaseServerTestCase):
    def _make_secret(self, id, value):
        # these tests are using secrets, but they could just as well
        # use any other model, we just need to create _something_ in the db
        now = datetime.now()
        return models.Secret(
            id=id,
            value=value,
            created_at=now,
            updated_at=now,
            visibility=VisibilityState.TENANT
        )

    def test_commits(self):
        """Items created in the transaction are stored"""
        with self.sm.transaction():
            self.sm.put(self._make_secret('tx_secret', 'value'))

        # rollback the current transaction - if the secret was committed
        # indeed, then this will be a no-op
        db.session.rollback()

        secret = self.sm.get(models.Secret, 'tx_secret')
        assert secret.value == 'value'

    def test_before_commits(self):
        """Items created before the transaction are stored as well"""
        self.sm.put(self._make_secret('tx_secret1', 'value1'))
        with self.sm.transaction():
            self.sm.put(self._make_secret('tx_secret2', 'value2'))
        assert self.sm.get(models.Secret, 'tx_secret1').value == 'value1'
        assert self.sm.get(models.Secret, 'tx_secret2').value == 'value2'

    def test_exception_rollback(self):
        """If the transaction throws, items created in it are not stored"""
        with self.assertRaisesRegex(RuntimeError, 'test error'):
            with self.sm.transaction():
                self.sm.put(self._make_secret('tx_secret', 'value'))
                raise RuntimeError('test error')
        with self.assertRaises(manager_exceptions.NotFoundError):
            self.sm.get(models.Secret, 'tx_secret')

    def test_exception_before_commits(self):
        """items created before a transaction that throws, are still stored"""
        with self.assertRaisesRegex(RuntimeError, 'test error'):
            self.sm.put(self._make_secret('tx_secret1', 'value1'))
            with self.sm.transaction():
                self.sm.put(self._make_secret('tx_secret2', 'value2'))
                raise RuntimeError('test error')

        assert self.sm.get(models.Secret, 'tx_secret1').value == 'value1'
        with self.assertRaises(manager_exceptions.NotFoundError):
            self.sm.get(models.Secret, 'tx_secret2')

    def test_subtransactions(self):
        with self.assertRaisesRegex(RuntimeError, 'disallowed'):
            with self.sm.transaction():
                with self.sm.transaction():
                    pass


class TestGetErrorFormat(TestCase):
    """Tests for the 404 not found error message formatting"""
    def setUp(self):
        self.sm = SQLStorageManager()

    def test_get_by_id(self):
        # Requested `Node` with ID `0` was not found
        message = self.sm._format_not_found_message(models.Node, {'id': 0})
        assert 'not found' in message
        assert 'with ID `0`' in message
        assert 'filters' not in message

    def test_get_by_id_and_filters(self):
        # Requested `Node` with ID `0` was not found (filters: {'x': 'y'})
        message = self.sm._format_not_found_message(
            models.Node, {'id': 0, 'x': 'y'})
        assert 'not found' in message
        assert 'with ID `0`' in message
        assert 'filters' in message

    def test_get_by_filters(self):
        # Requested `Node` was not found (filters: {'x': 'y'})"
        message = self.sm._format_not_found_message(
            models.Node, {'x': 'y'})
        assert 'ID' not in message
        assert 'filters' in message
        assert "'x': 'y'" in message
