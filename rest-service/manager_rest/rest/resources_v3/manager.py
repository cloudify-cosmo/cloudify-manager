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
                                             NotFoundError,
                                             NotListeningLDAPServer)
from manager_rest.workflow_executor import restart_restservice
from manager_rest.constants import (
    FILE_SERVER_BLUEPRINTS_FOLDER,
    FILE_SERVER_DEPLOYMENTS_FOLDER,
    FILE_SERVER_TENANT_RESOURCES_FOLDER,
    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
)

from .. import rest_decorators, rest_utils
from ...security.authentication import authenticator
from ..responses_v3 import BaseResponse, ResourceID


try:
    from cloudify_premium.multi_tenancy.responses import LdapResponse
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
        if uri.startswith('resources/'):
            uri = uri.replace('resources/', '', 1)
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
                    None,
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
    @authorize('ldap_set')
    @rest_decorators.marshal_with(LdapResponse)
    def post(self):
        ldap_config = self._validate_set_ldap_request()

        from cloudify_premium.authentication.ldap_authentication \
            import LdapAuthentication

        # update current configuration
        config.instance.update_db(ldap_config)

        # assert LDAP configuration is valid (if credential supplied).
        if ldap_config['ldap_username']:
            auth = LdapAuthentication()
            auth.configure(current_app.logger)
            try:
                auth.validate_connection()
                auth.authenticate_user(ldap_config.get('ldap_username'),
                                       ldap_config.get('ldap_password'))
            except (UnauthorizedError, NotListeningLDAPServer) as _ex:
                # reload previous configuration.
                error_msg = 'Failed setting LDAP' \
                            ' authenticator: Invalid parameters provided.'
                config.instance.load_configuration()
                if isinstance(_ex, NotListeningLDAPServer):
                    error_msg = \
                        'Failed setting LDAP: Unable to connect to ' \
                        'LDAP Server {0}'.format(ldap_config['ldap_server'])

                raise BadParametersError(error_msg)

        restart_restservice()

        ldap_config.pop('ldap_password')
        return ldap_config

    @authorize('ldap_status_get')
    def get(self):
        return 'enabled' if config.instance.ldap_server else 'disabled'

    def _validate_set_ldap_request(self):
        if not premium_enabled:
            raise MethodNotAllowedError('LDAP is only supported in the '
                                        'Cloudify premium edition.')
        base_substitutions = ['base_dn', 'domain_dn', 'group_dn']
        ldap_config = rest_utils.get_json_and_verify_params({
            'ldap_server': {},
            'ldap_domain': {},
            'ldap_username': {'optional': True},
            'ldap_password': {'optional': True},
            'ldap_is_active_directory': {'optional': True},
            'ldap_dn_extra': {'optional': True},
            'ldap_ca_cert': {'optional': True},
            'ldap_nested_levels': {'optional': True},
            'ldap_bind_format': {
                'optional': True,
                'allowed_substitutions': [
                    'username', 'domain'] + base_substitutions,
            },
            'ldap_group_dn': {
                'optional': True,
                'allowed_substitutions': ['base_dn', 'domain_dn'],
            },
            'ldap_base_dn': {'optional': True},
            'ldap_group_member_filter': {
                'optional': True,
                'allowed_substitutions': ['object_dn']
            },
            'ldap_user_filter': {
                'optional': True,
                'allowed_substitutions': ['username'] + base_substitutions,
            },
            'ldap_attribute_email': {'optional': True},
            'ldap_attribute_first_name': {'optional': True},
            'ldap_attribute_last_name': {'optional': True},
            'ldap_attribute_uid': {'optional': True},
            'ldap_attribute_group_membership': {'optional': True},
        })

        if ldap_config.get('ldap_nested_levels') is None:
            ldap_config['ldap_nested_levels'] = 1
        else:
            ldap_config['ldap_nested_levels'] = rest_utils.convert_to_int(
                ldap_config['ldap_nested_levels'])

        for attr in ldap_config:
            if ldap_config[attr] is None:
                # Otherwise we try to set None on the config entry, which is
                # not a string.
                ldap_config[attr] = ''

        ldap_config['ldap_is_active_directory'] = \
            rest_utils.verify_and_convert_bool(
                'ldap_is_active_directory',
                ldap_config.get('ldap_is_active_directory') or False
            )

        if ldap_config['ldap_server'].startswith('ldaps://'):
            if 'ldap_ca_cert' not in ldap_config:
                raise BadParametersError(
                    'A CA certificate must be provided to use ldaps.'
                )
        elif ldap_config['ldap_server'].startswith('ldap://'):
            if 'ldap_ca_cert' in ldap_config:
                raise BadParametersError(
                    'CA certificate cannot be provided when not using ldaps.'
                )
        else:
            raise BadParametersError(
                'ldap_server must specify protocol and should specify port, '
                'e.g. ldap://192.0.2.1:389 or ldaps://192.0.2.45:636'
            )

        user = ldap_config.get('ldap_username')
        password = ldap_config.get('ldap_password')
        if (user or password) and not (user and password):
            raise BadParametersError(
                'Must supply either both username and password or neither. '
                'Note that an empty username or password is invalid')

        return ldap_config
