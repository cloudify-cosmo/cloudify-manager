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

from flask_security.utils import md5

from .ldap import get_ldappy
from .security_models import user_datastore
from .user_handler import unauthorized_user_handler


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

        if not auth:
            # Creating this dummy auth object to have a simpler syntax
            # inside the auth methods
            auth = Authorization(user.username, user.password)

        # LDAP authentication
        if self._ldappy:
            user = self._ldap_authenticate_and_update_user(user, auth)
        else:
            # Basic HTTP authentication
            user = self._basic_http_authenticate(user, hashed_pass)

        user.last_login_at = datetime.now()
        user_datastore.commit()
        return user

    def configure_ldap(self):
        """Set the Ldappy instance; *must* be called after the configuration
        is loaded
        """
        self._ldappy = get_ldappy()

    def _ldap_authenticate_and_update_user(self, user, auth):
        """Authenticate the user against an LDAP server

        :param user: A valid user object, or None
        :param auth: flask.request.authorization, or None
        """

        if not self._ldappy.authenticate(auth.username, auth.password):
            unauthorized_user_handler(
                'LDAP authentication has failed for user: `{0}`'.
                format(auth.username)
            )

        if not user:
            # This might be the first time we authenticate this user, so we
            # might need to create it from the authorization data
            user = self._create_user(auth.username, auth.password)
        elif user.password != auth.password:
            # Reloading the user from the datastore, because the current user
            # object is detached from a session
            user = user_datastore.get_user(user.username)
            user.password = auth.password

        return user

    def _create_user(self, username, password):
        """Add a new user to the datastore using LDAP data

        :param username: Username
        :param password: Password
        :return: The newly created user
        """
        # TODO: roles/groups should go somewhere here as well
        ldap_user = self._ldappy.user_objects.get(name=username).pretty_data()

        # Getting the first element because ldappy always returns lists
        email = ldap_user.get('mail', [''])[0]
        first_name = ldap_user.get('first_name', [''])[0]
        last_name = ldap_user.get('last_name', [''])[0]

        return user_datastore.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            created_at=datetime.now()
        )

    @staticmethod
    def _basic_http_authenticate(user, hashed_pass):
        """Assert that `user` exists and that its stored password matches the
        one passed

        :param user: A valid user object, or None
        :param hashed_pass: md5 hashed password, or None
        """
        if not user or md5(user.password) != hashed_pass:
            unauthorized_user_handler('HTTP authentication failed')

        # Reloading the user from the datastore, because the current user
        # object is detached from a session
        return user_datastore.get_user(user.username)

authenticator = Authentication()

# Needs to be called only after the configuration was loaded
configure_ldap = authenticator.configure_ldap
