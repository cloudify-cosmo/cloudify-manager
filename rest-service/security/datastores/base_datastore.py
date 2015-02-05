class BaseDatastore(object):
    """
    This class is abstract and should be inherited by concrete
    implementations of data stores.
    """
    def get_user(self, identifier):
        raise NotImplementedError(
            "'get_user' must be implemented by the selected datastore")