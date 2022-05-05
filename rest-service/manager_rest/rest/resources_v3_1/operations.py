from datetime import datetime
from flask import request
from flask_restful.reqparse import Argument

from cloudify._compat import text_type
from cloudify import constants as common_constants
from cloudify.workflows import events as common_events, tasks
from cloudify.models_states import ExecutionState
from sqlalchemy.dialects.postgresql import JSON

from manager_rest import manager_exceptions
from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
    parse_datetime_string,
)
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate,
    detach_globals,
)
from manager_rest.storage import (
    get_storage_manager,
    models,
    db,
)
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import check_user_action_allowed
from manager_rest.execution_token import current_execution


class Operations(SecuredResource):
    @authorize('operations')
    @marshal_with(models.Operation)
    @paginate
    def get(self, _include=None, pagination=None, **kwargs):
        args = get_args_and_verify_arguments([
            Argument('graph_id', type=text_type, required=False),
            Argument('execution_id', type=text_type, required=False),
            Argument('state', type=text_type, required=False),
            Argument('skip_internal', type=bool, required=False),
        ])
        sm = get_storage_manager()
        graph_id = args.get('graph_id')
        exc_id = args.get('execution_id')
        state = args.get('state')
        skip_internal = args.get('skip_internal')

        filters = {}
        if graph_id and exc_id:
            raise manager_exceptions.BadParametersError(
                'Pass either graph_id or execution_id, not both')
        elif graph_id:
            filters['tasks_graph'] = sm.get(models.TasksGraph, graph_id)
        elif exc_id:
            execution = sm.get(models.Execution, exc_id)
            filters['_tasks_graph_fk'] = [
                tg._storage_id for tg in execution.tasks_graphs]
        else:
            raise manager_exceptions.BadParametersError(
                'Missing required param: graph_id or execution_id')
        if state is not None:
            filters['state'] = state
        if skip_internal:
            filters['type'] = ['SubgraphTask', 'RemoteWorkflowTask']

        return sm.list(
            models.Operation,
            filters=filters,
            pagination=pagination,
            include=_include,
        )

    @authorize('operations')
    def post(self, **kwargs):
        request_dict = get_json_and_verify_params({'action'})
        action = request_dict['action']
        if action == 'update-stored':
            self._update_stored_operations()
        return None, 204

    def _update_stored_operations(self):
        """Recompute operation inputs, for resumable ops of the given node

        For deployment_id's node_id's operation, find stored operations that
        weren't finished yet (so can be resumed), and update their inputs
        to match the inputs given in the node spec (ie. coming from the plan).

        This is useful in deployment-update, so that stored operations that
        are resumed after the update, use the already updated values.
        """
        deployment_id = request.json['deployment_id']
        if not deployment_id:
            return None, 204
        node_id = request.json['node_id']
        op_name = request.json['operation']

        sm = get_storage_manager()
        with sm.transaction():
            dep = sm.get(models.Deployment, deployment_id)
            node_id, new_inputs = self._new_operation_details(
                sm,
                dep,
                node_id,
                op_name,
                rel_index=request.json.get('rel_index'),
                key=request.json.get('key'),
            )
            for op in self._find_resumable_ops(sm, dep, node_id, op_name):
                self._update_operation_inputs(sm, op, new_inputs)

    def _new_operation_details(self, sm, deployment, node_id, operation_name,
                               rel_index=None, key=None):
        """Find the node_id and new inputs of the updated operation

        Note: the node_id might be different than the one we think we're
        updating, because if the operation is a target interface of a
        relationship, then we actually want the remote-side node of the rel.
        """
        node = sm.list(models.Node,
                       filters={'deployment': deployment, 'id': node_id})[0]
        if rel_index is not None:
            rel = node.relationships[rel_index]
            if key == 'target_operations':
                node_id = rel['target_id']
            operation = rel[key].get(operation_name, {})
        else:
            operation = node.operations.get(operation_name, {})
        return node_id, operation.get('inputs')

    def _find_resumable_ops(self, sm, deployment, node_id, operation_name):
        executions = sm.list(models.Execution, filters={
            'deployment': deployment,
            'status': [
                ExecutionState.PENDING,
                ExecutionState.STARTED,
                ExecutionState.CANCELLED,
                ExecutionState.FAILED
            ]
        }, get_all_results=True)
        if not executions:
            return
        graphs = sm.list(models.TasksGraph, filters={
            'execution_id': [e.id for e in executions]
        }, get_all_results=True)

        def _filter_operation(column):
            # path in the parameters dict that stores the node name
            node_name_path = ('task_kwargs', 'kwargs',
                              '__cloudify_context', 'node_name')
            # ..and the operation interface name,
            # eg. cloudify.interfaces.lifecycle.create
            # (NOT eg. script.runner.tasks.run)
            operation_name_path = ('task_kwargs', 'kwargs',
                                   '__cloudify_context', 'operation', 'name')
            # this will use postgres' json operators
            json_column = db.cast(column, JSON)
            return db.and_(
                json_column[node_name_path].astext == node_id,
                json_column[operation_name_path].astext == operation_name
            )

        return sm.list(models.Operation, filters={
            'parameters': _filter_operation,
            '_tasks_graph_fk': [tg._storage_id for tg in graphs],
            'state': [tasks.TASK_RESCHEDULED,
                      tasks.TASK_FAILED,
                      tasks.TASK_PENDING]
        }, get_all_results=True)

    def _update_operation_inputs(self, sm, operation, new_inputs):
        try:
            operation.parameters['task_kwargs']['kwargs'].update(new_inputs)
            operation.parameters['task_kwargs']['kwargs'][
                '__cloudify_context']['has_intrinsic_functions'] = True
        except KeyError:
            return
        sm.update(operation, modified_attrs=['parameters'])


