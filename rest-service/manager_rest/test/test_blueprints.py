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

__author__ = 'dan'


from base_test import BaseServerTestCase


class BlueprintsTestCase(BaseServerTestCase):

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_get_nonexistent_blueprint(self):
        get_blueprint_response = self.get('/blueprints/15').json
        self.assertTrue('404' in get_blueprint_response['message'])

    def test_post_and_then_search(self):
        post_blueprints_response = self.post_file(
            *self.post_blueprint_args()).json
        self.assertEquals('hello_world', post_blueprints_response['id'])
        get_blueprints_response = self.get('/blueprints').json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_post_blueprint_already_exists(self):
        self.post_file(*self.post_blueprint_args())
        post_blueprints_response = self.post_file(*self.post_blueprint_args())
        self.assertTrue('already exists' in
                        post_blueprints_response.json['message'])
        self.assertEqual(409, post_blueprints_response.status_code)

    def test_put_blueprint(self):
        blueprint_id = 'new_blueprint_id'
        put_blueprints_response = self.put_file(
            *self.post_blueprint_args(blueprint_id=blueprint_id)).json
        self.assertEqual(blueprint_id, put_blueprints_response['id'])

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.post_file(
            *self.post_blueprint_args(convention=True)).json
        self.assertEquals('hello_world',
                          post_blueprints_response['id'])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.post_file(
            *self.post_blueprint_args()).json
        get_blueprint_by_id_response = self.get(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        # setting 'source' field to be None as expected
        self.assertEquals(post_blueprints_response,
                          get_blueprint_by_id_response)

    def test_delete_blueprint(self):
        post_blueprints_response = self.post_file(
            *self.post_blueprint_args()).json

        # testing if resources are on fileserver
        self.assertTrue(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # deleting the blueprint that was just uploaded
        delete_blueprint_response = self.delete(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response['id'],
                          delete_blueprint_response['id'])

        # verifying deletion of blueprint
        resp = self.get('/blueprints/{0}'.format(post_blueprints_response[
                        'id']))
        self.assertEquals(404, resp.status_code)

        # verifying deletion of fileserver resources
        self.assertFalse(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # trying to delete a nonexistent blueprint
        resp = self.delete('/blueprints/nonexistent-blueprint')
        self.assertEquals(404, resp.status_code)

    def test_zipped_plugin(self):
        self.post_file(*self.post_blueprint_args())
        self.check_if_resource_on_fileserver('hello_world',
                                             'plugins/stub-installer.zip')
