#!/opt/manager/env/bin/python

import os
import sys
import socket
import logging
import argparse

from manager_rest import config
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import db, models

logger = logging.getLogger(__name__)


def update_managers_version(version):
    logger.debug('Updating Cloudify managers version in DB...')

    hostname = socket.gethostname()
    if hasattr(config.instance, 'manager_hostname'):
        hostname = config.instance.manager_hostname

    managers = (
        models.Manager.query
        .filter_by(hostname=hostname)
        .all()
    )
    for manager in managers:
        manager.version = version
    db.session.commit()


if __name__ == '__main__':
    os.environ.setdefault(
        'MANAGER_REST_CONFIG_PATH',
        '/opt/manager/cloudify-rest.conf',
    )
    os.environ.setdefault(
        'MANAGER_REST_SECURITY_CONFIG_PATH',
        '/opt/manager/rest-security.conf',
    )
    with setup_flask_app().app_context():
        config.instance.load_configuration()
    parser = argparse.ArgumentParser(
        description="Update the Cloudify manager version in the DB")
    parser.add_argument('version')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)s %(asctime)s %(message)s',
                        stream=sys.stderr)
    if os.geteuid() != 0:
        raise RuntimeError('This script must be run as root!')
    update_managers_version(args.version)
