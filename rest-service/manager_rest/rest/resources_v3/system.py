#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
#

from flask_security import current_user
from flask import current_app, request

from manager_rest import config
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import (SecuredResource,
                                   SecuredResourceSkipTenantAuth)
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)
from manager_rest.manager_exceptions import (BadParametersError,
                                             MethodNotAllowedError,
                                             UnauthorizedError)
from manager_rest.security.authentication import authenticator
from manager_rest.security.tenant_authorization import tenant_authorizer

from .. import rest_decorators, rest_utils
from ..responses_v3 import BaseResponse, ResourceID

try:
    from cloudify_premium import LdapResponse
except ImportError:
    LdapResponse = BaseResponse


class FileServerAuth(SecuredResourceSkipTenantAuth):
    @staticmethod
    def _verify_tenant(uri):
        tenanted_resources = [
            FILE_SERVER_BLUEPRINTS_FOLDER,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            FILE_SERVER_DEPLOYMENTS_FOLDER
        ]
        tenanted_resources = [r.strip('/') for r in tenanted_resources]
        uri = uri.strip('/')

        # verifying that the only tenant that can be accessed is the one in
        # the header
        for resource in tenanted_resources:
            if uri.startswith(resource):
                uri = uri.replace(resource, '').strip('/')
                uri_tenant, _ = uri.split('/', 1)
                user = authenticator.authenticate(request)
                tenant_authorizer.authorize(user, request, uri_tenant)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ResourceID)
    def get(self, **_):
        """
        Verify that the user is allowed to access requested resource.

        The user cannot access tenants except the one in the request's header.
        """
        uri = request.headers.get('X-Original-Uri')
        self._verify_tenant(uri)

        # verified successfully
        return {}


class LdapAuthentication(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(LdapResponse)
    def post(self):
        ldap_config = self._validate_set_ldap_request()

        from cloudify_premium.multi_tenancy.ldap_authentication \
            import LdapAuthentication

        # update current configuration
        for key, value in ldap_config.iteritems():
            setattr(config.instance, key, value)

        # assert LDAP configuration is valid.
        authenticator = LdapAuthentication()
        authenticator.configure_ldap()
        try:
            authenticator.authenticate_user(ldap_config.get('ldap_username'),
                                            ldap_config.get('ldap_password'))
        except UnauthorizedError:
            # reload previous configuration.
            config.instance.load_configuration()
            raise BadParametersError(
                'Failed setting LDAP authenticator: Invalid parameters '
                'provided.')

        config.reset(config.instance, write=True)

        # Restart the rest service so that each the LDAP configuration
        # be loaded to all flask processes.
        rest_utils.set_restart_task()

        ldap_config.pop('ldap_password')
        return ldap_config

    @staticmethod
    def _validate_set_ldap_request():
        if not current_user.is_admin:
            raise UnauthorizedError('User is not authorized to set LDAP '
                                    'configuration.')
        if not LdapAuthentication._only_admin_in_manager():
            raise MethodNotAllowedError('LDAP Configuration may be set only on'
                                        ' a clean manager.')
        if not current_app.premium_enabled:
            raise MethodNotAllowedError('LDAP is only supported in the '
                                        'Cloudify premium edition.')
        ldap_config = rest_utils.get_json_and_verify_params({
            'ldap_server',
            'ldap_username',
            'ldap_password',
            'ldap_domain',
            'ldap_is_active_directory',
            'ldap_dn_extra'
        })
        return ldap_config

    @staticmethod
    def _only_admin_in_manager():
        """
        True if no users other than the admin user exists.
        :return:
        """
        users = get_storage_manager().list(models.User)
        return len(users) == 1
