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
from manager_rest import server, util, config, storage_manager
from manager_rest.file_server import FileServer

STORAGE_MANAGER_MODULE_NAME = 'file_storage_manager'
FILE_SERVER_PORT = 53229
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'


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

    def _build_url(self, resource_path, query_params):
        query_string = ''
        if query_params and len(query_params) > 0:
            query_string += '&' + urllib.urlencode(query_params)
        return '{0}?{1}'.format(urllib.quote(resource_path), query_string)
