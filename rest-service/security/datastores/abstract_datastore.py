import abc


class AbstractDatastore(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of data stores.
    The only mandatory implementation is of get_user, which is expected
    to return an object that inherits security.models.UserModel
    """
    @staticmethod
    @abc.abstractmethod
    def get_user(self, identifier):
        raise NotImplementedError(
            "'get_user' must be implemented by the selected datastore implementation")