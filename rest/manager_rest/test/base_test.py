__author__ = 'dan'

import unittest
import json
from manager_rest import server, file_server

class BaseServerTestCase(unittest.TestCase):

    def setUp(self):
        self.file_server = file_server.FileServer()
        self.file_server.start()
        server.app.config['Testing'] = True
        self.app = server.app.test_client()

    def tearDown(self):
        self.file_server.stop()

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
        result = self.app.get(resource_path)
        result.json = json.loads(result.data)
        return result

