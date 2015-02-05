class BaseAuthenticationProvider(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of authentication providers.
    """
    def authenticate(self, user_id=None, password=None):
        raise NotImplementedError