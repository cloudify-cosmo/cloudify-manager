
import subprocess

from .. import acfy, exceptions
from manager_rest.config import instance
from manager_rest.manager_exceptions import UnauthorizedError

try:
    from cloudify_premium.authentication.ldap_authentication \
        import LdapAuthentication
except ImportError:
    LdapAuthentication = None


@acfy.group(name='ldap')
def ldap():
    if LdapAuthentication is None:
        raise exceptions.CloudifyACliError('This feature is not available')


@ldap.command(name='set')
@acfy.options.ldap_server()
@acfy.options.ldap_username()
@acfy.options.ldap_password()
@acfy.options.ldap_domain()
@acfy.options.ldap_is_active_directory()
@acfy.options.ldap_dn_extra()
def set_ldap(**ldap_config):
    for key, value in ldap_config.items():
        setattr(instance, key, value)

    auth = LdapAuthentication()
    auth.configure_ldap()
    try:
        auth.authenticate_user(ldap_config.get('ldap_username'),
                               ldap_config.get('ldap_password'))
    except UnauthorizedError:
        raise exceptions.CloudifyACliError(
            'Failed setting LDAP authenticator: Invalid parameters '
            'provided.')
    subprocess.check_call(['systemctl', 'restart', 'cloudify-restservice'])
