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
#
import os
import sys

from flask import request
from flask_security import current_user
from flask_restful_swagger import swagger

from manager_rest.deployment_update.constants import PHASES
from manager_rest import config
from manager_rest import manager_exceptions
from manager_rest import utils
from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.resource_manager import get_resource_manager
from manager_rest.app_logging import raise_unauthorized_user_error
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED)
from manager_rest.maintenance import (get_maintenance_file_path,
                                      prepare_maintenance_dict,
                                      get_running_executions)
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.utils import create_filter_params_list_description
from manager_rest.upload_manager import \
    UploadedBlueprintsDeploymentUpdateManager
from manager_rest.deployment_update.manager import \
    get_deployment_updates_manager
from .rest_utils import verify_and_convert_bool, get_json_and_verify_params
from .responses_v2_1 import MaintenanceMode as MaintenanceModeResponse
from . import rest_decorators, resources_v2


class MaintenanceMode(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def get(self, **_):
        maintenance_file_path = get_maintenance_file_path()
        if os.path.isfile(maintenance_file_path):
            state = utils.read_json_file(maintenance_file_path)

            if state['status'] == MAINTENANCE_MODE_ACTIVATED:
                return state
            if state['status'] == MAINTENANCE_MODE_ACTIVATING:
                running_executions = get_running_executions()

                # If there are no running executions,
                # maintenance mode would have been activated at the
                # maintenance handler hook (server.py)
                state['remaining_executions'] = running_executions
                return state
        else:
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)


class MaintenanceModeAction(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def post(self, maintenance_action, **_):
        if not current_user.is_admin:
            raise_unauthorized_user_error(
                '{0} does not have privileges to set maintenance mode'.format(
                    current_user))
        maintenance_file_path = get_maintenance_file_path()
        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                state = utils.read_json_file(maintenance_file_path)
                return state, 304
            now = utils.get_formatted_timestamp()
            try:
                user = current_user.username
            except AttributeError:
                user = ''
            remaining_executions = get_running_executions()
            status = MAINTENANCE_MODE_ACTIVATING \
                if remaining_executions else MAINTENANCE_MODE_ACTIVATED
            activated_at = '' if remaining_executions else now
            utils.mkdirs(config.instance.maintenance_folder)
            new_state = prepare_maintenance_dict(
                status=status,
                activation_requested_at=now,
                activated_at=activated_at,
                remaining_executions=remaining_executions,
                requested_by=user)
            utils.write_dict_to_json_file(maintenance_file_path, new_state)
            return new_state
        if maintenance_action == 'deactivate':
            if not os.path.isfile(maintenance_file_path):
                return prepare_maintenance_dict(
                        MAINTENANCE_MODE_DEACTIVATED), 304
            os.remove(maintenance_file_path)
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)
        valid_actions = ['activate', 'deactivate']
        raise BadParametersError(
                'Invalid action: {0}, Valid action '
                'values are: {1}'.format(maintenance_action, valid_actions))


class DeploymentUpdate(SecuredResource):
    @rest_decorators.exceptions_handled
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

    @staticmethod
    def _commit(deployment_id):
        manager = get_deployment_updates_manager()
        request_json = request.args
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

        deployment_update, _ = \
            UploadedBlueprintsDeploymentUpdateManager(). \
            receive_uploaded_data(deployment_id)

        manager.extract_steps_from_deployment_update(deployment_update)

        return manager.commit_deployment_update(
            deployment_update,
            skip_install=skip_install,
            skip_uninstall=skip_uninstall,
            workflow_id=workflow_id)


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


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=models.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        request_dict = get_json_and_verify_params()
        force = verify_and_convert_bool(
            'force', request_dict.get('force', False)
        )
        try:
            return get_resource_manager().remove_plugin(plugin_id=plugin_id,
                                                        force=force)
        except manager_exceptions.ManagerException:
            raise
        except manager_exceptions.ExecutionTimeout:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationTimeout(
                'Timed out during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb
        except Exception:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationError(
                'Failed during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb


def write_maintenance_state(state):
    maintenance_file_path = get_maintenance_file_path()
    with open(maintenance_file_path, 'w') as f:
        f.write(state)
