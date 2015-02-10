class BaseAuthenticationProvider(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of authentication providers.
    """

    @staticmethod
    def authenticate(user, auth_info):
        raise NotImplementedError

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        raise NotImplementedError