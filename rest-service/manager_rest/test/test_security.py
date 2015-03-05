from base_test import BaseServerTestCase
from manager_rest import config  # , resources
from itsdangerous import base64_encode
from flask import Flask
import yaml
import os
from flask_securest.rest_security import SecuREST, utils

SECUREST_SECRET_KEY = 'SECUREST_SECRET_KEY'
SECUREST_USERSTORE_DRIVER = 'SECUREST_USERSTORE_DRIVER'
SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE = \
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE'

# TODO is this required?
# PERMANENT_SESSION_LIFETIME = datetime.timedelta(seconds=30)
default_config = {
    'SECUREST_SECRET_KEY': 'SECUREST_SECRET_KEY',
    'SECUREST_USERSTORE_DRIVER': 'flask_securest.userstores.file:'
                                 'FileUserstore',
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE': 'username',
    }


class SecurityTestCase(BaseServerTestCase):

    def test_secured_resource(self):
        app = Flask(__name__)
        init_secure_app(app)
        # api = Api(app)
        # resources.setup_resources(api)

        creds = 'user1:pass1'
        encoded_creds = base64_encode(creds)
        # encoded_creds = urllib.urlencode(creds)
        auth_header = {'Authorization': encoded_creds}
        response = self.get('/status', headers=auth_header)
        print '***** response from Get "/status": {0} {1}'\
            .format(response.status_code, response.data)


def init_secure_app(app):
    cfy_config = config.instance()
    # TODO raise better exceptions
    if not hasattr(cfy_config, 'securest_secret_key') or \
            cfy_config.securest_secret_key is None:
        raise Exception('securest_secret_key not set')

    if not hasattr(cfy_config, 'securest_authentication_methods') or \
            cfy_config.securest_authentication_methods is None:
        raise Exception('securest_authentication_methods not set')

    if not hasattr(cfy_config, 'securest_userstore_driver') or \
            cfy_config.securest_userstore_driver is None:
        raise Exception('securest_userstore_driver not set')

    if not hasattr(cfy_config, 'securest_userstore_identifier_attribute') or \
            cfy_config.securest_userstore_identifier_attribute is None:
        raise Exception('securest_userstore_identifier_attribute not set')

    app.config[SECUREST_SECRET_KEY] = cfy_config.securest_secret_key
    app.config[SECUREST_USERSTORE_DRIVER] = \
        cfy_config.securest_userstore_driver
    app.config[SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE] = \
        cfy_config.securest_userstore_identifier_attribute

    secure_app = SecuREST(app)

    register_authentication_methods(secure_app,
                                    cfy_config.securest_authentication_methods)


def register_authentication_methods(secure_app, authentication_providers):
    # Note: the order of registration is important here
    for auth_method_path in authentication_providers:
        try:
            print '***** getting instance of: ', auth_method_path
            auth_provider = utils.get_class_instance(auth_method_path)
            print '----- Got class instance'

            '''
            if not hasattr(auth_provider, AUTHENTICATE_METHOD_NAME):
                # TODO use a more specific exception type
                raise Exception('authentication provider "{0}" does not'
                                ' implement {1}'.format(
                                    utils.get_runtime_class_fqn(auth_provider),
                                    AUTHENTICATE_METHOD_NAME))
            '''
            secure_app.authentication_provider(auth_provider)
        except Exception as e:
            print('Failed to register authentication method: ',
                  authentication_providers, e)
            raise e


# if 'MANAGER_REST_CONFIG_PATH' in os.environ:
config_file_path = os.path.dirname(__file__) + '/config.yaml'
if True:
    print '***** using {0} as MANAGER_REST_CONFIG_PATH'\
        .format(config_file_path)
    # with open(os.environ['MANAGER_REST_CONFIG_PATH']) as f:
    with open(config_file_path) as f:
        yaml_conf = yaml.load(f.read())
    obj_conf = config.instance()
    if 'file_server_root' in yaml_conf:
        obj_conf.file_server_root = yaml_conf['file_server_root']
    if 'file_server_base_uri' in yaml_conf:
        obj_conf.file_server_base_uri = yaml_conf['file_server_base_uri']
    if 'file_server_blueprints_folder' in yaml_conf:
        obj_conf.file_server_blueprints_folder = \
            yaml_conf['file_server_blueprints_folder']
    if 'file_server_uploaded_blueprints_folder' in yaml_conf:
        obj_conf.file_server_uploaded_blueprints_folder = \
            yaml_conf['file_server_uploaded_blueprints_folder']
    if 'file_server_resources_uri' in yaml_conf:
        obj_conf.file_server_resources_uri = \
            yaml_conf['file_server_resources_uri']
    if 'rest_service_log_path' in yaml_conf:
        obj_conf.rest_service_log_path = \
            yaml_conf['rest_service_log_path']
    if 'securest_secret_key' in yaml_conf:
        obj_conf.securest_secret_key = yaml_conf['securest_secret_key']
    if 'securest_authentication_methods' in yaml_conf:
        obj_conf.securest_authentication_methods = \
            yaml_conf['securest_authentication_methods']
    if 'securest_userstore_driver' in yaml_conf:
        obj_conf.securest_userstore_driver = \
            yaml_conf['securest_userstore_driver']
    if 'securest_userstore_identifier_attribute' in yaml_conf:
        obj_conf.securest_userstore_identifier_attribute = \
            yaml_conf['securest_userstore_identifier_attribute']
        # TODO Add security related config, probably hierarchically
        # else:
        #     print '***** no MANAGER_REST_CONFIG_PATH in os.environ'
