from passlib.context import CryptContext
from abstract_authentication_provider import AbstractAuthenticationProvider


DEFAULT_PASSWORD_HASH = 'plaintext'
DEFAULT_PASSWORD_SCHEMES = [
    'bcrypt',
    'des_crypt',
    'pbkdf2_sha256',
    'pbkdf2_sha512',
    'sha256_crypt',
    'sha512_crypt',
    'plaintext'
    ]
DEFAULT_DEPRECATED_PASSWORD_SCHEMES = ['auto']


class PasswordAuthenticator(AbstractAuthenticationProvider):

    def __init__(self):
        print '----- INITING PasswordAuthenticator'
        self.crypt_ctx = None

    def init(self, app):
        self.crypt_ctx = _get_crypt_context(app)

    def authenticate(self, auth_info, userstore):
        print '***** starting password authentication, user and password: ', \
            auth_info.user_id, auth_info.password
        # TODO the auth_info identity field be configurable?
        user_id = auth_info.user_id
        print '***** getting user from userstore: ', userstore
        user = userstore.get_user(user_id)

        if not user:
            # self.email.errors.append(get_message('USER_DOES_NOT_EXIST')[0])
            # Always throw the same general failure to avoid revealing
            # information about the account
            print '***** user not found'
            raise Exception('Unauthorized')
        if not user.password:
            # self.password.errors.append(get_message('PASSWORD_NOT_SET')[0])
            print '***** user has no password'
            raise Exception('Unauthorized')
            # TODO maybe use verify_and_update()?

        # TODO the 'password' field in the user object be configurable?
        if not self.crypt_ctx.verify(auth_info.password, user.password):
            # self.password.errors.append(get_message('INVALID_PASSWORD')[0])
            print '***** password verification failed'
            raise Exception('Unauthorized')
        if not user.is_active():
            # self.email.errors.append(get_message('DISABLED_ACCOUNT')[0])
            print '***** user is not active'
            raise Exception('Unauthorized')

        return user


def _get_crypt_context(app):
    pw_hash = app.config.get('PASSWORD_HASH', DEFAULT_PASSWORD_HASH)
    schemes = app.config.get('PASSWORD_SCHEMES', DEFAULT_PASSWORD_SCHEMES)
    deprecated = app.config.get('DEPRECATED_PASSWORD_SCHEMES',
                                DEFAULT_DEPRECATED_PASSWORD_SCHEMES)
    if pw_hash not in schemes:
        allowed = (', '.join(schemes[:-1]) + ' and ' + schemes[-1])
        raise ValueError("Invalid hash scheme {0}. Allowed values are {1}"
                         .format(pw_hash, allowed))
    try:
        crypt_ctx = CryptContext(schemes=schemes,
                                 default=pw_hash,
                                 deprecated=deprecated)
    except Exception as e:
        print 'Failed to initialize password crypt context: ', e
        raise e

    return crypt_ctx
