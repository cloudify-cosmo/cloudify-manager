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

    def test_store_load_blueprint(self):
        now = str(datetime.now())
        blueprint = models.BlueprintState(id='blueprint-id',
                                          created_at=now,
                                          updated_at=now,
                                          plan={'name': 'my-bp'})
        storage_manager.instance().put_blueprint('blueprint-id', blueprint)
        blueprint_from_list = storage_manager.instance().blueprints_list()[0]
        blueprint_restored = \
            storage_manager.instance().get_blueprint('blueprint-id')
        self.assertEquals(blueprint.__dict__, blueprint_from_list.__dict__)
        self.assertEquals(blueprint.__dict__, blueprint_restored.__dict__)

    def test_model_serialization(self):
        dep = models.Deployment(id='dep-id',
                                created_at='some-time1',
                                updated_at='some-time2',
                                blueprint_id='bp-id',
                                plan={'field': 'value'})

        serialized_dep = dep.to_dict()
        self.assertEquals(6, len(serialized_dep))
        self.assertEquals(dep.id, serialized_dep['id'])
        self.assertEquals(dep.created_at, serialized_dep['created_at'])
        self.assertEquals(dep.updated_at, serialized_dep['updated_at'])
        self.assertEquals(dep.blueprint_id, serialized_dep['blueprint_id'])
        self.assertEquals(dep.plan, serialized_dep['plan'])
        self.assertEquals(dep.permalink, serialized_dep['permalink'])

        deserialized_dep = models.Deployment(**serialized_dep)
        self.assertEquals(dep.id, deserialized_dep.id)
        self.assertEquals(dep.created_at, deserialized_dep.created_at)
        self.assertEquals(dep.updated_at, deserialized_dep.updated_at)
        self.assertEquals(dep.blueprint_id, deserialized_dep.blueprint_id)
        self.assertEquals(dep.plan, deserialized_dep.plan)
        self.assertEquals(dep.permalink, deserialized_dep.permalink)
