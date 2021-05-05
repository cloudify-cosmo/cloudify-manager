import json

import argparse

from manager_rest import config
from manager_rest.storage import db, models
from manager_rest.flask_utils import setup_flask_app

AUTH_TOKEN_LOCATION = '/opt/mgmtworker/work/admin_token'


def get_password_hash():
    app = setup_flask_app()
    return db.session.query(models.User).first().password


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config')
    args = parser.parse_args()
    with open(args.config) as f:
        script_config = json.load(f)
    for namespace, path in script_config['config'].items():
        config.instance.load_from_file(path, namespace=namespace)
    config.instance.load_configuration()

    script_config['password_hash'] = get_password_hash()
    with open(AUTH_TOKEN_LOCATION) as f:
        script_config['admin_token'] = f.read().strip()

    with open(args.config, 'w') as f:
        json.dump(script_config, f)