class OperationsId(SecuredResource):
    @authorize('operations')
    @marshal_with(models.Operation)
    def get(self, operation_id, **kwargs):
        return get_storage_manager().get(models.Operation, operation_id)

    @authorize('operations')
    @marshal_with(models.Operation)
    def put(self, operation_id, **kwargs):
        params = get_json_and_verify_params({
            'name': {'type': text_type, 'required': True},
            'graph_id': {'type': text_type, 'required': True},
            'dependencies': {'type': list, 'required': True},
            'parameters': {'type': dict},
            'type': {'type': text_type}
        })
        operation = get_resource_manager().create_operation(
            operation_id,
            name=params['name'],
            graph_id=params['graph_id'],
            dependencies=params['dependencies'],
            type=params['type'],
            parameters=params['parameters']
        )
        return operation, 201

    @authorize('operations', allow_if_execution=True)
    @detach_globals
    def patch(self, operation_id, **kwargs):
        request_dict = get_json_and_verify_params({
            'state': {'type': text_type},
            'result': {'optional': True},
            'exception': {'optional': True},
            'exception_causes': {'optional': True},
        })
        sm = get_storage_manager()
        with sm.transaction():
            instance = sm.get(models.Operation, operation_id, locking=True)
            old_state = instance.state
            instance.state = request_dict.get('state', instance.state)
            if instance.state == common_constants.TASK_SUCCEEDED:
                self._on_task_success(sm, instance)
            self._insert_event(
                instance,
                request_dict.get('result'),
                request_dict.get('exception'),
                request_dict.get('exception_causes')
            )
            if not instance.is_nop and \
                    old_state not in common_constants.TERMINATED_STATES and \
                    instance.state in common_constants.TERMINATED_STATES:
                self._modify_execution_operations_counts(instance, 1)
            sm.update(instance, modified_attrs=('state',))
        return {}, 200

    def _on_task_success(self, sm, operation):
        handler = getattr(self, f'_on_success_{operation.type}', None)
        if handler:
            handler(sm, operation)

    def _on_success_SetNodeInstanceStateTask(self, sm, operation):
        required_permission = 'node_instance_update'
        tenant_name = current_execution.tenant.name
        check_user_action_allowed(required_permission,
                                  tenant_name=tenant_name)
        try:
            kwargs = operation.parameters['task_kwargs']
            node_instance_id = kwargs['node_instance_id']
            state = kwargs['state']
        except KeyError:
            return
        node_instance = sm.get(
            models.NodeInstance, node_instance_id, locking=True)
        if node_instance.system_properties is None:
            node_instance.system_properties = {}
        if state == 'configured':
            node_instance.system_properties.setdefault(
                'configuration_drift', {
                    'ok': True,
                    'result': None,
                    'task': None,
                    'timestamp': datetime.utcnow().isoformat(),
                })
        if state == 'started':
            node_instance.system_properties.setdefault(
                'previous_status', None)
            node_instance.system_properties.setdefault(
                'status', {
                    'ok': True,
                    'result': None,
                    'task': None,
                    'timestamp': datetime.utcnow().isoformat(),
                })
        node_instance.state = state
        sm.update(node_instance, modified_attrs=('state', 'system_properties'))

    def _on_success_SendNodeEventTask(self, sm, operation):
        try:
            kwargs = operation.parameters['task_kwargs']
        except KeyError:
            return
        db.session.execute(models.Event.__table__.insert().values(
            timestamp=datetime.utcnow(),
            reported_timestamp=datetime.utcnow(),
            event_type='workflow_node_event',
            message=kwargs['event'],
            message_code=None,
            operation=None,
            node_id=kwargs['node_instance_id'],
            _execution_fk=current_execution._storage_id,
            _tenant_id=current_execution._tenant_id,
            _creator_id=current_execution._creator_id,
            visibility=current_execution.visibility,
        ))

    def _insert_event(self, operation, result=None, exception=None,
                      exception_causes=None):
        if operation.type not in ('RemoteWorkflowTask', 'SubgraphTask'):
            return
        if not current_execution:
            return
        try:
            context = operation.parameters['task_kwargs']['kwargs'][
                '__cloudify_context']
        except (KeyError, TypeError):
            context = {}
        if exception is not None:
            operation.parameters.setdefault('error', str(exception))
        current_retries = operation.parameters.get('current_retries') or 0
        total_retries = operation.parameters.get('total_retries') or 0

        try:
            message = common_events.format_event_message(
                operation.name,
                operation.type,
                operation.state,
                result,
                exception,
                current_retries,
                total_retries,
            )
            event_type = common_events.get_event_type(operation.state)
        except RuntimeError:
            return

        db.session.execute(models.Event.__table__.insert().values(
            timestamp=datetime.utcnow(),
            reported_timestamp=datetime.utcnow(),
            event_type=event_type,
            message=message,
            message_code=None,
            operation=context.get('operation', {}).get('name'),
            node_id=context.get('node_id'),
            source_id=context.get('source_id'),
            target_id=context.get('target_id'),
            error_causes=exception_causes,
            _execution_fk=current_execution._storage_id,
            _tenant_id=current_execution._tenant_id,
            _creator_id=current_execution._creator_id,
            visibility=current_execution.visibility,
        ))

    def _modify_execution_operations_counts(self, operation, finished_delta,
                                            total_delta=0):
        """Increase finished_operations for this operation's execution

        This is a separate sql-level update query, rather than ORM-level
        calls, for performance: the operation state-update call is on
        the critical path for all operations in a workflow; this saves
        about 3ms over the ORM approach (which requires fetching the
        execution; more if the DB is not local).
        """
        exc_table = models.Execution.__table__
        tg_table = models.TasksGraph.__table__
        values = {}
        if finished_delta:
            values['finished_operations'] =\
                exc_table.c.finished_operations + finished_delta
        if total_delta:
            values['total_operations'] =\
                exc_table.c.total_operations + total_delta
        db.session.execute(
            exc_table.update()
            .where(db.and_(
                tg_table.c._execution_fk == exc_table.c._storage_id,
                tg_table.c._storage_id == operation._tasks_graph_fk,
            ))
            .values(**values)
        )

    @authorize('operations')
    @marshal_with(models.Operation)
    def delete(self, operation_id, **kwargs):
        sm = get_storage_manager()
        with sm.transaction():
            instance = sm.get(models.Operation, operation_id, locking=True)
            if not instance.is_nop:
                finished_delta = (
                    -1
                    if instance.state in common_constants.TERMINATED_STATES
                    else 0
                )
                self._modify_execution_operations_counts(
                    instance, finished_delta, total_delta=-1)
            sm.delete(instance)
        return instance, 200


