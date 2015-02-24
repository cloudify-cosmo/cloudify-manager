from flask import globals as flask_globals
from itsdangerous import \
    URLSafeTimedSerializer, SignatureExpired, BadSignature

from flask_securest.authentication_providers.abstract_authentication_provider\
    import AbstractAuthenticationProvider


class TokenAuthenticator(AbstractAuthenticationProvider):

    @staticmethod
    def authenticate(auth_info, userstore):
        token = auth_info.token
        current_app = flask_globals.current_app
        print '***** verifying auth token: ', token

        if not token:
            raise Exception('token is missing or empty')

        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

        try:
            print '***** attempting to deserialize the token'
            open_token = serializer.loads(token)
        except SignatureExpired:
            print '***** exception SignatureExpired, returning None'
            return None  # valid token, but expired
        except BadSignature:
            print '***** exception BadSignature, returning None'
            return None  # invalid token

        print '***** token loaded successfully, user email from token is: ', \
            open_token['email']
        # TODO should the identity field in the token be configurable?
        user_id = open_token['user_id']
        print '***** getting user from userstore: ', userstore
        user = userstore.get_user(user_id)
        # user = userstore.find_user(email=data['email'])
        # for the SQLAlchemy model: user = User.query.get(data['id'])
        return user
