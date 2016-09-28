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
from flask_security.utils import md5

from .security_models import user_datastore
from .user_handler import unauthorized_user_handler

try:
    from manager_rest.cloudify_premium import ldap_authenticator
except:
    ldap_authenticator = None


Authorization = namedtuple('Authorization', 'username password')


class Authentication(object):
    def __init__(self):
        self._ldappy = None

    def authenticate(self, user, hashed_pass, auth):
        """Authenticate the user either against an LDAP server, or our
        user datastore

        :param user: A valid user object, or None
        :param hashed_pass: md5 hashed password, or None
        :param auth: flask.request.authorization, or None
        :return: The updated user object
        """
        if not user and not auth:
            unauthorized_user_handler('No authentication info provided')

        logger = current_app.logger
        logger.debug('Running user authentication for user {0}'.format(user))

        if not auth:
            # Creating this dummy auth object to have a simpler syntax
            # inside the auth methods
            auth = Authorization(user.username, user.password)

        if self._ldappy and ldap_authenticator:
            logger.debug('Running authentication with LDAP')
            user = ldap_authenticator.ldap_authenticate_and_update_user(user,
                                                                        auth)
        else:
            logger.debug('Running Basic HTTP authentication')
            user = self._basic_http_authenticate(user, hashed_pass)

        user.last_login_at = datetime.now()
        user_datastore.commit()
        return user

    @staticmethod
    def _basic_http_authenticate(user, hashed_pass):
        """Assert that `user` exists and that its stored password matches the
        one passed

        :param user: A valid user object, or None
        :param hashed_pass: md5 hashed password, or None
        """
        if not user or md5(user.password) != hashed_pass:
            unauthorized_user_handler('HTTP authentication failed '
                                      'for user: {0}'.format(user))

        # Reloading the user from the datastore, because the current user
        # object is detached from a session
        return user_datastore.get_user(user.username)

authenticator = Authentication()
