"""Snapshot-related utilities.

Functions that are called from snapshot-(usually restore), which are always
ran from the restservice virtualenv, put here for easy testing.
"""

import functools
import operator

from typing import Dict, List

from cloudify.models_states import DeploymentState
from dsl_parser.functions import find_requirements
from dsl_parser.models import Plan
from sqlalchemy import select, exists, and_, or_
from sqlalchemy.sql.expression import text as sql_text
from sqlalchemy.orm import Session
from manager_rest.storage import models, db


dep_table = models.Deployment.__table__
exc_table = models.Execution.__table__
ni_table = models.NodeInstance.__table__
nodes_table = models.Node.__table__
execution_states: Dict[str, List[str]] = {}
for exc_state, dep_state in DeploymentState.EXECUTION_STATES_SUMMARY.items():
    execution_states.setdefault(dep_state, []).append(exc_state)

PICKLE_TO_JSON_MIGRATION_BATCH_SIZE = 1000


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


pickle_migrations = {
    models.Deployment: [
        'capabilities', 'groups', 'inputs', 'outputs', 'policy_triggers',
        'policy_types', 'scaling_groups', 'workflows',
    ],
    models.Blueprint: ['plan'],
    models.DeploymentModification: [
        'context', 'modified_nodes', 'node_instances',
    ],
    models.DeploymentUpdate: [
        'deployment_plan', 'deployment_update_node_instances',
        'deployment_update_deployment', 'central_plugins_to_uninstall',
        'central_plugins_to_install', 'deployment_update_nodes',
        'modified_entity_ids', 'old_inputs', 'new_inputs',
    ],
    models.Execution: ['parameters'],
    models.Node: [
        'plugins', 'plugins_to_install', 'properties', 'relationships',
        'operations', 'type_hierarchy',
    ],
    models.NodeInstance: [
        'relationships', 'runtime_properties', 'scaling_groups',
    ],
    models.Plugin: [
        'excluded_wheels', 'supported_platform', 'supported_py_versions',
        'wheels',
    ],
    models.PluginsUpdate: ['deployments_to_update'],
}


def _json_column_null(json_column):
    """Condition of checking whether the json column is null

    We consider the json column empty in both the case of a SQL null,
    and the JSON null.
    The value will be a SQL null when the row is inserted directly via
    SQL (eg. in snapshot-restore), and it will be a JSON null when
    inserted using the ORM.
    note: db.JSON.NULL doesn't work here, but I don't know why.
    """
    return json_column.is_(None) | (json_column == sql_text("'null'"))


def _column_migrate_condition(model_cls, attr):
    """The SQL condition to check if the column needs to be migrated"""
    pickle_column = getattr(model_cls, f'{attr}_p')
    json_column = getattr(model_cls, attr)
    pickle_not_empty = pickle_column.isnot(None)

    return pickle_not_empty & _json_column_null(json_column)


def migrate_model(session: Session, model_cls, attributes, batch_size: int):
    any_column_needs_migrating = functools.reduce(
        operator.or_,
        (_column_migrate_condition(model_cls, attr) for attr in attributes)
    )
    stmt = (
        select(model_cls)
        .where(any_column_needs_migrating)
        .limit(batch_size)
        .with_for_update()
    )

    while True:
        results = session.execute(stmt).scalars().all()
        for inst in results:
            if isinstance(inst, models.Execution):
                inst.allow_custom_parameters = True
            for attr in attributes:
                # only set the attribute if it's not already set
                pickle_attr = getattr(inst, f'{attr}_p')
                json_attr = getattr(inst, attr)
                if pickle_attr is not None and not json_attr:
                    setattr(inst, attr, pickle_attr)

            session.add(inst)
        session.flush()

        if len(results) < batch_size:
            break


def migrate_pickle_to_json(batch_size=PICKLE_TO_JSON_MIGRATION_BATCH_SIZE):
    """Migrate the fields which were pickled to their JSON counterparts"""
    for model, attributes in pickle_migrations.items():
        migrate_model(db.session, model, attributes, batch_size)


def set_blueprint_requirements(batch_size: int=1000):
    stmt = (
        select(models.Blueprint)
        .where(_json_column_null(models.Blueprint.requirements))
        .limit(batch_size)
        .with_for_update()
    )
    while True:
        results = db.session.execute(stmt).scalars().all()
        for bp in results:
            try:
                plan = Plan(bp.plan)
                reqs = find_requirements(plan)
            except Exception:
                reqs = {}
            bp.requirements = reqs
            db.session.add(bp)
        db.session.flush()

        if len(results) < batch_size:
            break
