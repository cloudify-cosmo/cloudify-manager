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
        token = user_handler.get_token_from_request(request)
        api_token = user_handler.get_api_token_from_request(request)
        if auth:            # User + Password authentication
            user = user_handler.get_user_from_auth(auth)
            user = self._authenticate_password(user, auth)
        elif token:         # Token authentication
            user = self._authenticate_token(token)
        elif api_token:     # API token authentication
            user, user_token_key = user_handler.extract_api_token(api_token)
            if not user or user.api_token_key != user_token_key:
                raise_unauthorized_user_error(
                    'API token authentication failed')
        else:
            raise_unauthorized_user_error('No authentication '
                                          'info provided')

        user.last_login_at = datetime.now()
        user_datastore.commit()
        return user

    def _authenticate_password(self, user, auth):
        self.logger.debug('Authenticating username/password')
        username, password = auth.username, auth.password

        # If LDAP is not configured, *or* if the user is the bootstrap admin
        # we should run a basic HTTP auth
        if (user and user.is_bootstrap_admin) or not self.ldap:
            return self._http_auth(user, username, password)
        # Otherwise, we authenticate through LDAP
        else:
            return self._ldap_auth(user, username, password)

    def _http_auth(self, user, username, password):
        """Perform basic user authentication
        - Check that the password that was passed in the request can be
          verified against the password stored in the DB

        :param user: The DB user object
        :param username: The username from the request
        :param password: The password from the request
        :return: The DB user object
        """
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

    def _ldap_auth(self, user, username, password):
        """Perform LDAP user authentication
        - Authenticate the username and password against the LDAP server
        - If the user exists in the DB, update its groups and login date
        - If the user doesn't exist in the DB, create it with data from LDAP

        :param user: The DB user object
        :param username: The username from the request
        :param password: The password from the request
        :return: The DB user object
        """
        self.logger.debug('Running LDAP authentication')
        self.ldap.authenticate_user(username, password)
        if user:
            return self.ldap.update_user(user)
        else:
            return self.ldap.create_user(username)

    def _authenticate_token(self, token):
        """Make sure that the token passed exists, is valid, is not expired,
        and that the user contained within it exists in the DB

        :param token: An authentication token
        :return: A tuple: (A user object, its hashed password)
        """
        self.logger.debug('Authenticating token')
        expired, invalid, user, data, error = \
            user_handler.get_token_status(token)

        if invalid or (not isinstance(data, list) or len(data) != 2):
            raise_unauthorized_user_error(
                'Authentication token is invalid:\n{0}'.format(error)
            )
        elif expired:
            raise_unauthorized_user_error('Token is expired')
        elif not user:
            raise_unauthorized_user_error('No authentication info provided')
        elif md5(user.password) != data[1]:
            raise_unauthorized_user_error(
                'Authentication failed for {0}'.format(user)
            )

        return user


authenticator = Authentication()
