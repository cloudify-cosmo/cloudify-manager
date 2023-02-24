import json

import argparse

from manager_rest import config
from manager_rest.constants import BOOTSTRAP_ADMIN_ID, DEFAULT_TENANT_ID
from manager_rest.storage import models
from manager_rest.flask_utils import setup_flask_app


MANAGER_CONFIG = {
    'workflow': {
        'task_retries': 5,
        'task_retry_interval': 1,
        'subgraph_retries': 0,
    },
}


def get_password_hash():
    return models.User.query.get(BOOTSTRAP_ADMIN_ID).password


def get_tenant_password():
    return models.Tenant.query.get(DEFAULT_TENANT_ID).rabbitmq_password


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config')
    args = parser.parse_args()
    config.instance.load_from_file('/opt/manager/cloudify-rest.conf')
    config.instance.load_from_file('/opt/manager/rest-security.conf',
                                   namespace='security')

    with setup_flask_app().app_context():
        script_config = {
            'manager_config': MANAGER_CONFIG,
            'password_hash': get_password_hash(),
            'default_tenant_password': get_tenant_password(),
        }

    with open(args.config, 'w') as f:
        json.dump(script_config, f)
