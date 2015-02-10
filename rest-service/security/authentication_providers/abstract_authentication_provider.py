import abc


class AbstractAuthenticationProvider(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of authentication providers.
    """

    __metaclass__ = abc.ABCMeta

    @staticmethod
    @abc.abstractmethod
    def authenticate(user, auth_info):
        raise NotImplementedError

    @staticmethod
    def get_identifier_from_auth_info(auth_info):
        return auth_info.user_id