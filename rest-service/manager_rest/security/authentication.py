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

from datetime import datetime
from collections import namedtuple

from flask import current_app
from flask_security.utils import verify_password, md5

from manager_rest.storage import user_datastore
from manager_rest.app_logging import raise_unauthorized_user_error

from . import user_handler


Authorization = namedtuple('Authorization', 'username password')


class Authentication(object):
    @property
    def logger(self):
        return current_app.logger

    @property
    def ldap(self):
        return current_app.ldap

    def authenticate(self, request):
        auth = request.authorization
        if auth:    # User + Password authentication
            user = user_handler.get_user_from_auth(auth)
            user = self._authenticate_password(user, auth)
        else:       # Token authentication
            token = user_handler.get_token_from_request(request)
            if not token:
                raise_unauthorized_user_error('No authentication '
                                              'info provided')
            user = self._authenticate_token(token)

        user.last_login_at = datetime.now()
        user_datastore.commit()
        return user

    def _authenticate_password(self, user, auth):
        self.logger.debug('Authenticating username/password')
        username, password = auth.username, auth.password
        if self.ldap:
            self.logger.debug('Running LDAP authentication')
            self.ldap.authenticate_user(username, password)
            if user:
                user = self.ldap.update_user(user)
            else:
                user = self.ldap.create_user(username)
        else:
            self.logger.debug('Running basic HTTP authentication')
            if not user:
                raise_unauthorized_user_error(
                    'Authentication failed for '
                    '<User username=`{0}`>'.format(username)
                )
            if not verify_password(password, user.password):
                raise_unauthorized_user_error(
                    'Authentication failed for {0}'.format(user)
                )
        return user

    def _authenticate_token(self, token):
        """Make sure that the token passed exists, is valid, is not expired,
        and that the user contained within it exists in the DB

        :param token: An authentication token
        :return: A tuple: (A user object, its hashed password)
        """
        self.logger.debug('Authenticating token')
        expired, invalid, user, data = user_handler.get_token_status(token)

        if invalid or (not isinstance(data, list) or len(data) != 2):
            raise_unauthorized_user_error('Authentication token is invalid')
        elif expired:
            raise_unauthorized_user_error('Token is expired')
        elif not user:
            raise_unauthorized_user_error('No authentication info provided')
        elif md5(user.password) != data[1]:
            raise_unauthorized_user_error(
                'Authentication failed for {0}'.format(user)
            )

        return user

    @staticmethod
    def _basic_http_authenticate(user, hashed_pass):
        """Assert that `user` exists and that its stored password matches the
        one passed

        :param user: A valid user object, or None
        :param hashed_pass: md5 hashed password, or None
        """
        if not user or user.password != hashed_pass:
            raise_unauthorized_user_error('HTTP authentication failed '
                                          'for {0}'.format(user))

        # Reloading the user from the datastore, because the current user
        # object is detached from a session
        return user_datastore.get_user(user.username)


authenticator = Authentication()
