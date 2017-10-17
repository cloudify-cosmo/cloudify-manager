from manager_rest.storage import idencoder

import click

import os


@click.command()
@click.option('--user_id', help='User ID to encode', type=int, required=True)
def get_encoded_user_id(user_id):
    print(idencoder.get_encoder().encode(user_id))


if __name__ == '__main__':
    config_env_var = 'MANAGER_REST_SECURITY_CONFIG_PATH'
    if config_env_var not in os.environ:
        os.environ[config_env_var] = '/opt/manager/rest-security.conf'

    get_encoded_user_id()
