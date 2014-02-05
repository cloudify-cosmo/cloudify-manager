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

import json
import unittest
from datetime import datetime
from manager_rest import storage_manager, responses
import base_test


class StorageManagerTests(base_test.BaseServerTestCase):

    def test_store_load_blueprint(self):
        blueprint = responses.BlueprintState()
        blueprint.id = 'blueprint-id'
        blueprint.created_at = str(datetime.now())
        storage_manager.instance().put_blueprint('blueprint-id', blueprint)
        blueprint_from_list = storage_manager.instance().blueprints_list()[0]
        blueprint_restored = \
            storage_manager.instance().get_blueprint('blueprint-id')
        self.assertEquals(blueprint.__dict__, blueprint_from_list.__dict__)
        self.assertEquals(blueprint.__dict__, blueprint_restored.__dict__)

    def test_json_encode_decode(self):
        workflows = responses.Workflows()
        workflows.blueprint_id = 'blueprint-id'
        workflow1 = responses.Workflow().init(workflow_id='workflow1',
                                              created_at='just-now')
        workflow2 = responses.Workflow().init(workflow_id='workflow2',
                                              created_at='just-now-too')
        workflows.workflows = [workflow1, workflow2]
        workflows_dict = workflows.to_dict()
        workflows_json_encoded = json.dumps(workflows_dict)
        workflows_json_decoded = json.loads(workflows_json_encoded)
        workflows_restored = workflows.from_dict(
            workflows_json_decoded['data'])

        self.assertEquals(workflows.blueprint_id,
                          workflows_restored.blueprint_id)
        self.assertEquals(workflows.deployment_id,
                          workflows_restored.deployment_id)
        self.assertEquals(2, len(workflows_restored.workflows))
        self.assertEquals(workflows.workflows[0].created_at,
                          workflows_restored.workflows[0].created_at)
        self.assertEquals(workflows.workflows[0].name,
                          workflows_restored.workflows[0].name)
        self.assertEquals(workflows.workflows[1].created_at,
                          workflows_restored.workflows[1].created_at)
        self.assertEquals(workflows.workflows[1].name,
                          workflows_restored.workflows[1].name)
        self.assertTrue(hasattr(workflows_restored, 'resource_fields'))
        self.assertTrue(hasattr(workflows_restored.workflows[0],
                                'resource_fields'))
        self.assertTrue(hasattr(workflows_restored.workflows[1],
                                'resource_fields'))


