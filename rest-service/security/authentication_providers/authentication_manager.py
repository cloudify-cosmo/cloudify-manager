from security.utils import get_class

AUTHENTICATE_METHOD = 'authenticate'


# TODO make singleton (using meta-class?
# TODO or through a decorator setting a context?)
# TODO or maybe this shouldn't be a class at all? just static utility methods?
class AuthenticationManager():

    def __init__(self, current_app):
        # TODO: read from config file,
        # TODO: Verify the list is unique (a set) and maintains order
        self.authentication_methods = current_app.config.get('AUTHENTICATION_METHODS', [])
        if not self.authentication_methods:
            raise Exception('Authentication methods not set')

        # self.provider_path = \
        #     'security.authentication_providers.password:PasswordAuthenticator'

    def authenticate(self, auth_info, userstore, *args, **kwargs):

        user = None

        for provider_path in self.authentication_methods:
            try:
                print '***** attempting to authenticate using: ', provider_path
                provider = self.get_authentication_provider(provider_path, *args, **kwargs)
                user = provider.authenticate(auth_info, userstore)
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

        authentication_class = get_class(provider_path)

        # TODO instantiate only if not done already, keep instance in globals?
        # TODO use a more specific exception type and messages
        # validate authentication provider
        if not hasattr(authentication_class, AUTHENTICATE_METHOD):
            raise Exception('authentication class "{0}" does not contain the'
                            ' required method "{1}"'
                            .format(authentication_class.__name__,
                                    AUTHENTICATE_METHOD))

        return authentication_class(*args, **kwargs)