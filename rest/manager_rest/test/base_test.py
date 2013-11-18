__author__ = 'dan'

import unittest
import json
from manager_rest import server

class BaseServerTestCase(unittest.TestCase):

    def setUp(self):
        server.app.config['Testing'] = True
        self.app = server.app.test_client()

    def tearDown(self):
        pass

    def post(self, resource_path, data):
        result = self.app.post(resource_path, content_type='application/json', data=json.dumps(data))
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
        return self.app.get(resource_path)

