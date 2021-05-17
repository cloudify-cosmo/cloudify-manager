"""Snapshot-related utilities.

Functions that are called from snapshot-(usually restore), which are always
ran from the restservice virtualenv, put here for easy testing.
"""

from manager_rest import resource_manager
from manager_rest.storage import (
    models,
    get_storage_manager,
    db
)


def populate_deployment_statuses():
    sm = get_storage_manager()
    rm = resource_manager.ResourceManager(sm)
    deployments = sm.list(models.Deployment, get_all_results=True)
    for dep in deployments:
        latest_execution = \
            db.session.query(
                models.Execution
            ).filter(
                models.Execution._deployment_fk == dep._storage_id
            ).order_by(
                models.Execution.created_at.desc()
            ).limit(1).one()
        rm.update_deployment_statuses(latest_execution)
