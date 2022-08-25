import pydantic
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import request
from sqlalchemy.dialects.postgresql import insert

from cloudify.models_states import ExecutionState

from manager_rest import workflow_executor
from manager_rest.rest.responses_v3 import ItemsCount
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.rest import resources_v2, rest_decorators
from manager_rest.manager_exceptions import (
    BadParametersError, NonexistentWorkflowError)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest.rest_utils import (
    parse_datetime_multiple_formats,
    valid_user,
    parse_datetime_string,
    ListQuery,
)
from manager_rest.storage import models, db, get_storage_manager, ListResult


class _ExecutionDeleteArgs(pydantic.BaseModel):
    keep_last: Optional[int] = None
    to_datetime: Optional[str] = None


class Executions(resources_v2.Executions):
    @authorize('execution_delete')
    @rest_decorators.marshal_with(ItemsCount)
    @rest_decorators.create_filters(models.Execution)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def delete(self, filters=None, pagination=None, all_tenants=None):
        args = _ExecutionDeleteArgs.parse_obj(request.json)
        if args.keep_last is not None:
            if args.to_datetime is not None:
                raise BadParametersError(
                    "Must provide either a `to_datetime` timestamp or a "
                    "`keep_last` number of executions to keep"
                )
            if args.keep_last <= 0:
                raise BadParametersError(
                    "`keep_last` must be an integer greater than 0. got {} "
                    "instead.".format(args.keep_last)
                )
        requested_time = None
        if args.to_datetime is not None:
            requested_time = parse_datetime_multiple_formats(
                args.to_datetime)
        if 'status' in filters:
            if filters['status'] not in ExecutionState.END_STATES:
                raise BadParametersError(
                    'Can\'t filter by execution status `{0}`. '
                    'Allowed statuses are: {1}'.format(
                        filters['status'], ExecutionState.END_STATES)
                )
        else:
            filters['status'] = ExecutionState.END_STATES
        sm = get_storage_manager()
        executions = sm.list(models.Execution,
                             filters=filters,
                             all_tenants=all_tenants,
                             get_all_results=True)
        dep_creation_execs: Dict[str, int] = {}
        for execution in executions:
            if execution.workflow_id == 'create_deployment_environment' and \
                    execution.status == 'terminated':
                dep_creation_execs[execution.deployment_id] = \
                    dep_creation_execs.get(execution.deployment_id, 0) + 1

        deleted_count = 0
        if requested_time:
            for execution in executions:
                creation_time = datetime.strptime(execution.created_at,
                                                  '%Y-%m-%dT%H:%M:%S.%fZ')

                if creation_time < requested_time and \
                        self._can_delete_execution(execution,
                                                   dep_creation_execs):
                    sm.delete(execution)
                    deleted_count += 1
        else:
            if args.keep_last:
                max_to_delete = len(executions) - args.keep_last
            for execution in executions:
                if self._can_delete_execution(execution, dep_creation_execs):
                    sm.delete(execution)
                    deleted_count += 1
                    if args.keep_last and deleted_count >= max_to_delete:
                        break
        return ListResult([{'count': deleted_count}],
                          {'pagination': pagination})

    @staticmethod
    def _can_delete_execution(execution, dep_creation_execs):
        if execution.workflow_id == \
                'create_deployment_environment':
            if dep_creation_execs[execution.deployment_id] <= 1:
                return False
            else:
                dep_creation_execs[execution.deployment_id] -= 1
        return True


class ExecutionsCheck(SecuredResource):
    @authorize('execution_should_start')
    def get(self, execution_id):
        """
        `should_start` - return True if this execution can currently start
        (no system exeuctions / executions under the same deployment are
        currently running)
        """

        sm = get_storage_manager()
        execution = sm.get(models.Execution, execution_id)
        deployment_id = execution.deployment.id
        rm = get_resource_manager()
        return not (rm.check_for_executions(deployment_id, force=False,
                                            queue=True, execution=execution))


class _CreateExecGroupArgs(pydantic.BaseModel):
    deployment_group_id: str
    workflow_id: str
    default_parameters: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    force: Optional[bool] = False
    concurrency: Optional[int] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    associated_executions: Optional[List[str]] = None
    id: Optional[str] = None


