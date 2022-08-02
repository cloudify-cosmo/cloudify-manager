"""Snapshot-related utilities.

Functions that are called from snapshot-(usually restore), which are always
ran from the restservice virtualenv, put here for easy testing.
"""

from typing import Dict, List

from cloudify.models_states import DeploymentState
from sqlalchemy import select, exists, and_, or_
from manager_rest.storage import models, db


dep_table = models.Deployment.__table__
exc_table = models.Execution.__table__
ni_table = models.NodeInstance.__table__
nodes_table = models.Node.__table__
execution_states: Dict[str, List[str]] = {}
for exc_state, dep_state in DeploymentState.EXECUTION_STATES_SUMMARY.items():
    execution_states.setdefault(dep_state, []).append(exc_state)


def _set_latest_execution():
    """Set .latest_execution for all deployments

    Find the latest execution based on the created_at field, and set it
    for each deployment.
    """
    upd_query = (
        dep_table.update()
        .values(
            _latest_execution_fk=select([
                exc_table.c._storage_id
            ]).where(
                exc_table.c._deployment_fk == dep_table.c._storage_id
            ).order_by(
                exc_table.c.created_at.desc()
            ).limit(1).scalar_subquery()
        )
    )
    db.session.execute(upd_query)


def _set_installation_status():
    """Set .installation_status on all deployments.

    This is based on the dep's node instances: if all are started,
    the installation status is ACTIVE, otherwise INACTIVE
    """
    update_all_query = (
        dep_table.update()
        .values(installation_status=DeploymentState.ACTIVE)
    )
    upd_query = (
        dep_table.update()
        .where(exists(
            select([1])
            .select_from(ni_table.join(nodes_table))
            .where(and_(
                nodes_table.c._deployment_fk == dep_table.c._storage_id,
                ni_table.c.state != 'started',
            ))
        ))
        .values(installation_status=DeploymentState.INACTIVE)
    )
    db.session.execute(update_all_query)
    db.session.execute(upd_query)


def _set_deployment_status():
    """Set .deployment_status for each deployment

    This is based on both the installation status, and the latest
    execution's status. This logic must match the if ladder in
    Deployment.evaluate_deployment_status.

    There's conditions for every of the target statuses, and for each,
    we also add a "where deployment_status is None" filter, which gives
    this `if/else` semantics. (if a deployment hits one status, it won't
    hit another)
    """
    reset_query = dep_table.update().values(deployment_status=None)
    db.session.execute(reset_query)

    in_progress_condition = exc_table.c.status.in_(
        execution_states[DeploymentState.IN_PROGRESS])
    req_attention_condition = or_(
        dep_table.c.installation_status == DeploymentState.INACTIVE,
        exc_table.c.status.in_(execution_states[DeploymentState.FAILED]),
    )
    for condition, target_status in [
        (in_progress_condition, DeploymentState.IN_PROGRESS),
        (req_attention_condition, DeploymentState.REQUIRE_ATTENTION),
        (None, DeploymentState.GOOD)
    ]:
        conditions = [
            dep_table.c._latest_execution_fk == exc_table.c._storage_id,
            dep_table.c.deployment_status.is_(None)
        ]
        if condition is not None:
            conditions.append(condition)
        query = (
            dep_table.update()
            .where(exists(
                select([1]).where(and_(*conditions))
            ))
            .values(deployment_status=target_status)
        )
        db.session.execute(query)


def populate_deployment_statuses():
    """Set the 6.0-new status fields for all deployments.

    This is to be called after a snapshot-restore, to compute the new
    fields: .latest_execution, .installation_status and .deployment_status

    Note that unlike rm.update_deployment_statuses, this does not propagate
    to parents - that is because pre-6.0, there were no parent deployments.
    """
    _set_latest_execution()
    _set_installation_status()
    _set_deployment_status()
