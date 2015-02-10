from abstract_authentication_provider import AbstractAuthenticationProvider


class LdapAuthenticator(AbstractAuthenticationProvider):

    @staticmethod
    def authenticate(user, auth_info):
        pass

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        pass