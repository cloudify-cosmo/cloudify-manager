__author__ = 'noak'

from base_test import BaseServerTestCase
import urllib


class SecurityTestCase(BaseServerTestCase):

    def test_secured_resource(self):
        from itsdangerous import base64_encode
        creds = 'user1:pass1'
        encoded_creds = base64_encode(creds)
        # encoded_creds = urllib.urlencode(creds)
        auth_header = {'Authorization': encoded_creds}
        result = self.get('/status', headers=auth_header)
        # result = self.get('/status')
        print 'result of get /status:', result
