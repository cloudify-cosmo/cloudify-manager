import os
import argparse

from manager_rest.storage import models
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import get_storage_manager


config_env_var = 'MANAGER_REST_SECURITY_CONFIG_PATH'
os.environ[config_env_var] = '/opt/manager/rest-security.conf'
config_env_var = 'MANAGER_REST_CONFIG_PATH'
os.environ[config_env_var] = '/opt/manager/cloudify-rest.conf'


def _write_token_to_file(tempdir, token):
    file_name = os.path.join(tempdir, 'new_token')
    with open(file_name, 'w') as f:
        f.write(token)


def main(tempdir):
    """
    Create a Flask app, and using the updated security config file get a new
    REST token. Then write the new token to a file under the snapshot`s
    tmp dir.
    :param tempdir: The temp dir used by `restore snapshot` wf.
    """
    setup_flask_app()
    sm = get_storage_manager()
    admin_user = sm.get(models.User, 0)
    token = admin_user.get_auth_token(description='Snapshot restore')
    _write_token_to_file(tempdir, token)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Get new REST token using updated security config file.'
    )
    parser.add_argument('tempdir', help='Snapshot restore temp dir.')
    args = parser.parse_args()

    tempdir = args.tempdir
    main(tempdir)
