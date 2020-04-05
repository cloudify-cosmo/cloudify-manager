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
#

from manager_rest.test.attribute import attr

from manager_rest.test.base_test import BaseServerTestCase
from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=1, client_max_version=1)
class TestBlueprintsV1(BaseServerTestCase):
    """
    REST blueprints operations have changed in v2. This test class assures v1
    backwards compatibility has been preserved.
    """

    def test_blueprint_description(self):
        # In version 1, description should not be returned as part of the
        # response, but should still be available inside the DSL plan
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint.yaml',
                                     blueprint_id='blueprint')).json
        self.assertEqual('blueprint',
                         post_blueprints_response['id'])
        self.assertNotIn('description', post_blueprints_response)
        self.assertEqual("this is my blueprint's description",
                         post_blueprints_response['plan']['description'])

    def test_blueprint_main_file_name(self):
        # main_file_name should not be returned in blueprint response.
        blueprint_id = 'blueprint'
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint.yaml',
                                     blueprint_id=blueprint_id)).json

        self.assertNotIn('main_file_name', post_blueprints_response)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertNotIn('main_file_name', blueprint)

    def test_blueprint_v1(self):
        # tests blueprint put, get, and delete in V1.
        # put isn't tested via the client since the chunked upload we use
        # isn't supported by flask in unit tests
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint.yaml',
                                     blueprint_id='blueprint')).json
        blueprint = self.client.blueprints.get(blueprint_id='blueprint')
        self.assertEqual('blueprint', post_blueprints_response['id'])
        self.assertEqual(post_blueprints_response['id'], blueprint['id'])
        self.client.blueprints.delete(blueprint_id='blueprint')
        try:
            self.client.blueprints.get(blueprint_id='blueprint')
            self.fail('deleted blueprint is still available')
        except CloudifyClientError:
            pass
