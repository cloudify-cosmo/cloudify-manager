__author__ = 'dan'

import unittest
from base_test import BaseServerTestCase


class BlueprintsTestCase(BaseServerTestCase):

    def test_get(self):
        print self.get('/blueprints').data

    def test_post(self):
        result = self.post('/blueprints', {'data': 13})
        print result.status_code

if __name__ == '__main__':
    unittest.main()
