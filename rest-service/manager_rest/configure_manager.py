import argparse
import os
import random
import string
import yaml

from manager_rest import config
from manager_rest.amqp_manager import AMQPManager
from manager_rest.storage import storage_utils
from manager_rest.flask_utils import setup_flask_app


def _add_default_user_and_tenant(amqp_manager, script_config):
    storage_utils.create_default_user_tenant_and_roles(
        admin_username=script_config['admin_username'],
        admin_password=script_config['admin_password'],
        amqp_manager=amqp_manager
    )


def _generate_password(length=12):
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    password = ''.join(random.choice(chars) for _ in range(length))

    return password


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Create admin user in DB'
    )
    parser.add_argument(
        '-c',
        '--config_file_path',
        help='Path to a config file containing info needed by this script',
        required=False,
        default=os.environ.get('CONFIG_FILE_PATH'),
    )
    args = parser.parse_args()

    app = setup_flask_app()
    config.instance.load_configuration()
    user_config = yaml.safe_load(
        open(args.config_file_path)
    )

    if not user_config['manager']['security']['admin_password']:
        user_config['manager']['security']['admin_password'] = \
            _generate_password()

    user_credentials = {
        'admin_username': user_config['manager']['security']['admin_username'],
        'admin_password': user_config['manager']['security']['admin_password'],
    }
    amqp_manager = None
    if config.instance.amqp_management_host:
        amqp_manager = AMQPManager(
            host=config.instance.amqp_management_host,
            username=config.instance.amqp_username,
            password=config.instance.amqp_password,
            cadata=config.instance.amqp_ca
        )

    _add_default_user_and_tenant(amqp_manager, user_credentials)
