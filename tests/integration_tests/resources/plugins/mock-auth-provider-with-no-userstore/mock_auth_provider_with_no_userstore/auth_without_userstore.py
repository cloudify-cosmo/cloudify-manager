#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from itsdangerous import base64_decode
from flask import request
from flask_securest.authentication_providers.abstract_authentication_provider\
    import AbstractAuthenticationProvider

AUTH_HEADER_NAME = 'Authorization'
BASIC_AUTH_PREFIX = 'Basic'


class AuthorizeUserByUsername(AbstractAuthenticationProvider):

    @staticmethod
    def _retrieve_request_credentials():
        auth_header = request.headers.get(AUTH_HEADER_NAME)
        if not auth_header:
            raise RuntimeError('Request authentication header "{0}" is empty '
                               'or missing'.format(AUTH_HEADER_NAME))

        auth_header = auth_header.replace(BASIC_AUTH_PREFIX + ' ', '', 1)
        try:
            api_key = base64_decode(auth_header)
        except TypeError:
            pass
        else:
            api_key_parts = api_key.split(':')
            request_user_id = api_key_parts[0]
            request_password = api_key_parts[1]
            if not request_user_id or not request_password:
                raise RuntimeError('username or password not found on request')

        return request_user_id, request_password

    def authenticate(self, userstore):
        request_user_id, _ = self._retrieve_request_credentials()
        if request_user_id != 'not_the_default_username':
            raise Exception('authentication of {0} failed'.
                            format(self.request_user_id))

        return {'username': 'mockusername',
                'password': 'mockpassword',
                'email:': 'mockemail@mock.com',
                'roles': [],
                'active': True
                }
