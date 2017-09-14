
from os import environ
from base64 import urlsafe_b64encode

from ..constants import DEFAULT_TENANT_NAME


USERNAME_ENVAR = 'CFY_ADMIN_USERNAME'
PASSWORD_ENVAR = 'CFY_ADMIN_PASSWORD'


def get_auth_header():
    username = environ.get(USERNAME_ENVAR)
    password = environ.get(PASSWORD_ENVAR)
    if not username or not password:
        raise Exception('To run this command you must supply credentials via '
                        'the environment variables: {0}, {1}'.format(
                            USERNAME_ENVAR, PASSWORD_ENVAR))
    credentials = '{0}:{1}'.format(username, password)
    encoded_credentials = urlsafe_b64encode(credentials)
    header = {
        'Authorization': 'Basic ' + encoded_credentials,
        'Tenant': DEFAULT_TENANT_NAME
    }
    return header
