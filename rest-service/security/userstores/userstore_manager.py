from security.utils import get_class

GET_USER_METHOD = 'get_user'


# TODO make singleton (using meta-class?
# TODO or through a decorator setting a context?)
# TODO or maybe this shouldn't be a class at all? just static utility methods?
class UserstoreManager():

    def __init__(self):
        # TODO: read from config file
        self.userstore_driver_path = \
            'security.userstores.file:FileUserstore'
        # 'security.userstores.mongo:MongoUserstore'

    def get_userstore_driver(self, *args, **kwargs):
        # TODO instantiate only if not done already, keep instance in globals?
        # TODO verify the class has the method 'get_user()'

        """Returns a class from a string formatted as module:class"""
        #TODO use a more specific exception type and messages

        userstore_class = get_class(self.userstore_driver_path)

        # TODO use ABC?
        # validate userstore class
        if not hasattr(userstore_class, GET_USER_METHOD):
            raise Exception('userstore class "{0}" does not contain the'
                            ' required method "{1}"'
                            .format(userstore_class.__name__, GET_USER_METHOD))

        return userstore_class(*args, **kwargs)

        '''
        if not isinstance(userstore_driver, BaseUserstore):
            raise Exception('userstore driver class "{0}" is not an instance '
                            'of "{1}"'.format(driver_class_str, BaseUserstore))

        '''