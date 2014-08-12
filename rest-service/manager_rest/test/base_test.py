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

import unittest
import json
import urllib
import urllib2
import tempfile
import os
import tarfile

from manager_rest import server, util, config, storage_manager
from manager_rest.file_server import FileServer
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import HTTPClient


STORAGE_MANAGER_MODULE_NAME = 'file_storage_manager'
FILE_SERVER_PORT = 53229
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'
FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_RESOURCES_URI = '/resources'


class MockHTTPClient(HTTPClient):

    def __init__(self, app):
        super(MockHTTPClient, self).__init__('localhost')
        self.app = app

    @staticmethod
    def _build_url(resource_path, query_params):
        query_string = ''
        if query_params and len(query_params) > 0:
            query_string += '&' + urllib.urlencode(query_params)
            return '{0}?{1}'.format(urllib.quote(resource_path), query_string)
        return resource_path

    def do_request(self,
                   requests_method,
                   uri,
                   data=None,
                   params=None,
                   expected_status_code=200):
        if 'get' in requests_method.__name__:
            response = self.app.get(self._build_url(uri, params))

        elif 'put' in requests_method.__name__:
            response = self.app.put(self._build_url(uri, params),
                                    content_type='application/json',
                                    data=json.dumps(data))
        elif 'post' in requests_method.__name__:
            response = self.app.post(self._build_url(uri, params),
                                     content_type='application/json',
                                     data=json.dumps(data))
        else:
            raise NotImplemented()
        if response.status_code != expected_status_code:
            response.content = response.data
            response.json = lambda: json.loads(response.data)
            self._raise_client_error(response, uri)

        return json.loads(response.data)


class BaseServerTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.file_server = FileServer(self.tmpdir)
        self.file_server.start()
        storage_manager.storage_manager_module_name = \
            STORAGE_MANAGER_MODULE_NAME
        server.reset_state(self.create_configuration())
        util.copy_resources(config.instance().file_server_root)
        server.setup_app()
        server.app.config['Testing'] = True
        self.app = server.app.test_client()
        self.client = CloudifyClient('localhost')
        mock_http_client = MockHTTPClient(self.app)
        self.client.blueprints.api = mock_http_client
        self.client.deployments.api = mock_http_client
        self.client.executions.api = mock_http_client
        self.client.nodes.api = mock_http_client
        self.client.node_instances.api = mock_http_client
        self.client.manager.api = mock_http_client

    def tearDown(self):
        self.file_server.stop()

    def create_configuration(self):
        from manager_rest.config import Config
        test_config = Config()
        test_config.test_mode = True
        test_config.file_server_root = self.tmpdir
        test_config.file_server_base_uri = 'http://localhost:{0}'.format(
            FILE_SERVER_PORT)
        test_config.file_server_blueprints_folder = \
            FILE_SERVER_BLUEPRINTS_FOLDER
        test_config.file_server_uploaded_blueprints_folder = \
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER
        test_config.file_server_resources_uri = FILE_SERVER_RESOURCES_URI
        return test_config

    def post(self, resource_path, data, query_params=None):
        url = self._build_url(resource_path, query_params)
        result = self.app.post(url,
                               content_type='application/json',
                               data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def post_file(self, resource_path, file_path, query_params=None):
        with open(file_path) as f:
            result = self.app.post(
                self._build_url(resource_path, query_params), data=f.read())
            result.json = json.loads(result.data)
            return result

    def put_file(self, resource_path, file_path, query_params=None):
        with open(file_path) as f:
            result = self.app.put(
                self._build_url(resource_path, query_params), data=f.read())
            result.json = json.loads(result.data)
            return result

    def put(self, resource_path, data):
        result = self.app.put(urllib.quote(resource_path),
                              content_type='application/json',
                              data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def patch(self, resource_path, data):
        result = self.app.patch(urllib.quote(resource_path),
                                content_type='application/json',
                                data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def get(self, resource_path, query_params=None):
        result = self.app.get(self._build_url(resource_path, query_params))
        result.json = json.loads(result.data)
        return result

    def head(self, resource_path):
        result = self.app.head(urllib.quote(resource_path))
        return result

    def delete(self, resource_path, query_params=None):
        result = self.app.delete(self._build_url(resource_path, query_params))
        result.json = json.loads(result.data)
        return result

    def check_if_resource_on_fileserver(self, blueprint_id, resource_path):
        url = 'http://localhost:{0}/{1}/{2}/{3}'.format(
            FILE_SERVER_PORT, FILE_SERVER_BLUEPRINTS_FOLDER,
            blueprint_id, resource_path)
        try:
            urllib2.urlopen(url)
            return True
        except urllib2.HTTPError:
            return False

    def put_blueprint_args(self, blueprint_file_name=None,
                           blueprint_id='blueprint'):
        def make_tarfile(output_filename, source_dir):
            with tarfile.open(output_filename, "w:gz") as tar:
                tar.add(source_dir, arcname=os.path.basename(source_dir))

        def tar_mock_blueprint():
            tar_path = tempfile.mktemp()
            source_dir = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), 'mock_blueprint')
            make_tarfile(tar_path, source_dir)
            return tar_path

        resource_path = '/blueprints/{0}'.format(blueprint_id)
        result = [
            resource_path,
            tar_mock_blueprint(),
        ]

        if blueprint_file_name:
            data = {'application_file_name': blueprint_file_name}
        else:
            data = {}

        result.append(data)
        return result

    def put_deployment(self, deployment_id='deployment',
                       blueprint_file_name=None, blueprint_id='blueprint'):
        blueprint_response = self.put_file(
            *self.put_blueprint_args(blueprint_file_name, blueprint_id)).json
        try:
            blueprint_id = blueprint_response['id']
            # Execute post deployment
            deployment_response = self.put(
                '/deployments/{0}'.format(deployment_id),
                {'blueprint_id': blueprint_id}).json
            return (blueprint_id, deployment_response['id'],
                    blueprint_response,
                    deployment_response)
        except:
            raise RuntimeError(blueprint_response)

    def _build_url(self, resource_path, query_params):
        query_string = ''
        if query_params and len(query_params) > 0:
            query_string += '&' + urllib.urlencode(query_params)
            return '{0}?{1}'.format(urllib.quote(resource_path), query_string)
        return resource_path
