import os

from manager_rest import config
from manager_rest import resource_manager
from manager_rest.storage import (
    models,
    get_storage_manager,
    db
)
from cloudify.workflows import ctx

from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import SECURITY_FILE_LOCATION

os.environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
os.environ['MANAGER_REST_SECURITY_CONFIG_PATH'] = SECURITY_FILE_LOCATION


def _populate_deployment_statuses():
    ctx.logger.info(
        'Start populating deployment statuses restored from snapshot'
    )
    sm = get_storage_manager()
    rm = resource_manager.ResourceManager(sm)
    deployments = sm.list(models.Deployment, get_all_results=True)
    for dep in deployments:
        latest_execution = \
            db.session.query(
                models.Execution
            ).filter(
                models.Execution._deployment_fk==dep._storage_id
            ).order_by(
                models.Execution.created_at.desc()
            ).limit(1).one()
        rm.update_deployment_statuses(latest_execution)
    ctx.logger.info(
        'Finished populating deployment statuses restored from snapshot'
    )


if __name__ == '__main__':
    with setup_flask_app().app_context():
        config.instance.load_configuration()
        _populate_deployment_statuses()
