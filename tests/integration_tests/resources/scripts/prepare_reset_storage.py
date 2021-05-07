import json

import argparse

from manager_rest import config
from manager_rest.storage import models
from manager_rest.flask_utils import setup_flask_app


MANAGER_CONFIG = {
    'workflow': {
        'task_retries': 0,
        'task_retry_interval': 0,
        'subgraph_retries': 0
    },
}


def get_password_hash():
    setup_flask_app()
    return models.User.query.get(0).password


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config')
    args = parser.parse_args()
    config.instance.load_from_file('/opt/manager/cloudify-rest.conf')

    script_config = {
        'manager_config': MANAGER_CONFIG,
        'password_hash': get_password_hash(),
    }

    with open(args.config, 'w') as f:
        json.dump(script_config, f)
