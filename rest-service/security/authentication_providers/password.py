from base_authentication_provider import BaseAuthenticationProvider


class PasswordAuthenticator(BaseAuthenticationProvider):

    @staticmethod
    def authenticate(user_id, password, datastore, pwd_context):

        PasswordAuthenticator._validate_input(user_id, password, datastore, pwd_context)

        # TODO should use find or get here?
        user = datastore.get_user(user_id)
        # user = User.query.filter_by(api_key=api_key).first()

        # validate...
        if not user:
            # self.email.errors.append(get_message('USER_DOES_NOT_EXIST')[0])
            print '***** error: USER_DOES_NOT_EXIST'
            # Always throw the same general failure to avoid revealing account information
            raise Exception('Authentication failed')
        if not user.password:
            # self.password.errors.append(get_message('PASSWORD_NOT_SET')[0])
            print '***** error: PASSWORD_NOT_SET'
            raise Exception('Authentication failed')
            # TODO maybe use verify_and_update()?
        if not pwd_context.verify(password, getattr(user, 'password')):
            # self.password.errors.append(get_message('INVALID_PASSWORD')[0])
            print '***** error: INVALID_PASSWORD'
            raise Exception('Authentication failed')
        if not user.is_active():
            # self.email.errors.append(get_message('DISABLED_ACCOUNT')[0])
            raise Exception('Authentication failed')

        return user

    @staticmethod
    def _validate_input(user_id, password, datastore, pwd_context):
        if not user_id:
            raise Exception('user_id is missing or empty')

        if not password:
            raise Exception('password is missing or empty')

        if not datastore:
            raise Exception('datastore is missing or empty')

        if not pwd_context:
            raise Exception('pwd_context is missing or empty')

        if not isinstance(user_id, basestring):
            raise Exception('user_id is not a string')

        if not isinstance(password, basestring):
            raise Exception('password is not a string')
