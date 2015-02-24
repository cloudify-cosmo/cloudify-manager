import abc


class AbstractUserstore(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of user stores.
    The only mandatory implementation is of get_user, which is expected
    to return an object that inherits security.models.UserModel
    """

    __metaclass__ = abc.ABCMeta

    @property
    def identifying_attribute(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_user(self, identifier):
        raise NotImplementedError
