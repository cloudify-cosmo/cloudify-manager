#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import pydantic
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import request

from manager_rest import manager_exceptions, workflow_executor
from manager_rest.rest import swagger
from manager_rest.constants import DEPLOYMENT_UPDATE_STATES as STATES
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.execution_token import current_execution
from manager_rest.storage import models, get_storage_manager, db
from manager_rest.utils import (create_filter_params_list_description,
                                current_tenant)

from manager_rest.resource_manager import get_resource_manager
from .. import rest_decorators
from ..rest_utils import (
    lookup_and_validate_user,
    parse_datetime_string,
    remove_invalid_keys,
    valid_user,
    wait_for_execution,
)


class _DeploymentUpdateStartArgs(pydantic.BaseModel):
    blueprint_id: Optional[str] = None
    preview: Optional[bool] = False
    runtime_only_evaluation: Optional[bool] = None
    force: Optional[bool] = False
    inputs: Optional[Dict[str, Any]] = {}
    reinstall_list: Optional[List[str]] = []
    blueprint: Optional[str] = None
    reevaluate_active_statuses: Optional[bool] = False
    auto_correct_types: Optional[bool] = False
    update_plugins: Optional[bool] = True
    install_first: Optional[bool] = False
    ignore_failure: Optional[bool] = False
    skip_reinstall: Optional[bool] = False
    skip_install: Optional[bool] = False
    skip_uninstall: Optional[bool] = False
    skip_drift_check: Optional[bool] = False
    force_reinstall: Optional[bool] = False
    skip_heal: Optional[bool] = False
    workflow_id: Optional[str] = None


class DeploymentUpdate(SecuredResource):
    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def post(self, id, phase):
        """Start a deployment-update

        This endpoint has two modes of operation: POST /initiate, which
        starts a dep-update; and POST /finalize, which currently does nothing,
        and only exists for backwards compatibility.
        """
        if phase == 'initiate':
            return self._initiate(id)
        else:
            sm = get_storage_manager()
            return sm.get(models.DeploymentUpdate, id)

    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def put(self, id, phase):
        """DEPRECATED.

        This method is implemented for backward-compatibility only.
        """
        return self._initiate(id)

    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def _initiate(self, deployment_id):
        sm = get_storage_manager()
        rm = get_resource_manager()

        args = _DeploymentUpdateStartArgs.parse_obj(request.json)
        runtime_eval = args.runtime_only_evaluation

        with sm.transaction() as tx:
            deployment = sm.get(models.Deployment, deployment_id)
            if args.blueprint_id:
                blueprint = sm.get(models.Blueprint, args.blueprint_id)
            else:
                blueprint = deployment.blueprint
            inputs = args.inputs
            if runtime_eval is None:
                runtime_eval = deployment.runtime_only_evaluation
            new_inputs = deployment.inputs.copy()
            new_inputs.update(inputs)
            dep_up = models.DeploymentUpdate(
                id=f'{deployment.id}-{uuid.uuid4()}',
                old_blueprint=deployment.blueprint,
                new_blueprint=blueprint or deployment.blueprint,
                old_inputs=deployment.inputs,
                new_inputs=new_inputs,
                preview=args.preview,
                runtime_only_evaluation=runtime_eval,
                state=STATES.UPDATING,
            )
            execution_args = {
                'update_id': dep_up.id,
                'blueprint_id': blueprint.id,
                'inputs': inputs,
                'preview': args.preview,
                'runtime_only_evaluation': runtime_eval,
                'force': args.force,
                'workflow_id': args.workflow_id,
                'reevaluate_active_statuses': args.reevaluate_active_statuses,
                'auto_correct_types': args.auto_correct_types,
                'update_plugins': args.update_plugins,
                'install_first': args.install_first,
                'ignore_failure': args.ignore_failure,
                'skip_reinstall': args.skip_reinstall,
                'skip_uninstall': args.skip_uninstall,
                'reinstall_list': args.reinstall_list,
                'skip_install': args.skip_install,
                'skip_drift_check': args.skip_drift_check,
                'force_reinstall': args.force_reinstall,
                'skip_heal': args.skip_heal,
            }

            update_exec = models.Execution(
                deployment=deployment,
                workflow_id='update',
                parameters=execution_args,
                allow_custom_parameters=True,
            )
            sm.put(update_exec)

            if current_execution and \
                    current_execution.workflow_id == 'csys_update_deployment':
                # if we're created from a update_deployment workflow, join its
                # exec-groups, for easy tracking
                for exec_group in current_execution.execution_groups:
                    exec_group.executions.append(update_exec)
            dep_up.execution = update_exec
            sm.put(dep_up)
            dep_up.set_deployment(deployment)
            try:
                messages = rm.prepare_executions(
                    [update_exec],
                    allow_overlapping_running_wf=True,
                    force=args.force,
                )
            except manager_exceptions.DependentExistsError:
                dep_up.state = STATES.FAILED
                sm.update(dep_up)
                tx.force_commit = True
                raise

        workflow_executor.execute_workflow(messages)
        if args.preview:
            wait_for_execution(sm, dep_up.execution.id)
            sm.refresh(dep_up)
        return dep_up