class TasksGraphs(SecuredResource):
    @authorize('operations')
    @marshal_with(models.TasksGraph)
    @paginate
    def get(self, _include=None, pagination=None, **kwargs):
        args = get_args_and_verify_arguments([
            Argument('execution_id', type=text_type, required=True),
            Argument('name', type=text_type, required=False)
        ])
        sm = get_storage_manager()
        execution_id = args.get('execution_id')
        name = args.get('name')
        execution = sm.get(models.Execution, execution_id)
        filters = {'execution': execution}
        if name:
            filters['name'] = name
        return sm.list(
            models.TasksGraph,
            filters=filters,
            pagination=pagination,
            include=_include,
        )


class TasksGraphsId(SecuredResource):
    @authorize('operations')
    @marshal_with(models.TasksGraph)
    def post(self, **kwargs):
        params = get_json_and_verify_params({
            'name': {'type': text_type},
            'execution_id': {'type': text_type},
            'operations': {'optional': True},
            'created_at': {'optional': True},
            'graph_id': {'optional': True},
        })
        created_at = params.get('created_at')
        operations = params.get('operations', [])
        if params.get('graph_id'):
            check_user_action_allowed('set_execution_details')
        if created_at or any(op.get('created_at') for op in operations):
            check_user_action_allowed('set_timestamp')
            created_at = parse_datetime_string(params.get('created_at'))
            for op in operations:
                if op.get('created_at'):
                    op['created_at'] = parse_datetime_string(op['created_at'])
        sm = get_storage_manager()
        with sm.transaction():
            tasks_graph = get_resource_manager().create_tasks_graph(
                name=params['name'],
                execution_id=params['execution_id'],
                operations=params.get('operations', []),
                created_at=created_at,
                graph_id=params.get('graph_id')
            )
        return tasks_graph, 201

    @authorize('operations')
    @marshal_with(models.TasksGraph)
    def patch(self, tasks_graph_id, **kwargs):
        request_dict = get_json_and_verify_params(
            {'state': {'type': text_type}}
        )
        sm = get_storage_manager()
        instance = sm.get(models.TasksGraph, tasks_graph_id, locking=True)
        instance.state = request_dict.get('state', instance.state)
        return sm.update(instance)
