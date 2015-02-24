import abc


class AbstractAuthenticationProvider(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of authentication providers.
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def authenticate(self, user, auth_info):
        raise NotImplementedError
