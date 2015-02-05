import importlib

GET_USER_METHOD = 'get_user'


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

        if not self.datastore_driver_path:
            raise Exception('datastore driver path is missing or empty')

        if not isinstance(self.datastore_driver_path, basestring):
            raise Exception('datastore driver path is not a string')

        driver_path = self.datastore_driver_path.strip()
        if not ':' in driver_path or driver_path.count(':') > 1:
            raise Exception('Invalid datastore driver path, expected format: '
                            'module:class')

        driver_path_parts = driver_path.split(':')
        driver_module_str = driver_path_parts[0].strip()
        driver_class_str = driver_path_parts[1].strip()

        if not driver_module_str or not driver_class_str:
            raise Exception('Invalid datastore driver path, expected format: '
                            'module:class')

        driver_module = importlib.import_module(driver_module_str)
        if not hasattr(driver_module, driver_class_str):
            raise Exception('datastore driver module "{0}", does not contain'
                            ' class "{1}"'.format(driver_module_str,
                                                driver_class_str))

        driver_class = getattr(driver_module, driver_class_str)
        datastore_driver = driver_class(*args, **kwargs)

        # TODO use ABC?
        # validate datastore driver
        if not hasattr(driver_class, GET_USER_METHOD):
            raise Exception('datastore class "{0}" does not contain the'
                            ' required method "{1}"'
                            .format(driver_class_str, GET_USER_METHOD))

        '''
        if not isinstance(datastore_driver, BaseDatastore):
            raise Exception('datastore driver class "{0}" is not an instance '
                            'of "{1}"'.format(driver_class_str, BaseDatastore))

        '''

        return datastore_driver