class _CreateDeploymentUpdateArgs(_DeploymentUpdateStartArgs):
    deployment_id: str
    state: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    old_blueprint_id: Optional[str] = None
    execution_id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None


class _UpdateDeploymentUpdateArgs(pydantic.BaseModel):
    state: Optional[str] = None
    plan: Optional[Dict[str, Any]] = None
    steps: Optional[List[Any]] = None
    nodes: Optional[Any] = None
    node_instances: Optional[Any] = None


class DeploymentUpdateId(SecuredResource):
    @swagger.operation(
        responseClass=models.DeploymentUpdate,
        nickname="DeploymentUpdate",
        notes='Return a single deployment update',
        parameters=create_filter_params_list_description(
            models.DeploymentUpdate.response_fields, 'deployment update')
    )
    @authorize('deployment_update_get')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def get(self, update_id, _include=None):
        """Get a deployment update by id"""
        return get_storage_manager().get(
            models.DeploymentUpdate,
            update_id,
            include=_include,
        )

    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def put(self, update_id):
        params = _CreateDeploymentUpdateArgs.parse_obj(request.json)
        sm = get_storage_manager()
        if params.execution_id is None and not current_execution:
            # Only allow non-execution creation of dep updates for restores
            raise manager_exceptions.ForbiddenError(
                'Deployment update objects can only be created by executions')

        if params.get('execution_id'):
            execution = sm.get(models.Execution,
                               params['execution_id'])
        else:
            execution = current_execution
        created_at = None
        if params.get('created_at'):
            check_user_action_allowed('set_timestamp', None, True)
            created_at = parse_datetime_string(params['created_at'])
        created_by = None
        if params.get('created_by'):
            check_user_action_allowed('set_owner', None, True)
            created_by = valid_user(params['created_by'])

        add_steps = False
        with sm.transaction():
            dep = sm.get(models.Deployment, params.deployment_id)
            dep_upd = sm.get(models.DeploymentUpdate, update_id,
                             fail_silently=True)
            if dep_upd is None:
                dep_upd = models.DeploymentUpdate(
                    id=update_id,
                    _execution_fk=execution._storage_id,
                )
            dep_upd.state = params.state or STATES.UPDATING
            dep_upd.new_inputs = params.inputs
            if params.blueprint_id:
                dep_upd.new_blueprint = sm.get(
                    models.Blueprint, params.blueprint_id)
            if created_at:
                dep_upd.created_at = created_at
            if created_by:
                dep_upd.creator = created_by
            if params.old_blueprint_id:
                dep_upd.old_blueprint = sm.get(
                    models.Blueprint, params.old_blueprint_id)
            for attr in [
                'runtime_only_evaluation', 'deployment_plan', 'steps',
                'deployment_update_node_instances', 'modified_entity_ids',
                'central_plugins_to_install', 'central_plugins_to_uninstall',
                'old_inputs', 'deployment_update_nodes', 'visibility',
            ]:
                if getattr(params, attr, None) is not None:
                    if attr == 'steps':
                        add_steps = True
                    else:
                        setattr(dep_upd, attr, getattr(params, attr, None))
            dep_upd.set_deployment(dep)

        if add_steps:
            steps_to_add = self._prepare_raw_steps(
                dep_upd, params['steps'])
            with sm.transaction():
                db.session.execute(
                    models.DeploymentUpdateStep.__table__.insert(),
                    steps_to_add,
                )

        return dep_upd

    def _prepare_raw_steps(self, dep_update, raw_steps):
        if any(item.get('created_by') for item in raw_steps):
            check_user_action_allowed('set_owner')

        valid_params = {'action', '_creator_id', '_deployment_update_fk',
                        'entity_id', 'entity_type', 'id', 'private_resource',
                        'resource_availability', '_tenant_id',
                        'topology_order', 'visibility'}

        user_lookup_cache: Dict[str, models.User] = {}

        for raw_step in raw_steps:
            raw_step['_tenant_id'] = dep_update._tenant_id

            created_by = lookup_and_validate_user(raw_step.get('created_by'),
                                                  user_lookup_cache)
            raw_step['_creator_id'] = created_by.id
            raw_step['_deployment_update_fk'] = dep_update._storage_id
            raw_step['visibility'] = dep_update.visibility

            remove_invalid_keys(raw_step, valid_params)

        return raw_steps

    @authorize('deployment_update_update')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def patch(self, update_id):
        params = _UpdateDeploymentUpdateArgs.parse_obj(request.json)
        sm = get_storage_manager()
        with sm.transaction():
            dep_upd = sm.get(models.DeploymentUpdate, update_id)
            if params.state:
                dep_upd.state = params.state
            if params.plan:
                dep_upd.deployment_plan = params.plan
            if params.steps:
                for step_spec in params.steps:
                    step = models.DeploymentUpdateStep(
                        id=str(uuid.uuid4()),
                        **step_spec
                    )
                    step.set_deployment_update(dep_upd)
            if params.nodes:
                dep_upd.deployment_update_nodes = params.nodes
            if params.node_instances:
                dep_upd.deployment_update_node_instances = \
                    params.node_instances
            if dep_upd.state == STATES.SUCCESSFUL and not dep_upd.preview:
                dep_upd.deployment.updated_at = datetime.utcnow()
            return dep_upd


