__author__ = 'dan'

import unittest
import json
from manager_rest import server


class BaseServerTestCase(unittest.TestCase):

    def setUp(self):
        server.reset_state(self.create_configuration())
        server.app.config['Testing'] = True
        server.main()
        self.app = server.app.test_client()

    def tearDown(self):
        server.stop_file_server()

    def create_configuration(self):
        from config import Config
        config = Config()
        config.test_mode = True
        return config

    def post(self, resource_path, data):
        result = self.app.post(resource_path, content_type='application/json', data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def post_file(self, resource_path, file_path, attribute_name, file_name, data):
        with open(file_path) as f:
            result = self.app.post(resource_path, data=dict({attribute_name: (f, file_name)}.items() + data.items()))
            result.json = json.loads(result.data)
            return result

    def put(self, resource_path, data):
        result = self.app.put(resource_path, content_type='application/json', data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def patch(self, resource_path, data):
        result = self.app.patch(resource_path, content_type='application/json', data=json.dumps(data))
        result.json = json.loads(result.data)
        return result

    def get(self, resource_path):
        result = self.app.get(resource_path)
        result.json = json.loads(result.data)
        return result

    def head(self, resource_path):
        result = self.app.get(resource_path)
        result.json = json.loads(result.data)
        print "result.json:: ", result.json
        print "result:: ", result
        return result



