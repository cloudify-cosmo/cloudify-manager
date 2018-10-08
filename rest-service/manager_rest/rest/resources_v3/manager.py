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

from flask import request
from flask import current_app

from cloudify.models_states import VisibilityState

from manager_rest.security import SecuredResource
from manager_rest import config, premium_enabled, utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.manager_exceptions import (BadParametersError,
                                             MethodNotAllowedError,
                                             UnauthorizedError,
                                             NotFoundError)
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER,
                                    FILE_SERVER_TENANT_RESOURCES_FOLDER)

from .. import rest_decorators, rest_utils
from ...security.authentication import authenticator
from ..responses_v3 import BaseResponse, ResourceID

try:
    from cloudify_premium import LdapResponse
except ImportError:
    LdapResponse = BaseResponse


class FileServerAuth(SecuredResource):
    @staticmethod
    def _verify_tenant(uri):
        tenanted_resources = [
            FILE_SERVER_BLUEPRINTS_FOLDER,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            FILE_SERVER_DEPLOYMENTS_FOLDER,
            FILE_SERVER_TENANT_RESOURCES_FOLDER
        ]
        tenanted_resources = [r.strip('/') for r in tenanted_resources]
        uri = uri.strip('/')

        # verifying that the only tenant that can be accessed is the one in
        # the header
        for resource in tenanted_resources:
            if uri.startswith(resource):
                # Example of uri: 'blueprints/default_tenant/blueprint_1/
                # scripts/configure.sh'
                _, uri_tenant = uri.split('/', 2)[:2]
                authenticator.authenticate(request)

                # if it's global blueprint - no need or tenant verification
                # first load requested tenant to config then check if global
                tenant = get_storage_manager().get(
                    models.Tenant,
                    uri_tenant,
                    filters={'name': uri_tenant}
                )
                utils.set_current_tenant(tenant)
                if FileServerAuth._is_global_blueprint(uri):
                    return

                @authorize('file_server_auth', uri_tenant)
                def _authorize():
                    pass

                _authorize()
                return

    @staticmethod
    def _is_global_blueprint(uri):
        try:
            resource, tenant, resource_id = uri.split('/')[:3]
        except Exception:
            # in case of different format of file server uri
            return False
        if resource not in [FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                            FILE_SERVER_BLUEPRINTS_FOLDER]:
            return False
        try:
            blueprint = get_storage_manager().get(models.Blueprint,
                                                  resource_id)
        except NotFoundError:
            return False
        return blueprint.visibility == VisibilityState.GLOBAL

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
    @authorize('ldap_set')
    @rest_decorators.marshal_with(LdapResponse)
    def post(self):
        ldap_config = self._validate_set_ldap_request()

        from cloudify_premium.authentication.ldap_authentication \
            import LdapAuthentication

        # update current configuration
        for key, value in ldap_config.iteritems():
            setattr(config.instance, key, value)

        # assert LDAP configuration is valid (if credential supplied).
        if ldap_config['ldap_username']:
            auth = LdapAuthentication()
            auth.configure(current_app.logger)
            try:
                auth.authenticate_user(ldap_config.get('ldap_username'),
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

    @rest_decorators.exceptions_handled
    @authorize('ldap_status_get')
    def get(self):
        return 'enabled' if config.instance.ldap_server else 'disabled'

    @staticmethod
    def _only_admin_in_manager():
        """
        True if no users other than the admin user exists.
        :return:
        """
        users = get_storage_manager().list(models.User)
        return len(users) == 1

    def _validate_set_ldap_request(self):
        if not self._only_admin_in_manager():
            raise MethodNotAllowedError('LDAP Configuration may be set only on'
                                        ' a clean manager.')
        if not premium_enabled:
            raise MethodNotAllowedError('LDAP is only supported in the '
                                        'Cloudify premium edition.')
        ldap_config = rest_utils.get_json_and_verify_params({
            'ldap_server': {},
            'ldap_username': {'optional': True},
            'ldap_password': {'optional': True},
            'ldap_domain': {},
            'ldap_is_active_directory': {'optional': True},
            'ldap_dn_extra': {}
        })
        # Not allowing empty username or password
        ldap_config['ldap_username'] = ldap_config.get('ldap_username') or None
        ldap_config['ldap_password'] = ldap_config.get('ldap_password') or None
        ldap_config['ldap_is_active_directory'] = \
            rest_utils.verify_and_convert_bool(
                'ldap_is_active_directory',
                ldap_config.get('skip_uninstall', 'false')
            )

        if ((ldap_config['ldap_username']
             and not ldap_config['ldap_password'])
            or (ldap_config['ldap_password']
                and not ldap_config['ldap_username'])):
            raise BadParametersError(
                'Must supply either both username and password or neither. '
                'Note that an empty username or password is invalid')

        return ldap_config
