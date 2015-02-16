import importlib

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

    def authenticate(self, auth_info, datastore):

        user = None

        for provider_path in self.authentication_methods:
            try:
                provider = self.get_authentication_provider(provider_path)
                user = provider.authenticate(auth_info, datastore)
                break
            except Exception as e:
                #  TODO use the caught exception?
                continue  # try the next authentication method until successful

        if not user:
            raise Exception('Unauthorized')

        return user

    @staticmethod
    def get_authentication_provider(provider_path):
        # TODO instantiate only if not done already, keep instance in globals?

        """Returns a class from a string formatted as module:class"""
        #TODO use a more specific exception type and messages

        if not provider_path:
            raise Exception('authentication provider path is missing or empty')

        if not isinstance(provider_path, basestring):
            raise Exception('authentication provider is not a string')

        provider_path = provider_path.strip()
        if not ':' in provider_path or provider_path.count(':') > 1:
            raise Exception('Invalid authentication provider path, expected '
                            'format: module:class')

        provider_path_parts = provider_path.split(':')
        auth_provider_module_str = provider_path_parts[0].strip()
        auth_provider_class_str = provider_path_parts[1].strip()

        if not auth_provider_module_str or not auth_provider_class_str:
            raise Exception('Invalid authentication provider path, expected'
                            ' format: module:class')

        authentication_module = importlib.import_module(auth_provider_module_str)
        if not hasattr(authentication_module, auth_provider_class_str):
            raise Exception('authentication provider module "{0}", does not'
                            ' contain class "{1}"'
                            .format(auth_provider_module_str,
                                    auth_provider_class_str))

        authentication_class = getattr(authentication_module, auth_provider_class_str)
        authentication_provider = authentication_class(*args, **kwargs)

        # validate authentication provider
        if not hasattr(authentication_class, AUTHENTICATE_METHOD):
            raise Exception('authentication class "{0}" does not contain the'
                            ' required method "{1}"'
                            .format(auth_provider_class_str,
                                    AUTHENTICATE_METHOD))

        return authentication_provider