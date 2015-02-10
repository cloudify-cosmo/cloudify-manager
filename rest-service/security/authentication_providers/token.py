from base_authentication_provider import BaseAuthenticationProvider


class TokenAuthenticator(BaseAuthenticationProvider):

    @staticmethod
    def authenticate(user, auth_info):
        pass

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        pass