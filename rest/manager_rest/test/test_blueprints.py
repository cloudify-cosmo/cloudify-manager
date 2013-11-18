__author__ = 'dan'


from base_test import BaseServerTestCase


class BlueprintsTestCase(BaseServerTestCase):

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post(self):
        result = self.post('/blueprints', {})
        print result.status_code
