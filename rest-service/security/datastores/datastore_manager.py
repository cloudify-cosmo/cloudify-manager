import importlib

GET_USER_METHOD = 'get_user'


@staticmethod
def instantiate_class(class_path, *args, **kwargs):
    if not class_path:
        raise Exception('class path is missing or empty')

    if not isinstance(class_path, basestring):
        raise Exception('class path is not a string')

    class_path = class_path.strip()
    if not ':' in class_path or class_path.count(':') > 1:
        raise Exception('Invalid class path, expected format: '
                        'module:class')

    class_path_parts = class_path.split(':')
    class_module_str = class_path_parts[0].strip()
    class_name = class_path_parts[1].strip()

    if not class_module_str or not class_name:
        raise Exception('Invalid class path, expected format: '
                        'module:class')

    module = importlib.import_module(class_module_str)
    if not hasattr(module, class_name):
        raise Exception('module "{0}", does not contain class "{1}"'
            .format(class_module_str, class_name))

    clazz = getattr(module, class_name)
    return clazz(*args, **kwargs)


# TODO make singleton (using meta-class?
# TODO or through a decorator setting a context?)
# TODO or maybe this shouldn't be a class at all? just static utility methods?
class DatastoreManager():

    def __init__(self):
        # TODO: read from config file
        self.datastore_driver_path = \
            'security.datastores.mongo:MongoDatastore'
            # 'security.datastores.file_driver:FileDatastore'

    def get_datastore_driver(self, *args, **kwargs):
        # TODO instantiate only if not done already, keep instance in globals?
        # TODO verify the class has the method 'get_user()'

        """Returns a class from a string formatted as module:class"""
        #TODO use a more specific exception type and messages

        return instantiate_class(self.datastore_driver_path, *args, **kwargs)
        '''
        # TODO use ABC?
        # validate datastore driver
        if not hasattr(driver_class, GET_USER_METHOD):
            raise Exception('datastore class "{0}" does not contain the'
                            ' required method "{1}"'
                            .format(driver_class_str, GET_USER_METHOD))
        '''

        '''
        if not isinstance(datastore_driver, BaseDatastore):
            raise Exception('datastore driver class "{0}" is not an instance '
                            'of "{1}"'.format(driver_class_str, BaseDatastore))

        '''