class ExecutionGroups(SecuredResource):
    @authorize('execution_group_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.ExecutionGroup)
    @rest_decorators.sortable(models.ExecutionGroup)
    @rest_decorators.create_filters(models.ExecutionGroup)
    @rest_decorators.paginate
    def get(self, _include=None, filters=None, pagination=None, sort=None):
        if _include and 'execution_ids' in _include:
            # If we don't do this, this include will result in lots of queries
            _include.remove('execution_ids')
            _include.append('executions')
        args = ListQuery.parse_obj(request.args)
        return get_storage_manager().list(
            models.ExecutionGroup,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=args.all_tenants,
            get_all_results=args.get_all_results
        )

    @authorize('execution_group_create')
    @rest_decorators.marshal_with(models.ExecutionGroup, force_get_data=True)
    @rest_decorators.not_while_cancelling
    def post(self):
        request_dict = _CreateExecGroupArgs.parse_obj(request.json).dict()
        default_parameters = request_dict.get('default_parameters') or {}
        parameters = request_dict.get('parameters') or {}
        workflow_id = request_dict['workflow_id']
        force = request_dict.get('force') or False
        concurrency = request_dict.get('concurrency', 5)

        created_at = None
        if request_dict.get('created_at'):
            check_user_action_allowed('set_timestamp')
            created_at = parse_datetime_string(request_dict['created_at'])

        owner = None
        if request_dict.get('created_by'):
            check_user_action_allowed('set_owner')
            owner = valid_user(request_dict['created_by'])

        sm = get_storage_manager()

        executions = []
        if request_dict.get('associated_executions'):
            executions = [
                sm.get(models.Execution, execution)
                for execution in request_dict['associated_executions']
            ]
        if request_dict.get('id'):
            check_user_action_allowed('set_execution_group_details',
                                      None, True)
        dep_group = sm.get(models.DeploymentGroup,
                           request_dict['deployment_group_id'])
        group = models.ExecutionGroup(
            id=request_dict.get('id') or str(uuid.uuid4()),
            deployment_group=dep_group,
            workflow_id=workflow_id,
            visibility=dep_group.visibility,
            concurrency=concurrency,
        )
        if created_at:
            group.created_at = created_at
        if owner:
            group.creator = owner
        if executions:
            group.executions = executions
        sm.put(group)
        rm = get_resource_manager()
        if executions:
            # This is a pre-populated group, so should be part of a restore,
            # don't actually run anything!
            return group
        with sm.transaction():
            for dep in dep_group.deployments:
                params = default_parameters.copy()
                params.update(parameters.get(dep.id) or {})
                try:
                    execution = models.Execution(
                        workflow_id=workflow_id,
                        deployment=dep,
                        parameters=params,
                        status=ExecutionState.PENDING,
                    )
                except NonexistentWorkflowError as ex:
                    log = models.Log(
                        reported_timestamp=datetime.utcnow(),
                        message=str(ex),
                        logger='cloudify-restservice',
                        level='info',
                        execution_group=group
                    )
                    sm.put(log)
                else:
                    sm.put(execution)
                    executions.append(execution)
                    group.executions.append(execution)
            messages = group.start_executions(sm, rm, force=force)
        workflow_executor.execute_workflow(messages)
        return group


class _ExecutionGroupActionArgs(pydantic.BaseModel):
    action: str


class _ExecutionGroupUpdateArgs(pydantic.BaseModel):
    success_group_id: Optional[str] = None
    failure_group_id: Optional[str] = None


class ExecutionGroupsId(SecuredResource):
    @authorize('execution_group_get', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.ExecutionGroup, force_get_data=True)
    @rest_decorators.all_tenants
    def get(self, group_id, _include=None, all_tenants=None):
        return get_storage_manager().get(
            models.ExecutionGroup,
            group_id,
            include=_include,
            all_tenants=all_tenants,
        )

    @authorize('execution_group_cancel')
    @rest_decorators.marshal_with(models.ExecutionGroup)
    def post(self, group_id, **kwargs):
        args = _ExecutionGroupActionArgs.parse_obj(request.json)
        action = args.action

        valid_actions = ['cancel', 'force-cancel', 'kill',
                         'resume', 'force-resume']

        if action not in valid_actions:
            raise BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        sm = get_storage_manager()
        group = sm.get(models.ExecutionGroup, group_id)
        if action in ('cancel', 'force-cancel', 'kill'):
            self._cancel_group(sm, group, action)
        if action in ('resume', 'force-resume'):
            self._resume_group(sm, group, action)
        return group

    def _cancel_group(self, sm, group, action):
        rm = get_resource_manager()
        with sm.transaction():
            to_cancel = []
            for exc in group.executions:
                if exc.status == ExecutionState.QUEUED:
                    exc.status = ExecutionState.CANCELLED
                elif exc.status in ExecutionState.END_STATES:
                    continue
                else:
                    to_cancel.append(exc.id)

        rm.cancel_execution(to_cancel,
                            force=action == 'force-cancel',
                            kill=action == 'kill')

    def _resume_group(self, sm, group, action):
        rm = get_resource_manager()
        force = action == 'force-resume'
        resume_states = {ExecutionState.FAILED, ExecutionState.CANCELLED}
        with sm.transaction():
            for exc in group.executions:
                if exc.status not in resume_states:
                    continue
                rm.reset_operations(exc, force=force)
                exc.status = ExecutionState.PENDING
                exc.ended_at = None
                exc.resumed = True
                sm.update(exc, modified_attrs=('status', 'ended_at', 'resume'))
            messages = group.start_executions(sm, rm)
        workflow_executor.execute_workflow(messages)

    @authorize('execution_group_update')
    @rest_decorators.marshal_with(models.ExecutionGroup)
    def patch(self, group_id, **kwargs):
        args = _ExecutionGroupUpdateArgs.parse_obj(request.json)
        sm = get_storage_manager()

        with sm.transaction():
            group = sm.get(models.ExecutionGroup, group_id)
            success_group_id = args.success_group_id
            if success_group_id:
                group.success_group = sm.get(
                    models.DeploymentGroup, success_group_id)
                self._add_deps_to_group(group)
            failure_group_id = args.failure_group_id
            if failure_group_id:
                group.failed_group = sm.get(
                    models.DeploymentGroup, failure_group_id)
                self._add_deps_to_group(group, success=False)
            sm.update(group)
        return group

    def _add_deps_to_group(self, group, success=True):
        deployment_ids = (
            db.session.query(models.Execution._deployment_fk)
            .filter(models.Execution.execution_group_id == group.id)
            .filter(
                models.Execution.status == (
                    ExecutionState.TERMINATED if success
                    else ExecutionState.FAILED
                )
            )
            .all()
        )
        if success:
            target_group_id = group.success_group._storage_id
        else:
            target_group_id = group.failed_group._storage_id
        # low-level sqlalchemy core, to avoid having to fetch all the deps
        tb = models.Deployment.deployment_groups.property.secondary
        db.session.execute(
            insert(tb)
            .values([
                {
                    'deployment_group_id': target_group_id,
                    'deployment_id': dep_id
                } for dep_id, in deployment_ids
            ])
            .on_conflict_do_nothing()
        )
