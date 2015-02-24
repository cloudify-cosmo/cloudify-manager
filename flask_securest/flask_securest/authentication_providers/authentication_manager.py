from flask.globals import current_app

from flask_securest import utils
from flask_securest.authentication_providers.abstract_authentication_provider \
    import AbstractAuthenticationProvider


# TODO or maybe this shouldn't be a class at all? just static utility methods?
class AuthenticationManager():

    def __init__(self, app):
        # TODO: read from config file,
        # TODO: Verify the list is unique (a set) and maintains order
        self.authentication_methods = \
            app.config.get('SECUREST_AUTHENTICATION_METHODS', [])
        if not self.authentication_methods:
            raise Exception('Authentication methods not set')

    def authenticate(self, auth_info, *args, **kwargs):
        user = None
        for provider_path in self.authentication_methods:
            try:
                print '***** attempting to authenticate using: ', provider_path
                provider = self.get_authentication_provider(
                    provider_path, *args, **kwargs)
                print '***** userstore is: ', current_app.securest_userstore
                user = provider.authenticate(auth_info,
                                             current_app.securest_userstore)
                break
            except Exception as e:
                #  TODO use the caught exception?
                print '***** caught authentication exception: ', e.message
                continue  # try the next authentication method until successful

        if not user:
            raise Exception('Unauthorized')

        return user

    @staticmethod
    def get_authentication_provider(provider_path, *args, **kwargs):

        authentication_provider = utils.get_class_instance(provider_path,
                                                           *args, **kwargs)

        # TODO instantiate only if not done already, keep instance in globals?
        # TODO use a more specific exception type and messages
        # validate authentication provider
        if not isinstance(authentication_provider,
                          AbstractAuthenticationProvider):
            raise Exception('authentication class "{0}" must extend {1}'
                            .format(utils.get_runtime_class_fqn
                                    (authentication_provider),
                                    utils.get_runtime_class_fqn
                                    (AbstractAuthenticationProvider)))

        return authentication_provider
