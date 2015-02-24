import abc


class AbstractAuthenticationProvider(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of user stores.
    The only mandatory implementation is of get_user, which is expected
    to return an object that inherits security.models.UserModel
    """

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def init(self, app):
        raise NotImplementedError

    @abc.abstractmethod
    def authenticate(self, identifier):
        raise NotImplementedError
