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

from cloudify.models_states import VisibilityState

from manager_rest import utils
from manager_rest.test import base_test
from manager_rest.storage import models
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
        self.assertEquals(blueprint.to_dict(), blueprint_from_list.to_dict())
        self.assertEquals(blueprint.to_dict(), blueprint_restored.to_dict())
        # in bp returned from delete operation only 'id' is guaranteed to
        # return
        self.assertEquals(blueprint.id, bp_from_delete.id)
        blueprints_list = self.sm.list(models.Blueprint)
        self.assertEquals(0, len(blueprints_list))

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

        self.assertEquals(2, len(blueprint_deployments))
        if blueprint_deployments[0].id != deployment1.id:
            blueprint_deployments[0], blueprint_deployments[1] =\
                blueprint_deployments[1], blueprint_deployments[0]
        self.assertEquals(deployment1.to_dict(),
                          blueprint_deployments[0].to_dict())
        self.assertEquals(deployment2.to_dict(),
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
        self.assertEquals(20, len(serialized_dep))
        self.assertEquals(dep.id, serialized_dep['id'])
        self.assertEquals(dep.created_at, serialized_dep['created_at'])
        self.assertEquals(dep.updated_at, serialized_dep['updated_at'])
        self.assertEquals(dep.blueprint_id, serialized_dep['blueprint_id'])
        self.assertEquals(dep.permalink, serialized_dep['permalink'])
        self.assertEquals(dep.tenant.name, serialized_dep['tenant_name'])
        self.assertEquals(dep.description, None)

        # `blueprint_id` isn't a regular column, but a relationship
        serialized_dep.pop('blueprint_id')
        serialized_dep.pop('tenant_name')
        serialized_dep.pop('created_by')
        serialized_dep.pop('site_name')

        # Deprecated columns, for backwards compatibility -
        # was added to the response
        serialized_dep.pop('resource_availability')
        serialized_dep.pop('private_resource')

        deserialized_dep = models.Deployment(**serialized_dep)
        self.assertEquals(dep.id, deserialized_dep.id)
        self.assertEquals(dep.created_at, deserialized_dep.created_at)
        self.assertEquals(dep.updated_at, deserialized_dep.updated_at)
        self.assertEquals(dep.permalink, deserialized_dep.permalink)
        self.assertEquals(dep.description, deserialized_dep.description)

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
        self.assertEquals('blueprint-id', blueprint_restored.id)
        self.assertEquals(now, blueprint_restored.created_at)
        self.assertFalse(hasattr(blueprint_restored, 'updated_at'))
        self.assertFalse(hasattr(blueprint_restored, 'plan'))
        self.assertFalse(hasattr(blueprint_restored, 'main_file_name'))

    def test_all_results_query(self):
        now = utils.get_formatted_timestamp()
        for i in range(1, 1002):
            secret = models.Secret(id='secret_{}'.format(i),
                                   value='value',
                                   created_at=now,
                                   updated_at=now,
                                   visibility=VisibilityState.TENANT)
            self.sm.put(secret)

        secret_list = self.sm.list(
            models.Secret,
            include=['id', 'created_at'],
            get_all_results=True
        )
        self.assertEquals(1000, len(secret_list))
