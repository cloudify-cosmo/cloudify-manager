#########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

from flask import current_app, Response
from flask_security.utils import verify_password, verify_hash

from cloudify.workflows import tasks
from cloudify.models_states import ExecutionState

from manager_rest.security import user_handler
from manager_rest.storage import user_datastore
from manager_rest.security.hash_request_cache import HashVerifyRequestCache
from manager_rest.execution_token import (
    current_execution,
    get_execution_token_from_request
)
from manager_rest.manager_exceptions import UnauthorizedError, NoAuthProvided


Authorization = namedtuple('Authorization', 'username password')
failed_auth_message = 'Authentication failed for <User username=`{0}`>. ' \
                      'Wrong credentials or locked account'


class Authentication(object):
    def __init__(self):
        self.token_based_auth = False
        self.token_verified_cache = HashVerifyRequestCache()

    @property
    def logger(self):
        return current_app.logger

    @property
    def external_auth(self):
        return current_app.external_auth

    @property
    def external_auth_configured(self):
        return current_app.external_auth \
            and current_app.external_auth.configured()

    @staticmethod
    def _increment_failed_logins_counter(user):
        user.last_failed_login_at = datetime.utcnow()
        user.failed_logins_counter += 1
        user_datastore.commit()

    def authenticate(self, request):
        user = self._internal_auth(request)
        is_bootstrap_admin = user and user.is_bootstrap_admin
        if self.external_auth_configured \
                and not is_bootstrap_admin \
                and not self.token_based_auth:
            self.logger.debug('using external auth')
            user = user_handler.get_user_from_auth(request.authorization)
            response = self.external_auth.authenticate(request, user)
            if isinstance(response, Response):
                return response
            user = response
        if not user:
            raise NoAuthProvided()
        self.logger.debug('Authenticated user: {0}'.format(user))

        if request.authorization:
            # Reset the counter only when using basic authentication
            # (User + Password), otherwise the counter will be reset on
            # every UI refresh (every 4 sec) and accounts won't be locked.
            user.failed_logins_counter = 0
            now = datetime.utcnow()
            if not user.last_login_at:
                user.first_login_at = now
            user.last_login_at = now
        user_datastore.commit()
        return user

    def _internal_auth(self, request):
        user = None
        auth = request.authorization
        token = user_handler.get_token_from_request(request)
        api_token = user_handler.get_api_token_from_request(request)
        execution_token = get_execution_token_from_request(request)
        self.token_based_auth = token or api_token or execution_token
        if auth:  # Basic authentication (User + Password)
            user = user_handler.get_user_from_auth(auth)
            self._check_if_user_is_locked(user, auth)
            user = self._authenticate_password(user, auth)
        elif execution_token:  # Execution Token authentication
            user = self._authenticate_execution_token()
        elif token:  # Token authentication
            user = self._authenticate_token(token)
        elif api_token:  # API token authentication
            user, user_token_key = user_handler.extract_api_token(api_token)
            if not user or user.api_token_key != user_token_key:
                raise UnauthorizedError('API token authentication failed')
        return user

    def _check_if_user_is_locked(self, user, auth):
        if self.external_auth_configured:
            return user
        if not user or user.is_locked:
            raise UnauthorizedError(failed_auth_message.format(auth.username))

    def _authenticate_password(self, user, auth):
        self.logger.debug('Authenticating username/password')
        is_bootstrap_admin = user and user.is_bootstrap_admin
        if self.external_auth_configured and not is_bootstrap_admin:
            # if external_auth is configured, use it
            return None
        username, password = auth.username, auth.password
        return self._http_auth(user, username, password)

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
            raise UnauthorizedError(failed_auth_message.format(username))
        if not verify_password(password, user.password):
            self._increment_failed_logins_counter(user)
            raise UnauthorizedError(failed_auth_message.format(username))
        return user

    def _verify_token(self, token, user):
        if not self.token_verified_cache.get_verify_hash_result(token,
                                                                user.id):
            if not verify_hash(compare_data=user.password, hashed_data=token):
                raise UnauthorizedError(
                    failed_auth_message.format(user.username))
            else:
                self.token_verified_cache.cache_verify_hash_result(token,
                                                                   user.id)

    def _authenticate_token(self, token):
        """Make sure that the token passed exists, is valid, is not expired,
        and that the user contained within it exists in the DB

        :param token: An authentication token
        :return: A tuple: (A user object, its hashed password)
        """
        self.logger.debug('Authenticating token')
        expired, invalid, user, data, error = \
            user_handler.get_token_status(token)

        if expired:
            raise UnauthorizedError('Token is expired')
        elif invalid or (not isinstance(data, list) or len(data) != 2):
            raise UnauthorizedError(
                'Authentication token is invalid:\n{0}'.format(error)
            )
        elif not user:
            raise NoAuthProvided()
        else:
            self._verify_token(token=data[1], user=user)

        return user

    def _authenticate_execution_token(self):
        """Make sure the token passed exists and valid (by verifying the
           current_execution). Valid token is connected to an active execution

        :return: A user object
        """
        self.logger.debug('Authenticating execution token')
        error_msg = 'Authentication failed, invalid Execution Token'
        if not current_execution:
            self.logger.debug('{0}. Exactly one execution should match this '
                              'token'.format(error_msg))
            raise UnauthorizedError(error_msg)

        if current_execution.status not in ExecutionState.ACTIVE_STATES:
            if self._is_valid_scheduled_execution() or \
                    self._is_valid_cancelled_execution():
                return current_execution.creator

            # Not an active execution
            self.logger.debug('{0}. The execution is not active'
                              .format(error_msg))
            raise UnauthorizedError(error_msg)
        return current_execution.creator

    @staticmethod
    def _is_valid_scheduled_execution():
        """Check if it's a scheduled execution that is just started to run"""
        if current_execution.status == ExecutionState.SCHEDULED:
            current_time = datetime.utcnow()
            scheduled_for = datetime.strptime(current_execution.scheduled_for,
                                              '%Y-%m-%dT%H:%M:%S.%fZ')
            # The scheduled execution just started to run
            return abs((current_time - scheduled_for).total_seconds()) < 60
        return False

    @staticmethod
    def _is_valid_cancelled_execution():
        """Check if it's a cancelled execution that has running operations"""
        if current_execution.status != ExecutionState.CANCELLED:
            return False

        for graph in current_execution.tasks_graphs:
            for operation in graph.operations:
                if operation.state not in tasks.TERMINATED_STATES:
                    return True
        return False


authenticator = Authentication()
