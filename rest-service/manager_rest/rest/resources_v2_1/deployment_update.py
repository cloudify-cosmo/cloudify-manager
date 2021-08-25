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
from os.path import join
from shutil import copytree, rmtree

from flask import request
from flask_restful_swagger import swagger

from cloudify._compat import text_type

from manager_rest.security import SecuredResource
from manager_rest import manager_exceptions, config
from manager_rest.security.authorization import authorize
from manager_rest.deployment_update.constants import (
    PHASES,
    STATES
)
from manager_rest.execution_token import current_execution
from manager_rest.storage import models, get_storage_manager
from manager_rest.deployment_update.manager import \
    get_deployment_updates_manager
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)
from manager_rest.utils import (create_filter_params_list_description,
                                current_tenant)

from .. import rest_decorators
from ..rest_utils import verify_and_convert_bool, get_json_and_verify_params


class DeploymentUpdate(SecuredResource):
    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def post(self, id, phase):
        """
        Provides support for two phases of deployment update. The phase is
        chosen according to the phase arg, and the id is used by this step.

        In the first phase ("initiate") the deployment update is:

        1. Staged (from a new blueprint)
        2. The steps are extracted and saved onto the data model.
        3. The data storage is manipulated according to the
           addition/modification steps.
        4. The update workflow is run, executing any lifecycles of add/removed
           nodes or relationships.

        Prerequisites:

        * The blueprint for the deployment update has already been uploaded
          to the manager.
        * The request should contain a blueprint id.
        * The inputs are supplied as a json dict - just like in deployment
          creation.

        Note: the blueprint id of the deployment will be updated to the given
        blueprint id.

        The second step ("finalize") finalizes the commit by manipulating the
        data model according to any removal steps.

        In order
        :param id: for the initiate step it's the deployment_id, and for the
        finalize step it's the update_id
        :param phase: initiate or finalize
        :return: update response
        """
        if phase == PHASES.INITIAL:
            return self._initiate(id)
        if phase == PHASES.FINAL:
            return get_deployment_updates_manager().finalize_commit(id)

    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def put(self, id, phase):
        """DEPRECATED.  Please use POST method instead.

        This method is implemented for backward-compatibility only.
        """
        return self._initiate(id)

    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def _initiate(self, deployment_id):
        manager, skip_install, skip_uninstall, skip_reinstall, workflow_id, \
            ignore_failure, install_first, preview, update_plugins, \
            runtime_eval, auto_correct_args, reevaluate_active_statuses, \
            force = \
            self._parse_args(deployment_id, request.json)
        blueprint, inputs, reinstall_list = \
            self._get_and_validate_blueprint_and_inputs(deployment_id,
                                                        request.json)
        blueprint_dir_abs = _get_plugin_update_blueprint_abs_path(
            config.instance.file_server_root, blueprint)
        deployment_dir = join(FILE_SERVER_DEPLOYMENTS_FOLDER,
                              current_tenant.name,
                              deployment_id,
                              'updated_blueprint')
        dep_dir_abs = join(config.instance.file_server_root, deployment_dir)
        rmtree(dep_dir_abs, ignore_errors=True)
        copytree(blueprint_dir_abs, dep_dir_abs)
        file_name = blueprint.main_file_name
        try:
            deployment_update = manager.stage_deployment_update(
                deployment_id, deployment_dir, file_name, inputs,
                blueprint.id, preview,
                runtime_only_evaluation=runtime_eval,
                auto_correct_types=auto_correct_args,
                reevaluate_active_statuses=reevaluate_active_statuses)
        finally:
            rmtree(dep_dir_abs, ignore_errors=True)

        manager.extract_steps_from_deployment_update(deployment_update)
        return manager.commit_deployment_update(deployment_update,
                                                skip_install,
                                                skip_uninstall,
                                                skip_reinstall,
                                                workflow_id,
                                                ignore_failure,
                                                install_first,
                                                reinstall_list,
                                                update_plugins=update_plugins,
                                                force=force)

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
        runtime_only_evaluation = verify_and_convert_bool(
            'runtime_only_evaluation',
            request_json.get('runtime_only_evaluation', False)
        )
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
        manager = get_deployment_updates_manager(preview)
        return (manager,
                skip_install,
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


def _get_plugin_update_blueprint_abs_path(server_root, blueprint):
    def get_blueprint_abs_path(_blueprint):
        return join(server_root,
                    FILE_SERVER_BLUEPRINTS_FOLDER,
                    _blueprint.tenant_name,
                    _blueprint.id)
    if not blueprint.temp_of_plugins_update:
        return get_blueprint_abs_path(blueprint)
    original_blueprint = blueprint.temp_of_plugins_update[0].blueprint
    return get_blueprint_abs_path(original_blueprint)
