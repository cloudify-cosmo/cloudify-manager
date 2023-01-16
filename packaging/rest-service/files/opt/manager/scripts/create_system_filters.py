#!/opt/manager/env/bin/python

import os

from manager_rest.storage import db
from manager_rest.flask_utils import setup_flask_app
from manager_rest.configure_manager import create_system_filters


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
    with setup_flask_app().app_context():
        create_system_filters()
        db.session.commit()
