from manager_rest import config
from manager_rest.storage import idencoder

import argparse
import os


def get_encoded_user_id(user_id):
    print(idencoder.get_encoder().encode(user_id))


if __name__ == '__main__':
    config_env_var = 'MANAGER_REST_SECURITY_CONFIG_PATH'
    if config_env_var not in os.environ:
        os.environ[config_env_var] = '/opt/manager/rest-security.conf'
    config.instance.load_configuration(from_db=False)

    # Not using click because the rest service doesn't have click in community
    parser = argparse.ArgumentParser(
        description='Get encoded form of user ID for API tokens.',
    )
    parser.add_argument(
        '-u', '--user_id',
        help='User ID to encode',
        type=int,
        required=True,
    )

    args = parser.parse_args()

    get_encoded_user_id(args.user_id)
