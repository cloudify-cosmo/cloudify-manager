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

import uuid

from flask import request
from flask_restful_swagger import swagger

from cloudify._compat import text_type

from manager_rest.security import SecuredResource
from manager_rest import manager_exceptions, workflow_executor
from manager_rest.security.authorization import authorize
from manager_rest.deployment_update.constants import (
    PHASES,
    STATES
)
from manager_rest.execution_token import current_execution
from manager_rest.storage import models, get_storage_manager, db
from manager_rest.deployment_update.manager import \
    get_deployment_updates_manager
from manager_rest.utils import create_filter_params_list_description

from manager_rest.resource_manager import get_resource_manager
from .. import rest_decorators
from ..rest_utils import verify_and_convert_bool, get_json_and_verify_params


class DeploymentUpdate(SecuredResource):
    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def post(self, id, phase):
        """Start a deployment-update

        This endpoint has two modes of operation: POST /initiate, which
        starts a dep-update; and POST /finalize, which currently does nothing,
        and only exists for backwards compatibility.
        """
        if phase == PHASES.INITIAL:
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
        skip_install, skip_uninstall, skip_reinstall, workflow_id, \
            ignore_failure, install_first, preview, update_plugins, \
            runtime_eval, auto_correct_args, reevaluate_active_statuses, \
            force = \
            self._parse_args(deployment_id, request.json)
        with sm.transaction():
            blueprint, inputs, reinstall_list = \
                self._get_and_validate_blueprint_and_inputs(deployment_id,
                                                            request.json)
            deployment = sm.get(models.Deployment, deployment_id)
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
                preview=preview,
                runtime_only_evaluation=runtime_eval,
                state=STATES.UPDATING,
            )
            execution_args = {
                'update_id': dep_up.id,
                'preview': preview,
                'ignore_failure': ignore_failure,
                'skip_install': skip_install,
                'skip_reinstall': skip_reinstall,
                'skip_uninstall': skip_uninstall,
                'workflow_id': workflow_id,
                'blueprint_id': blueprint.id,
                'inputs': inputs,
            }
            update_exec = models.Execution(
                deployment=deployment,
                workflow_id='csys_new_deployment_update',
                parameters=execution_args
            )
            sm.put(update_exec)
            dep_up.execution = update_exec
            sm.put(dep_up)
            dep_up.set_deployment(deployment)
            messages = rm.prepare_executions(
                [update_exec],
                allow_overlapping_running_wf=True,
                force=force,
            )
            if current_execution and \
                    current_execution.workflow_id == 'csys_update_deployment':
                # if we're created from a update_deployment workflow, join its
                # exec-groups, for easy tracking
                for exec_group in current_execution.execution_groups:
                    exec_group.executions.append(update_exec)
                db.session.commit()
        workflow_executor.execute_workflow(messages)
        return dep_up

    @staticmethod
    def _get_and_validate_blueprint_and_inputs(deployment_id, request_json):
        inputs = request_json.get('inputs', {})
        reinstall_list = request_json.get('reinstall_list', [])
        blueprint_id = request_json.get('blueprint_id')
        if not isinstance(inputs, dict):
            raise manager_exceptions.BadParametersError(
                'parameter `inputs` must be of type `dict`')
        if not isinstance(reinstall_list, list):
            raise manager_exceptions.BadParametersError(
                'parameter `reinstall_list` must be of type `list`')
        if not blueprint_id and not inputs:
            raise manager_exceptions.BadParametersError(
                'Must supply either the `blueprint_id` parameter, or new '
                'inputs, in order the perform a deployment update')
        if blueprint_id is None:
            deployment = get_storage_manager().get(models.Deployment,
                                                   deployment_id)
            blueprint = deployment.blueprint
        else:
            blueprint = get_storage_manager().get(models.Blueprint,
                                                  blueprint_id)
        return blueprint, inputs, reinstall_list

    @staticmethod
    def _parse_args(deployment_id, request_json, using_post_request=False):
        skip_install = verify_and_convert_bool(
            'skip_install',
            request_json.get('skip_install', False))
        skip_uninstall = verify_and_convert_bool(
            'skip_uninstall',
            request_json.get('skip_uninstall', False))
        skip_reinstall = verify_and_convert_bool(
            'skip_reinstall',
            request_json.get('skip_reinstall', using_post_request))
        ignore_failure = verify_and_convert_bool(
            'ignore_failure',
            request_json.get('ignore_failure', False))
        install_first = verify_and_convert_bool(
            'install_first',
            request_json.get('install_first', using_post_request))
        preview = not using_post_request and verify_and_convert_bool(
            'preview',
            request_json.get('preview', False))
        workflow_id = request_json.get('workflow_id', None)
        update_plugins = verify_and_convert_bool(
            'update_plugins',
            request_json.get('update_plugins', True))
        runtime_only_evaluation = request_json.get('runtime_only_evaluation')
        auto_correct_types = verify_and_convert_bool(
            'auto_correct_types',
            request_json.get('auto_correct_types', False)
        )
        reevaluate_active_statuses = verify_and_convert_bool(
            'reevaluate_active_statuses',
            request_json.get('reevaluate_active_statuses', False)
        )
        force = verify_and_convert_bool(
            'force',
            request_json.get('force', False)
        )
        return (skip_install,
                skip_uninstall,
                skip_reinstall,
                workflow_id,
                ignore_failure,
                install_first,
                preview,
                update_plugins,
                runtime_only_evaluation,
                auto_correct_types,
                reevaluate_active_statuses,
                force)


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
        return get_deployment_updates_manager().get_deployment_update(
            update_id,
            include=_include)

    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def put(self, update_id):
        params = get_json_and_verify_params({
            'deployment_id': {'type': text_type, 'required': True},
            'state': {'optional': True},
            'inputs': {'optional': True},
            'blueprint_id': {'optional': True}
        })
        sm = get_storage_manager()
        if not current_execution:
            raise manager_exceptions.ForbiddenError(
                'Deployment update objects can only be created by executions')

        with sm.transaction():
            dep = sm.get(models.Deployment, params['deployment_id'])
            dep_upd = sm.get(models.DeploymentUpdate, update_id,
                             fail_silently=True)
            if dep_upd is None:
                dep_upd = models.DeploymentUpdate(
                    id=update_id,
                    _execution_fk=current_execution._storage_id
                )
            dep_upd.state = params.get('state') or STATES.UPDATING
            dep_upd.new_inputs = params.get('inputs')
            if params.get('blueprint_id'):
                dep_upd.new_blueprint = sm.get(
                    models.Blueprint, params['blueprint_id'])
            dep_upd.set_deployment(dep)
            return dep_upd

    @authorize('deployment_update_update')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def patch(self, update_id):
        params = get_json_and_verify_params({
            'state': {'optional': True},
            'plan': {'optional': True},
            'steps': {'optional': True},
            'nodes': {'optional': True},
            'node_instances': {'optional': True},
        })
        sm = get_storage_manager()
        with sm.transaction():
            dep_upd = sm.get(models.DeploymentUpdate, update_id)
            if params.get('state'):
                dep_upd.state = params['state']
            if params.get('plan'):
                dep_upd.deployment_plan = params['plan']
            if params.get('steps'):
                for step_spec in params['steps']:
                    step = models.DeploymentUpdateStep(
                        id=str(uuid.uuid4()),
                        **step_spec
                    )
                    step.set_deployment_update(dep_upd)
            if params.get('nodes'):
                dep_upd.deployment_update_nodes = params['nodes']
            if params.get('node_instances'):
                dep_upd.deployment_update_node_instances = \
                    params['node_instances']
            return dep_upd


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
        deployment_updates = \
            get_deployment_updates_manager().list_deployment_updates(
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                substr_filters=search
            )
        return deployment_updates
