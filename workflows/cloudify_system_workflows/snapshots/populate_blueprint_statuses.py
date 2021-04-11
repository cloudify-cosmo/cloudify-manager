import os

from manager_rest import config
from manager_rest.storage import models, get_storage_manager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import SECURITY_FILE_LOCATION

from cloudify.models_states import BlueprintUploadState

os.environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
os.environ['MANAGER_REST_SECURITY_CONFIG_PATH'] = SECURITY_FILE_LOCATION


def _populate_blueprint_statuses():
    sm = get_storage_manager()
    blueprints = sm.list(models.Blueprint, get_all_results=True)
    for blueprint in blueprints:
        blueprint.state = BlueprintUploadState.UPLOADED
        sm.update(blueprint)


if __name__ == '__main__':
    with setup_flask_app().app_context():
        config.instance.load_configuration()
        _populate_blueprint_statuses()
