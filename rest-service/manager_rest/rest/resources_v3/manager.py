import pydantic
import string
from typing import Optional

from flask import request
from flask import current_app

from cloudify.models_states import VisibilityState

from manager_rest.security import SecuredResource
from manager_rest import config, premium_enabled, utils
from manager_rest.security.authorization import (
    authorize,
    check_user_action_allowed,
)
from manager_rest.storage import models, get_storage_manager
from manager_rest.manager_exceptions import (BadParametersError,
                                             ForbiddenError,
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
from ...security.authentication import authenticate
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
        if uri.startswith('resources/'):
            uri = uri.replace('resources/', '', 1)
        # verifying that the only tenant that can be accessed is the one in
        # the header
        for resource in tenanted_resources:
            if uri.startswith(resource):
                # Example of uri: 'blueprints/default_tenant/blueprint_1/
                # scripts/configure.sh'
                _, uri_tenant = uri.split('/', 2)[:2]
                authenticate(request)

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

                check_user_action_allowed('file_server_auth', uri_tenant)
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

    @staticmethod
    def _verify_audit(uri, method):
        if method == 'GET':
            check_user_action_allowed('audit_log_view', None, True)
        elif method == 'DELETE':
            check_user_action_allowed('audit_log_truncate', None, True)
        elif method == 'POST':
            check_user_action_allowed('audit_log_inject', None, True)
        else:
            # This must be a 401 or 403 to work with nginx's auth_check
            raise ForbiddenError(
                'Method {} is not permitted on this {}.'.format(
                    method, uri,
                )
            )

    @rest_decorators.marshal_with(ResourceID)
    def get(self, **_):
        """
        Verify that the user is allowed to access requested resource.

        The user cannot access tenants except the one in the request's header.
        """
        uri = request.headers['X-Original-Uri'].strip('/')
        method = request.headers['X-Original-Method']
        if uri.startswith('api/'):
            resource = uri.split('/')[2]

            if resource.startswith('audit'):
                self._verify_audit(uri, method)
        self._verify_tenant(uri)

        # verified successfully
        return {}


def _validate_allowed_substitutions(param_name, param_value, allowed):
    if param_value is None:
        return
    f = string.Formatter()
    invalid = []
    for _, field, _, _ in f.parse(param_value):
        if field is None:
            # This will occur at the end of a string unless the string ends at
            # the end of a field
            continue
        if field not in allowed:
            invalid.append(field)
    if invalid:
        raise pydantic.ValidationError(
            '{candidate_name} has invalid parameters.\n'
            'Invalid parameters found: {invalid}.\n'
            'Allowed: {allowed}'.format(
                candidate_name=param_name,
                invalid=', '.join(invalid),
                allowed=', '.join(allowed),
            )
        )


class _LDAPConfigArgs(pydantic.BaseModel):
    ldap_server: str
    ldap_domain: str
    ldap_username: Optional[str] = None
    ldap_password: Optional[str] = None
    ldap_is_active_directory: Optional[bool] = False
    ldap_dn_extra: Optional[str] = None
    ldap_ca_cert: Optional[str] = None
    ldap_nested_levels: Optional[int] = None
    ldap_bind_format: Optional[str] = None
    ldap_base_dn: Optional[str] = None
    ldap_group_dn: Optional[str] = None
    ldap_group_member_filter: Optional[str] = None
    ldap_user_filter: Optional[str] = None
    ldap_attribute_email: Optional[str] = None
    ldap_attribute_first_name: Optional[str] = None
    ldap_attribute_last_name: Optional[str] = None
    ldap_attribute_uid: Optional[str] = None
    ldap_attribute_group_membership: Optional[str] = None

    @pydantic.validator('ldap_bind_format')
    def ldap_bind_format_substitutions(cls, v):
        _validate_allowed_substitutions('ldap_bind_format', v, allowed=[
            'username', 'domain', 'base_dn', 'domain_dn', 'group_dn',
        ])

    @pydantic.validator('ldap_group_dn')
    def ldap_group_dn_substitutions(cls, v):
        _validate_allowed_substitutions(
            'ldap_group_dn', v,
            allowed=['base_dn', 'domain_dn'],
        )

    @pydantic.validator('ldap_group_member_filter')
    def ldap_group_member_filter_substitutions(cls, v):
        _validate_allowed_substitutions(
            'ldap_group_member_filter', v,
            allowed=['object_dn'],
        )

    @pydantic.validator('ldap_user_filter')
    def ldap_user_filter_substitutions(cls, v):
        _validate_allowed_substitutions(
            'ldap_user_filter', v,
            allowed=['username', 'base_dn', 'domain_dn', 'group_dn'],
        )


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
        ldap_config = _LDAPConfigArgs.parse_obj(request.json).dict()
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
