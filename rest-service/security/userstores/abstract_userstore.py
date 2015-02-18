import abc


class AbstractUserstore(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of user stores.
    The only mandatory implementation is of get_user, which is expected
    to return an object that inherits security.models.UserModel
    """

    __metaclass__ = abc.ABCMeta

    @staticmethod
    @property
    def identifying_attribute():
        return 'username'

    # @staticmethod
    @abc.abstractmethod
    def get_user(self, identifier):
        raise NotImplementedError