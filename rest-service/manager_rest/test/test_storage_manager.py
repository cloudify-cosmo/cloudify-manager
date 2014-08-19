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

__author__ = 'ran'

from datetime import datetime
from manager_rest import storage_manager, models
import base_test


class StorageManagerTests(base_test.BaseServerTestCase):

    def test_store_load_delete_blueprint(self):
        now = str(datetime.now())
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          plan={'name': 'my-bp'},
                                          source='bp-source')
        storage_manager.instance().put_blueprint('blueprint-id', blueprint)
        blueprint_from_list = storage_manager.instance().blueprints_list()[0]
        blueprint_restored = \
            storage_manager.instance().get_blueprint('blueprint-id')
        bp_from_delete = storage_manager.instance().delete_blueprint(
            'blueprint-id')
        self.assertEquals(blueprint.__dict__, blueprint_from_list.__dict__)
        self.assertEquals(blueprint.__dict__, blueprint_restored.__dict__)
        # in bp returned from delete operation only 'id' is guaranteed to
        # return
        self.assertEquals(blueprint.id, bp_from_delete.id)
        self.assertEquals(0,
                          len(storage_manager.instance().blueprints_list()))

    def test_get_blueprint_deployments(self):
        now = str(datetime.now())
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          plan={'name': 'my-bp'},
                                          source='bp-source')
        storage_manager.instance().put_blueprint('blueprint-id', blueprint)

        deployment1 = models.Deployment(id='dep-1',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='blueprint-id',
                                        plan={'name': 'my-bp'},
                                        permalink=None,
                                        workflows={},
                                        inputs={})
        storage_manager.instance().put_deployment('dep-1', deployment1)

        deployment2 = models.Deployment(id='dep-2',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='blueprint-id',
                                        plan={'name': 'my-bp'},
                                        permalink=None,
                                        workflows={},
                                        inputs={})
        storage_manager.instance().put_deployment('dep-2', deployment2)

        deployment3 = models.Deployment(id='dep-3',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='another-blueprint-id',
                                        plan={'name': 'my-bp'},
                                        permalink=None,
                                        workflows={},
                                        inputs={})
        storage_manager.instance().put_deployment('dep-3', deployment3)

        blueprint_deployments = storage_manager.instance()\
            .get_blueprint_deployments(
                'blueprint-id')

        self.assertEquals(2, len(blueprint_deployments))
        self.assertEquals(deployment1.__dict__,
                          blueprint_deployments[0].__dict__)
        self.assertEquals(deployment2.__dict__,
                          blueprint_deployments[1].__dict__)

    def test_model_serialization(self):
        dep = models.Deployment(id='dep-id',
                                created_at='some-time1',
                                updated_at='some-time2',
                                blueprint_id='bp-id',
                                plan={'field': 'value'},
                                permalink=None,
                                workflows={},
                                inputs={})

        serialized_dep = dep.to_dict()
        self.assertEquals(7, len(serialized_dep))
        self.assertEquals(dep.id, serialized_dep['id'])
        self.assertEquals(dep.created_at, serialized_dep['created_at'])
        self.assertEquals(dep.updated_at, serialized_dep['updated_at'])
        self.assertEquals(dep.blueprint_id, serialized_dep['blueprint_id'])
        self.assertEquals(dep.permalink, serialized_dep['permalink'])

        deserialized_dep = models.Deployment(**serialized_dep)
        self.assertEquals(dep.id, deserialized_dep.id)
        self.assertEquals(dep.created_at, deserialized_dep.created_at)
        self.assertEquals(dep.updated_at, deserialized_dep.updated_at)
        self.assertEquals(dep.blueprint_id, deserialized_dep.blueprint_id)
        self.assertEquals(dep.permalink, deserialized_dep.permalink)

    def test_fields_query(self):
        now = str(datetime.now())
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          plan={'name': 'my-bp'},
                                          source='bp-source')
        storage_manager.instance().put_blueprint('blueprint-id', blueprint)

        blueprint_restored = \
            storage_manager.instance().get_blueprint('blueprint-id',
                                                     {'id', 'created_at'})
        self.assertEquals('blueprint-id', blueprint_restored.id)
        self.assertEquals(now, blueprint_restored.created_at)
        self.assertEquals(None, blueprint_restored.updated_at)
        self.assertEquals(None, blueprint_restored.plan)
