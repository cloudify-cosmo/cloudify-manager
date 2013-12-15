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

class BlueprintsTestCase(BaseServerTestCase):

    def post_blueprint_args(self):
        def make_tarfile(output_filename, source_dir):
            with tarfile.open(output_filename, "w:gz") as tar:
                tar.add(source_dir, arcname=os.path.basename(source_dir))

        def tar_mock_blueprint():
            tar_path = tempfile.mktemp()
            source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_blueprint')
            make_tarfile(tar_path, source_dir)
            return tar_path

        return [
            '/blueprints',
            tar_mock_blueprint(),
            'application_archive',
            'mezzanine-app.tar.gz',
            {'application_file': 'mock_blueprint%2Fmezzanine_blueprint.yaml'}
        ]

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post_and_then_get(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        self.assertEquals('mezzanine', post_blueprints_response['name'])
        get_blueprints_response = self.get('/blueprints').json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        get_blueprint_by_id_response = self.get('/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response, get_blueprint_by_id_response)

    def test_post_blueprints_id_executions_and_then_get(self):
        blueprint = self.post_file(*self.post_blueprint_args()).json
        resource_path = '/blueprints/{0}/executions'.format(blueprint['id'])
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        self.assertEquals(execution['workflowId'], 'install')
        get_execution = self.get(resource_path).json
        self.assertEquals(1, len(get_execution))
        self.assertEquals(execution, get_execution[0])

    def test_get_blueprints_id_executions_empty(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        get_executions = self.get('/blueprints/{0}/executions'.format(post_blueprints_response['id'])).json
        self.assertEquals(len(get_executions), 0)

    def test_get_blueprints_id_validate(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        resource_path = '/blueprints/{0}/validate'.format(post_blueprints_response['id'])
        validation = self.get(resource_path).json
        self.assertEqual(validation['status'], 'valid')

    def test_get_executions_id(self):
        blueprint = self.post_file(*self.post_blueprint_args()).json
        resource_path = '/blueprints/{0}/executions'.format(blueprint['id'])
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        get_execution = self.get(get_execution_resource).json
        self.assertEquals(get_execution['status'], 'terminated')

    def test_zipped_plugin(self):
        self.post_file(*self.post_blueprint_args())
        from manager_rest.file_server import PORT as file_server_port
        response = requests.get('http://localhost:{0}/stub-installer.zip'.format(file_server_port))
        self.assertEquals(response.status_code, 200)

    def test_get_deployments_empty(self):
        result = self.get('/deployments')
        self.assertEquals(0, len(result.json))

    def test_install_then_get_deployments(self):
        blueprint = self.post_file(*self.post_blueprint_args()).json
        resource_path = '/blueprints/{0}/executions'.format(blueprint['id'])
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        deployment_id = execution['deploymentId']
        self.assertIsNotNone(deployment_id)
        get_deployments_response = self.get('/deployments').json
        self.assertEquals(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(blueprint['id'], single_deployment['blueprintId'])
        self.assertEquals(execution['id'], single_deployment['executionId'])
        self.assertEquals(execution['workflowId'], single_deployment['workflowId'])
        self.assertEquals(execution['createdAt'], single_deployment['createdAt'])
        self.assertEquals(execution['createdAt'], single_deployment['updatedAt'])
        import json
        typed_blueprint_plan = json.loads(blueprint['plan'])
        typed_deployment_plan = json.loads(single_deployment['plan'])
        self.assertEquals(typed_blueprint_plan['name'], typed_deployment_plan['name'])

    def test_install_then_get_deployment_by_id(self):
        blueprint = self.post_file(*self.post_blueprint_args()).json
        resource_path = '/blueprints/{0}/executions'.format(blueprint['id'])
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        deployment_id = execution['deploymentId']
        self.assertIsNotNone(deployment_id)
        single_deployment = self.get('/deployments/{0}'.format(deployment_id)).json
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(blueprint['id'], single_deployment['blueprintId'])
        self.assertEquals(execution['id'], single_deployment['executionId'])
        self.assertEquals(execution['workflowId'], single_deployment['workflowId'])
        self.assertEquals(execution['createdAt'], single_deployment['createdAt'])
        self.assertEquals(execution['createdAt'], single_deployment['updatedAt'])
        import json
        typed_blueprint_plan = json.loads(blueprint['plan'])
        typed_deployment_plan = json.loads(single_deployment['plan'])
        self.assertEquals(typed_blueprint_plan['name'], typed_deployment_plan['name'])