from abstract_authentication_provider import AbstractAuthenticationProvider


class TokenAuthenticator(AbstractAuthenticationProvider):

    @staticmethod
    def authenticate(user, auth_info):
        print '***** verifying auth token: ', token
        print '***** app config: '
        for item in app.config:
            print '***** app config item: {0} has value: {1}'.format(item, app.config[item])

        print '***** initializing serializer with secret key: ', app.config['SECRET_KEY']
        s = Serializer(app.config['SECRET_KEY'])
        print '***** serializer: ', s
        try:
            print '***** attempting to deserialize the token'
            data = s.loads(token)
        except SignatureExpired:
            print '***** exception SignatureExpired, returning None'
            return None  # valid token, but expired
        except BadSignature:
            print '***** exception BadSignature, returning None'
            return None  # invalid token

        print '***** token loaded successfully, user email from token is: ', data['email']
        user = user_datastore.find_user(email=data['email'])
        # for the SQLAlchemy model: user = User.query.get(data['id'])
        return user

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        pass