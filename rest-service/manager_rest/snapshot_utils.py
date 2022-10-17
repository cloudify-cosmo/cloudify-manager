"""Snapshot-related utilities.

Functions that are called from snapshot-(usually restore), which are always
ran from the restservice virtualenv, put here for easy testing.
"""

from typing import Dict, List

from cloudify.models_states import DeploymentState
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


def _migrate_blueprints_table(session: Session, batch_size: int):
    stmt = select(models.Blueprint).where(
        (models.Blueprint.plan_p.isnot(None)) &
        (models.Blueprint.plan == sql_text("'null'"))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for bp in results:
            bp.plan = bp.plan_p
            session.add(bp)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_deployments_table(session: Session, batch_size: int):
    stmt = select(models.Deployment).where(
        ((models.Deployment.capabilities_p.isnot(None)) &
         (models.Deployment.capabilities == sql_text("'null'"))) |
        ((models.Deployment.groups_p.isnot(None)) &
         (models.Deployment.groups == sql_text("'null'"))) |
        ((models.Deployment.inputs_p.isnot(None)) &
         (models.Deployment.inputs == sql_text("'null'"))) |
        ((models.Deployment.outputs_p.isnot(None)) &
         (models.Deployment.outputs == sql_text("'null'"))) |
        ((models.Deployment.policy_triggers_p.isnot(None)) &
         (models.Deployment.policy_triggers == sql_text("'null'"))) |
        ((models.Deployment.policy_types_p.isnot(None)) &
         (models.Deployment.policy_types == sql_text("'null'"))) |
        ((models.Deployment.scaling_groups_p.isnot(None)) &
         (models.Deployment.scaling_groups == sql_text("'null'"))) |
        ((models.Deployment.workflows_p.isnot(None)) &
         (models.Deployment.workflows == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for dep in results:
            dep.capabilities = dep.capabilities_p
            dep.groups = dep.groups_p
            dep.inputs = dep.inputs_p
            dep.outputs = dep.outputs_p
            dep.policy_triggers = dep.policy_triggers_p
            dep.policy_types = dep.policy_types_p
            dep.scaling_groups = dep.scaling_groups_p
            dep.workflows = dep.workflows_p
            session.add(dep)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_deployment_modifications_table(session: Session, batch_size: int):
    model = models.DeploymentModification
    stmt = select(model).where(
        ((model.context_p.isnot(None)) &
         (model.context == sql_text("'null'"))) |
        ((model.modified_nodes_p.isnot(None)) &
         (model.modified_nodes == sql_text("'null'"))) |
        ((model.node_instances_p.isnot(None)) &
         (model.node_instances == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for dep_mod in results:
            dep_mod.context = dep_mod.context_p
            dep_mod.modified_nodes = dep_mod.modified_nodes_p
            dep_mod.node_instances = dep_mod.node_instances_p
            session.add(dep_mod)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_deployment_updates_table(session: Session, batch_size: int):
    model = models.DeploymentUpdate
    stmt = select(model).where(
        ((model.deployment_plan_p.isnot(None)) &
         (model.deployment_plan == sql_text("'null'"))) |
        ((model.deployment_update_node_instances_p.isnot(None)) &
         (model.deployment_update_node_instances == sql_text("'null'"))) |
        ((model.deployment_update_deployment_p.isnot(None)) &
         (model.deployment_update_deployment == sql_text("'null'"))) |
        ((model.central_plugins_to_uninstall_p.isnot(None)) &
         (model.central_plugins_to_uninstall == sql_text("'null'"))) |
        ((model.central_plugins_to_install_p.isnot(None)) &
         (model.central_plugins_to_install == sql_text("'null'"))) |
        ((model.deployment_update_nodes_p.isnot(None)) &
         (model.deployment_update_nodes == sql_text("'null'"))) |
        ((model.modified_entity_ids_p.isnot(None)) &
         (model.modified_entity_ids == sql_text("'null'"))) |
        ((model.old_inputs_p.isnot(None)) &
         (model.old_inputs == sql_text("'null'"))) |
        ((model.new_inputs_p.isnot(None)) &
         (model.new_inputs == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for dep_upd in results:
            dep_upd.deployment_plan = dep_upd.deployment_plan_p
            dep_upd.deployment_update_node_instances =\
                dep_upd.deployment_update_node_instances_p
            dep_upd.deployment_update_deployment =\
                dep_upd.deployment_update_deployment_p
            dep_upd.central_plugins_to_uninstall =\
                dep_upd.central_plugins_to_uninstall_p
            dep_upd.central_plugins_to_install =\
                dep_upd.central_plugins_to_install_p
            dep_upd.deployment_update_nodes = dep_upd.deployment_update_nodes_p
            dep_upd.modified_entity_ids = dep_upd.modified_entity_ids_p
            dep_upd.old_inputs = dep_upd.old_inputs_p
            dep_upd.new_inputs = dep_upd.new_inputs_p
            session.add(dep_upd)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_executions_table(session: Session, batch_size: int):
    stmt = select(models.Execution).where(
        (models.Execution.parameters_p.isnot(None)) &
        (models.Execution.parameters == sql_text("'null'"))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for execution in results:
            execution.parameters = execution.parameters_p
            session.add(execution)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_nodes_table(session: Session, batch_size: int):
    stmt = select(models.Node).where(
        ((models.Node.plugins_p.isnot(None)) &
         (models.Node.plugins == sql_text("'null'"))) |
        ((models.Node.plugins_to_install_p.isnot(None)) &
         (models.Node.plugins_to_install == sql_text("'null'"))) |
        ((models.Node.properties_p.isnot(None)) &
         (models.Node.properties == sql_text("'null'"))) |
        ((models.Node.relationships_p.isnot(None)) &
         (models.Node.relationships == sql_text("'null'"))) |
        ((models.Node.operations_p.isnot(None)) &
         (models.Node.operations == sql_text("'null'"))) |
        ((models.Node.type_hierarchy_p.isnot(None)) &
         (models.Node.type_hierarchy == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for node in results:
            node.plugins = node.plugins_p
            node.plugins_to_install = node.plugins_to_install_p
            node.properties = node.properties_p
            node.relationships = node.relationships_p
            node.operations = node.operations_p
            node.type_hierarchy = node.type_hierarchy_p
            session.add(node)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_node_instances_table(session: Session, batch_size: int):
    stmt = select(models.NodeInstance).where(
        ((models.NodeInstance.relationships_p.isnot(None)) &
         (models.NodeInstance.relationships == sql_text("'null'"))) |
        ((models.NodeInstance.runtime_properties_p.isnot(None)) &
         (models.NodeInstance.runtime_properties == sql_text("'null'"))) |
        ((models.NodeInstance.scaling_groups_p.isnot(None)) &
         (models.NodeInstance.scaling_groups == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for ni in results:
            ni.relationships = ni.relationships_p
            ni.runtime_properties = ni.runtime_properties_p
            ni.scaling_groups = ni.scaling_groups_p
            session.add(ni)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_plugins_table(session: Session, batch_size: int):
    stmt = select(models.Plugin).where(
        ((models.Plugin.excluded_wheels_p.isnot(None)) &
         (models.Plugin.excluded_wheels == sql_text("'null'"))) |
        ((models.Plugin.supported_platform_p.isnot(None)) &
         (models.Plugin.supported_platform == sql_text("'null'"))) |
        ((models.Plugin.supported_py_versions_p.isnot(None)) &
         (models.Plugin.supported_py_versions == sql_text("'null'"))) |
        ((models.Plugin.wheels_p.isnot(None)) &
         (models.Plugin.wheels == sql_text("'null'")))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for plugin in results:
            plugin.excluded_wheels = plugin.excluded_wheels_p
            plugin.supported_platform = plugin.supported_platform_p
            plugin.supported_py_versions = plugin.supported_py_versions_p
            plugin.wheels = plugin.wheels_p
            session.add(plugin)
        session.flush()

        if len(results) < batch_size:
            break


def _migrate_plugins_updates_table(session: Session, batch_size: int):
    stmt = select(models.PluginsUpdate).where(
        (models.PluginsUpdate.deployments_to_update_p.isnot(None)) &
        (models.PluginsUpdate.deployments_to_update == sql_text("'null'"))
    ).limit(batch_size).with_for_update()

    while True:
        results = session.execute(stmt).scalars().all()
        for plug_upd in results:
            plug_upd.deployments_to_update = plug_upd.deployments_to_update_p
            session.add(plug_upd)
        session.flush()

        if len(results) < batch_size:
            break


def migrate_pickle_to_json(batch_size=PICKLE_TO_JSON_MIGRATION_BATCH_SIZE):
    """Migrate the fields which were pickled to their JSON counterparts"""
    _migrate_blueprints_table(db.session, batch_size)
    _migrate_deployments_table(db.session, batch_size)
    _migrate_deployment_modifications_table(db.session, batch_size)
    _migrate_deployment_updates_table(db.session, batch_size)
    _migrate_executions_table(db.session, batch_size)
    _migrate_nodes_table(db.session, batch_size)
    _migrate_node_instances_table(db.session, batch_size)
    _migrate_plugins_table(db.session, batch_size)
    _migrate_plugins_updates_table(db.session, batch_size)
