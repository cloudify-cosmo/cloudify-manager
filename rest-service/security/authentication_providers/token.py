from abstract_authentication_provider import AbstractAuthenticationProvider
from flask import globals as flask_globals
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


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
            data = serializer.loads(token)
        except SignatureExpired:
            print '***** exception SignatureExpired, returning None'
            return None  # valid token, but expired
        except BadSignature:
            print '***** exception BadSignature, returning None'
            return None  # invalid token

        print '***** token loaded successfully, user email from token is: ', data['email']
        user = userstore.find_user(email=data['email'])
        # for the SQLAlchemy model: user = User.query.get(data['id'])
        return user

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        pass