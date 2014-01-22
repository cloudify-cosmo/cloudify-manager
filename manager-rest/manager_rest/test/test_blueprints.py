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
import tempfile
import os
import tarfile
import requests


def post_blueprint_args(convention=False):
    def make_tarfile(output_filename, source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))

    def tar_mock_blueprint():
        tar_path = tempfile.mktemp()
        source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'mock_blueprint')
        make_tarfile(tar_path, source_dir)
        return tar_path

    result = [
        '/blueprints',
        tar_mock_blueprint(),
        ]

    if not convention:
        data = {'application_file_name': 'blueprint.yaml'}
    else:
        data = {}

    result.append(data)
    return result


class BlueprintsTestCase(BaseServerTestCase):

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post_and_then_get(self):
        post_blueprints_response = self.post_file(*post_blueprint_args()).json
        self.assertEquals('hello_world', post_blueprints_response['name'])
        get_blueprints_response = self.get('/blueprints').json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.post_file(
            *post_blueprint_args(convention=True)).json
        self.assertEquals('hello_world',
                          post_blueprints_response['name'])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.post_file(*post_blueprint_args()).json
        print "##### response:", post_blueprints_response
        get_blueprint_by_id_response = self.get(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response,
                          get_blueprint_by_id_response)

    def test_get_blueprints_id_validate(self):
        post_blueprints_response = self.post_file(*post_blueprint_args()).json
        resource_path = '/blueprints/{0}/validate'.format(
            post_blueprints_response['id'])
        validation = self.get(resource_path).json
        self.assertEqual(validation['status'], 'valid')

    def test_zipped_plugin(self):
        self.post_file(*post_blueprint_args())
        from manager_rest.file_server import PORT as FILE_SERVER_PORT
        response = requests.get(
            'http://localhost:{0}/stub-installer.zip'.format(FILE_SERVER_PORT))
        self.assertEquals(response.status_code, 200)
