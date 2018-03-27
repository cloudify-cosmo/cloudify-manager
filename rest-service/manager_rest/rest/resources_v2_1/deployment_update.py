#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from os.path import join
from shutil import copytree, rmtree

from flask import request
from flask_restful_swagger import swagger

from manager_rest.security import SecuredResource
from manager_rest import manager_exceptions, config
from manager_rest.security.authorization import authorize
from manager_rest.deployment_update.constants import PHASES
from manager_rest.storage import models, get_storage_manager
from manager_rest.utils import create_filter_params_list_description
from manager_rest.upload_manager import \
    UploadedBlueprintsDeploymentUpdateManager
from manager_rest.deployment_update.manager import \
    get_deployment_updates_manager
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)

from .. import rest_decorators
from ..rest_utils import verify_and_convert_bool


class DeploymentUpdate(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def post(self, id, phase):
        """
        Provides support for two phases of deployment update. The phase is
        chosen according to the phase arg, and the id is used by this step.

        In the first phase the deployment update is
        1. Staged (from a new blueprint)
        2. The steps are extracted and saved onto the data model.
        3. The data storage is manipulated according to the
        addition/modification steps.
        4. The update workflow is run, executing any lifecycles of add/removed
        nodes or relationships.

        The second step finalizes the commit by manipulating the data model
        according to any removal steps.

        In order
        :param id: for the initiate step it's the deployment_id, and for the
        finalize step it's the update_id
        :param phase: initiate or finalize
        :return: update response
        """
        if phase == PHASES.INITIAL:
            return self._commit(id)
        elif phase == PHASES.FINAL:
            return get_deployment_updates_manager().finalize_commit(id)

    @rest_decorators.exceptions_handled
    @authorize('deployment_update_create')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def put(self, id, phase):
        """
        Supports a newer form of deployment update, when the blueprint for the
        update has already been uploaded to the manager.
        The request should contain a blueprint id (instead of a new blueprint
        to upload)
        The inputs are now supplied as a json dict - just like in deployment
        creation.

        Note: the blueprint id of the deployment will be updated to the given
        blueprint id.
        """
        request_json = request.json
        manager, skip_install, skip_uninstall, workflow_id = \
            self._get_params_and_validate(id, request_json)
        inputs = request_json.get('inputs', {})
        blueprint_id = request_json.get('blueprint_id')
        if not isinstance(inputs, dict):
            raise manager_exceptions.BadParametersError(
                'parameter `inputs` must be of type `dict`')
        if not blueprint_id:
            raise manager_exceptions.BadParametersError(
                'Must supply the parameter `blueprint_id`')

        sm = get_storage_manager()
        blueprint = sm.get(models.Blueprint, blueprint_id)
        blueprint_dir_abs = join(config.instance.file_server_root,
                                 FILE_SERVER_BLUEPRINTS_FOLDER,
                                 blueprint.tenant_name,
                                 blueprint_id)
        deployment = sm.get(models.Deployment, id)
        deployment_dir = join(FILE_SERVER_DEPLOYMENTS_FOLDER,
                              deployment.tenant_name,
                              id)
        dep_dir_abs = join(config.instance.file_server_root, deployment_dir)
        rmtree(dep_dir_abs, ignore_errors=True)
        copytree(blueprint_dir_abs, dep_dir_abs)
        file_name = blueprint.main_file_name
        deployment.blueprint = blueprint
        sm.update(deployment)
        deployment_update = manager.stage_deployment_update(id,
                                                            deployment_dir,
                                                            file_name,
                                                            inputs)
        manager.extract_steps_from_deployment_update(deployment_update)
        return manager.commit_deployment_update(deployment_update,
                                                skip_install=skip_install,
                                                skip_uninstall=skip_uninstall,
                                                workflow_id=workflow_id)

    def _commit(self, deployment_id):
        request_json = request.args
        manager, skip_install, skip_uninstall, workflow_id = \
            self._get_params_and_validate(deployment_id, request_json)

        deployment_update, _ = \
            UploadedBlueprintsDeploymentUpdateManager(). \
            receive_uploaded_data(deployment_id)

        manager.extract_steps_from_deployment_update(deployment_update)

        return manager.commit_deployment_update(
            deployment_update,
            skip_install=skip_install,
            skip_uninstall=skip_uninstall,
            workflow_id=workflow_id)

    @staticmethod
    def _get_params_and_validate(deployment_id, request_json):
        manager = get_deployment_updates_manager()
        skip_install = verify_and_convert_bool(
            'skip_install',
            request_json.get('skip_install', 'false'))
        skip_uninstall = verify_and_convert_bool(
            'skip_uninstall',
            request_json.get('skip_uninstall', 'false'))
        force = verify_and_convert_bool(
            'force',
            request_json.get('force', 'false'))
        workflow_id = request_json.get('workflow_id', None)

        if (skip_install or skip_uninstall) and workflow_id:
            raise manager_exceptions.BadParametersError(
                'skip_install has been set to {0}, skip uninstall has been'
                ' set to {1}, and a custom workflow {2} has been set to '
                'replace "update". However, skip_install and '
                'skip_uninstall are mutually exclusive with a custom '
                'workflow'.format(skip_install,
                                  skip_uninstall,
                                  workflow_id))
        manager.validate_no_active_updates_per_deployment(
            deployment_id=deployment_id, force=force)
        return manager, skip_install, skip_uninstall, workflow_id


class DeploymentUpdateId(SecuredResource):
    @swagger.operation(
            responseClass=models.DeploymentUpdate,
            nickname="DeploymentUpdate",
            notes='Return a single deployment update',
            parameters=create_filter_params_list_description(
                models.DeploymentUpdate.response_fields, 'deployment update'
            )
    )
    @rest_decorators.exceptions_handled
    @authorize('deployment_update_get')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    def get(self, update_id):
        return \
            get_deployment_updates_manager().get_deployment_update(update_id)


class DeploymentUpdates(SecuredResource):
    @swagger.operation(
            responseClass='List[{0}]'.format(
                    models.DeploymentUpdate.__name__),
            nickname="listDeploymentUpdates",
            notes='Returns a list of deployment updates',
            parameters=create_filter_params_list_description(
                    models.DeploymentUpdate.response_fields,
                    'deployment updates'
            )
    )
    @rest_decorators.exceptions_handled
    @authorize('deployment_update_list')
    @rest_decorators.marshal_with(models.DeploymentUpdate)
    @rest_decorators.create_filters(models.DeploymentUpdate)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.DeploymentUpdate)
    def get(self, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List deployment modification stages
        """
        deployment_updates = \
            get_deployment_updates_manager().list_deployment_updates(
                    include=_include, filters=filters, pagination=pagination,
                    sort=sort, **kwargs)
        return deployment_updates
