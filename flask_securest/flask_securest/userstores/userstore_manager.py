from flask.ext.securest.userstores.abstract_userstore import AbstractUserstore
from flask_securest import utils


GET_USER_METHOD = 'get_user'


# TODO make singleton (using meta-class?
# TODO or through a decorator setting a context?)
# TODO or maybe this shouldn't be a class at all? just static utility methods?
class UserstoreManager():

    def __init__(self, app):
        self.userstore_driver_path = \
            app.config.get('SECUREST_USERSTORE_DRIVER')
        self.userstore_identifier_attribute = \
            app.config.get('SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE')

        if not self.userstore_driver_path:
            raise Exception('Userstore driver path not set')

        if not self.userstore_identifier_attribute:
            raise Exception('Userstore identifier attribute not set')

    def get_userstore_driver(self, *args, **kwargs):
        # TODO instantiate only if not done already, keep instance in globals?
        # TODO verify the class has the method 'get_user()'

        """Returns a class from a string formatted as module:class"""
        # TODO use a more specific exception type and messages
        userstore_driver = \
            utils.get_class_instance(self.userstore_driver_path,
                                     *args, **kwargs)

        # TODO instantiate only if not done already, keep instance in globals?
        # TODO use a more specific exception type and messages
        # validate authentication provider
        if not isinstance(userstore_driver, AbstractUserstore):
            raise Exception('userstore class "{0}" must inherit {1}'
                            .format(utils.get_runtime_class_fqn
                                    (userstore_driver),
                                    utils.get_runtime_class_fqn
                                    (AbstractUserstore)))

        userstore_driver.identifying_attribute = \
            self.userstore_identifier_attribute
        return userstore_driver
