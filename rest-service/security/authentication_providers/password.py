from abstract_authentication_provider import AbstractAuthenticationProvider
from passlib.context import CryptContext
from flask.globals import current_app


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


def _get_crypt_context():
    config = current_app.config
    pw_hash = config.get('PASSWORD_HASH', DEFAULT_PASSWORD_HASH)
    schemes = config.get('PASSWORD_SCHEMES', DEFAULT_PASSWORD_SCHEMES)
    deprecated = config.get('DEPRECATED_PASSWORD_SCHEMES',
                            DEFAULT_DEPRECATED_PASSWORD_SCHEMES)
    if pw_hash not in schemes:
        allowed = (', '.join(schemes[:-1]) + ' and ' + schemes[-1])
        raise ValueError("Invalid hash scheme %r. Allowed values are %s" % (pw_hash, allowed))
    try:
        cc = CryptContext(schemes=schemes, default=pw_hash, deprecated=deprecated)
    except Exception as e:
        print 'Failed to initialize password crypt context: ', e
    return cc


class PasswordAuthenticator(AbstractAuthenticationProvider):

    @staticmethod
    def authenticate(auth_info, datastore):

        user_id = auth_info.user_id     # TODO the identity field should be configurable?
        user = datastore.get_user(user_id)

        if not user:
            # self.email.errors.append(get_message('USER_DOES_NOT_EXIST')[0])
            # Always throw the same general failure to avoid revealing account information
            raise Exception('Unauthorized')
        if not user.password:
            # self.password.errors.append(get_message('PASSWORD_NOT_SET')[0])
            raise Exception('Unauthorized')
            # TODO maybe use verify_and_update()?
        # TODO break this line:
        if not _get_crypt_context().verify(auth_info.password, getattr(user, 'password')):
            # self.password.errors.append(get_message('INVALID_PASSWORD')[0])
            raise Exception('Unauthorized')
        if not user.is_active():
            # self.email.errors.append(get_message('DISABLED_ACCOUNT')[0])
            raise Exception('Unauthorized')

        return user