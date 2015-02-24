from flask_securest.authentication_providers.abstract_authentication_provider \
    import AbstractAuthenticationProvider


class SqlAuthenticator(AbstractAuthenticationProvider):

    @staticmethod
    def authenticate(user, auth_info):
        pass
