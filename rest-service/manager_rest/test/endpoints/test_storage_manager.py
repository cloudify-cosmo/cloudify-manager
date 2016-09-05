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

from nose.plugins.attrib import attr

from manager_rest import models, utils
from manager_rest.storage import storage_manager
from manager_rest.test import base_test


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class StorageManagerTests(base_test.BaseServerTestCase):

    def test_store_load_delete_blueprint(self):
        now = utils.get_formatted_timestamp()
        sm = storage_manager._get_instance()
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          description=None,
                                          plan={'name': 'my-bp'},
                                          source='bp-source',
                                          main_file_name='aaa')
        sm.put_blueprint('blueprint-id', blueprint)
        blueprint_from_list = sm.list_blueprints().items[0]
        blueprint_restored = sm.get_blueprint('blueprint-id')
        bp_from_delete = sm.delete_blueprint('blueprint-id')
        self.assertEquals(blueprint.to_dict(), blueprint_from_list.to_dict())
        self.assertEquals(blueprint.to_dict(), blueprint_restored.to_dict())
        # in bp returned from delete operation only 'id' is guaranteed to
        # return
        self.assertEquals(blueprint.id, bp_from_delete.id)
        blueprints_list = sm.list_blueprints().items
        self.assertEquals(0, len(blueprints_list))

    def test_get_blueprint_deployments(self):
        now = utils.get_formatted_timestamp()
        sm = storage_manager._get_instance()
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          description=None,
                                          plan={'name': 'my-bp'},
                                          source='bp-source',
                                          main_file_name='aaa')
        sm.put_blueprint('blueprint-id', blueprint)

        deployment1 = models.Deployment(id='dep-1',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='blueprint-id',
                                        plan={'name': 'my-bp'},
                                        permalink=None,
                                        description=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        sm.put_deployment('dep-1', deployment1)

        deployment2 = models.Deployment(id='dep-2',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='blueprint-id',
                                        plan={'name': 'my-bp'},
                                        permalink=None,
                                        description=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        sm.put_deployment('dep-2', deployment2)

        deployment3 = models.Deployment(id='dep-3',
                                        created_at=now,
                                        updated_at=now,
                                        blueprint_id='another-blueprint-id',
                                        plan={'name': 'my-bp'},
                                        description=None,
                                        permalink=None,
                                        workflows={},
                                        inputs={},
                                        policy_types={},
                                        policy_triggers={},
                                        groups={},
                                        scaling_groups={},
                                        outputs={})
        sm.put_deployment('dep-3', deployment3)

        blueprint_deployments = \
            sm.list_blueprint_deployments('blueprint-id').items

        self.assertEquals(2, len(blueprint_deployments))
        if blueprint_deployments[0].id != deployment1.id:
            blueprint_deployments[0], blueprint_deployments[1] =\
                blueprint_deployments[1], blueprint_deployments[0]
        self.assertEquals(deployment1.to_dict(),
                          blueprint_deployments[0].to_dict())
        self.assertEquals(deployment2.to_dict(),
                          blueprint_deployments[1].to_dict())

    def test_model_serialization(self):
        dep = models.Deployment(id='dep-id',
                                created_at='some-time1',
                                updated_at='some-time2',
                                blueprint_id='bp-id',
                                plan={'field': 'value'},
                                permalink=None,
                                description=None,
                                workflows={},
                                inputs={},
                                policy_types={},
                                policy_triggers={},
                                groups={},
                                scaling_groups={},
                                outputs={})

        serialized_dep = dep.to_dict()
        self.assertEquals(13, len(serialized_dep))
        self.assertEquals(dep.id, serialized_dep['id'])
        self.assertEquals(dep.created_at, serialized_dep['created_at'])
        self.assertEquals(dep.updated_at, serialized_dep['updated_at'])
        self.assertEquals(dep.blueprint_id, serialized_dep['blueprint_id'])
        self.assertEquals(dep.permalink, serialized_dep['permalink'])
        self.assertEquals(dep.description, None)

        deserialized_dep = models.Deployment(**serialized_dep)
        self.assertEquals(dep.id, deserialized_dep.id)
        self.assertEquals(dep.created_at, deserialized_dep.created_at)
        self.assertEquals(dep.updated_at, deserialized_dep.updated_at)
        self.assertEquals(dep.blueprint_id, deserialized_dep.blueprint_id)
        self.assertEquals(dep.permalink, deserialized_dep.permalink)
        self.assertEquals(dep.description, deserialized_dep.description)

    def test_fields_query(self):
        now = utils.get_formatted_timestamp()
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          description=None,
                                          plan={'name': 'my-bp'},
                                          source='bp-source',
                                          main_file_name='aaa')
        sm = storage_manager._get_instance()
        sm.put_blueprint('blueprint-id', blueprint)

        blueprint_restored = sm.get_blueprint('blueprint-id',
                                              {'id', 'created_at'})
        self.assertEquals('blueprint-id', blueprint_restored.id)
        self.assertEquals(now, blueprint_restored.created_at)
        self.assertEquals(None, blueprint_restored.updated_at)
        self.assertEquals(None, blueprint_restored.plan)
        self.assertEquals(None, blueprint_restored.main_file_name)
