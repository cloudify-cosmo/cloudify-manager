import os
from manager_rest import config
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import SECURITY_FILE_LOCATION
from manager_rest.snapshot_utils import populate_deployment_statuses
from manager_rest.storage import db


os.environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
os.environ['MANAGER_REST_SECURITY_CONFIG_PATH'] = SECURITY_FILE_LOCATION

if __name__ == '__main__':
    with setup_flask_app().app_context():
        config.instance.load_configuration()
        populate_deployment_statuses()
        db.session.commit()