class _BulkCreateDepUpdatesArgs(pydantic.BaseModel):
    deployment_updates: List[Any] = []


class DeploymentUpdates(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.DeploymentUpdate.__name__),
        nickname="listDeploymentUpdates",
        notes='Returns a list of deployment updates',
        parameters=create_filter_params_list_description(
            models.DeploymentUpdate.response_fields,
            'deployment updates'
        )
    )
    @authorize('deployment_update_list')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    @rest_decorators.create_filters(models.DeploymentUpdate)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.DeploymentUpdate)
    @rest_decorators.search('id')
    def get(self,
            _include=None,
            filters=None,
            pagination=None,
            sort=None,
            search=None,
            **kwargs):
        """List deployment updates"""
        return get_storage_manager().list(
            models.DeploymentUpdate,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            substr_filters=search,
        )

    @swagger.operation(
        nickname="bulkInsertDeploymentUpdates",
        notes="For internal use.",
    )
    @authorize('deployment_update_create')
    def post(self):
        params = _BulkCreateDepUpdatesArgs.parse_obj(request.json)
        sm = get_storage_manager()
        raw_updates = params.deployment_updates
        raw_steps = []
        for raw_update in raw_updates:
            raw_steps.extend(raw_update.pop('steps', []))
        if not raw_updates:
            return "", 204
        user_cache: Dict[str, models.User] = {}
        tenant_cache: Dict[str, models.Tenant] = {}
        with sm.transaction():
            self._prepare_raw_updates(sm, raw_updates, user_cache,
                                      tenant_cache)
            db.session.execute(
                models.DeploymentUpdate.__table__.insert(),
                raw_updates,
            )
            self._prepare_raw_steps(sm, raw_steps, user_cache, tenant_cache)
            db.session.execute(
                models.DeploymentUpdateStep.__table__.insert(),
                raw_steps,
            )
        return "[]", 201

    def _prepare_raw_updates(self, sm, raw_updates, user_cache, tenant_cache):
        if any(item.get('creator') for item in raw_updates):
            check_user_action_allowed('set_owner')

        if any(item.get('created_at') for item in raw_updates):
            check_user_action_allowed('set_timestamp')

        valid_params = {'id', 'visibility', 'created_at', 'deployment_plan',
                        'deployment_update_node_instances',
                        'central_plugins_to_uninstall',
                        'central_plugins_to_install',
                        'deployment_update_nodes', 'modified_entity_ids',
                        'old_inputs', 'new_inputs', 'state',
                        'runtime_only_evaluation',
                        'keep_old_deployment_dependencies', '_deployment_fk',
                        'execution_id', '_old_blueprint_fk',
                        '_new_blueprint_fk', '_tenant_id', '_creator_id',
                        'steps'}

        bp_cache: Dict[str, models.Blueprint] = {}
        dep_cache: Dict[str, models.Deployment] = {}
        for raw_update in raw_updates:
            creator = lookup_and_validate_user(raw_update.get('creator'),
                                               user_cache)
            raw_update['_creator_id'] = creator.id

            if 'tenant_name' in raw_update:
                raw_update['_tenant_id'] = _lookup_id(
                    sm, models.Tenant, raw_update['tenant_name'],
                    tenant_cache)
            else:
                raw_update['_tenant_id'] = current_tenant.id

            raw_update['_old_blueprint_fk'] = _lookup_id(
                sm, models.Blueprint, raw_update['old_blueprint_id'],
                bp_cache)
            raw_update['_new_blueprint_fk'] = _lookup_id(
                sm, models.Blueprint, raw_update['new_blueprint_id'],
                bp_cache)
            raw_update['_deployment_fk'] = _lookup_id(
                sm, models.Deployment, raw_update['deployment_id'],
                dep_cache)

            remove_invalid_keys(raw_update, valid_params)

    def _prepare_raw_steps(self, sm, raw_steps, user_cache, tenant_cache):
        valid_params = {'id', 'visibility', 'action', 'entity_id',
                        'entity_type', 'topology_order',
                        '_deployment_update_fk', '_tenant_id',
                        '_creator_id'}

        dep_update_cache: Dict[str, models.DeploymentUpdate] = {}
        for raw_step in raw_steps:
            creator = lookup_and_validate_user(raw_step.get('creator'),
                                               user_cache)
            raw_step['_creator_id'] = creator.id

            if 'tenant_name' in raw_step:
                raw_step['_tenant_id'] = _lookup_id(
                    sm, models.Tenant, raw_step['tenant_name'],
                    tenant_cache)
            else:
                raw_step['_tenant_id'] = current_tenant.id

            raw_step['_deployment_update_fk'] = _lookup_id(
                sm, models.DeploymentUpdate, raw_step['deployment_update_id'],
                dep_update_cache)

            remove_invalid_keys(raw_step, valid_params)


def _lookup_id(sm, model_type, search_id, cache=None):
    if cache is None:
        # We won't cache the results, but set this to keep the rest of the
        # function logic the same
        cache = {}
    search_prop = 'id'
    id_prop = '_storage_id'
    if model_type == models.Tenant:
        search_prop = 'name'
        id_prop = 'id'
    if search_id not in cache:
        result = sm.list(model_type, filters={search_prop: search_id})
        count = len(result)
        if count != 1:
            raise RuntimeError(f'Expected 1 result for {model_type} with '
                               f'ID {search_id}, but got {count}.')
        cache[search_id] = getattr(result.items[0], id_prop)
    return cache[search_id]
