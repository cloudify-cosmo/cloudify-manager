from base_test import BaseServerTestCase


class SecurityTestCase(BaseServerTestCase):

    def setUp(self):
        self._secured = True
        super(SecurityTestCase, self).setUp()

    def test_secured_client(self):
        client = self.create_client(user='user1', password='pass1')
        client.deployments.list()

    def tearDown(self):
        self._secured = True
        super(SecurityTestCase, self).tearDown()