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
import zipfile
import urllib
import shutil
import sys

from flask.ext.restful_swagger import swagger
from flask_securest.rest_security import SecuredResource
from flask import request
from flask_securest import rest_security
from manager_rest.deployment_update.constants import PHASES

from manager_rest.files import UploadedDataManager
from manager_rest.resources import (marshal_with,
                                    exceptions_handled,
                                    verify_json_content_type,
                                    verify_and_convert_bool,
                                    CONVENTION_APPLICATION_BLUEPRINT_FILE)
from manager_rest import models
from manager_rest import resources
from manager_rest import resources_v2
from manager_rest import responses_v2_1
from manager_rest import config
from manager_rest import archiving
from manager_rest import manager_exceptions
from manager_rest import utils
from manager_rest.blueprints_manager import get_blueprints_manager
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED)
from manager_rest.maintenance import (get_maintenance_file_path,
                                      prepare_maintenance_dict,
                                      get_running_executions)
from manager_rest.manager_exceptions import BadParametersError
from deployment_update.manager import get_deployment_updates_manager
from manager_rest.resources_v2 import create_filters, paginate, sortable
from manager_rest.utils import create_filter_params_list_description


def override_marshal_with(f, model):
    @exceptions_handled
    @marshal_with(model)
    def wrapper(*args, **kwargs):
        with resources.skip_nested_marshalling():
            return f(*args, **kwargs)
    return wrapper


class UploadedBlueprintsDeploymentUpdateManager(UploadedDataManager):

    def _get_kind(self):
        return 'deployment'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return config.instance().file_server_deployments_folder

    def _get_archive_type(self, archive_path):
        return archiving.get_archive_type(archive_path)

    def _prepare_and_process_doc(self,
                                 data_id,
                                 file_server_root,
                                 archive_target_path,
                                 additional_inputs=None):
        application_dir = self._extract_file_to_file_server(
            archive_target_path,
            file_server_root
        )
        return self._prepare_and_submit_blueprint(
                file_server_root,
                application_dir,
                data_id,
                additional_inputs), archive_target_path

    def _move_archive_to_uploaded_dir(self, *args, **kwargs):
        pass

    @classmethod
    def _prepare_and_submit_blueprint(cls,
                                      file_server_root,
                                      app_dir,
                                      deployment_id,
                                      additional_inputs=None):

        app_dir, app_file_name = \
            cls._extract_application_file(file_server_root, app_dir)

        # add to deployment update manager (will also dsl_parse it)
        try:
            cls._process_plugins(file_server_root, app_dir, deployment_id)
            update = get_deployment_updates_manager().stage_deployment_update(
                    deployment_id,
                    app_dir,
                    app_file_name,
                    additional_inputs=additional_inputs or {}
                )

            # Moving the contents of the app dir to the dest dir, while
            # overwriting any file encountered

            # create the destination root dir
            file_server_deployment_root = \
                os.path.join(file_server_root,
                             config.instance().file_server_deployments_folder,
                             deployment_id)

            app_root_dir = os.path.join(file_server_root, app_dir)

            for root, dirs, files in os.walk(app_root_dir):
                # Creates a corresponding dir structure in the deployment dir
                dest_rel_dir = os.path.relpath(root, app_root_dir)
                dest_dir = os.path.abspath(
                        os.path.join(file_server_deployment_root,
                                     dest_rel_dir))
                utils.mkdirs(dest_dir)

                # Calculate source dir
                source_dir = os.path.join(file_server_root, app_dir, root)

                for file_name in files:
                    source_file = os.path.join(source_dir, file_name)
                    relative_dest_path = os.path.relpath(source_file,
                                                         app_root_dir)
                    dest_file = os.path.join(file_server_deployment_root,
                                             relative_dest_path)
                    shutil.copy(source_file, dest_file)

            return update
        except Exception:
            shutil.rmtree(os.path.join(file_server_root, app_dir))
            raise

    @classmethod
    def _extract_application_file(cls, file_server_root, application_dir):

        full_application_dir = os.path.join(file_server_root, application_dir)

        if 'application_file_name' in request.args:
            application_file_name = urllib.unquote(
                    request.args['application_file_name']).decode('utf-8')
            application_file = os.path.join(full_application_dir,
                                            application_file_name)
            if not os.path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                        '{0} does not exist in the application '
                        'directory'.format(application_file_name)
                )
        else:
            application_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE
            application_file = os.path.join(full_application_dir,
                                            application_file_name)
            if not os.path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                        'application directory is missing blueprint.yaml and '
                        'application_file_name query parameter was not passed')

        # return relative path from the file server root since this path
        # is appended to the file server base uri
        return application_dir, application_file_name

    @classmethod
    def _process_plugins(cls, file_server_root, app_dir, deployment_id):
        plugins_directory = os.path.join(file_server_root, app_dir, 'plugins')
        if not os.path.isdir(plugins_directory):
            return
        plugins = [os.path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if os.path.isdir(os.path.join(plugins_directory,
                                                 directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(os.path.basename(plugin_dir))
            target_zip_path = os.path.join(file_server_root, app_dir,
                                           'plugins', final_zip_name)
            cls._zip_dir(plugin_dir, target_zip_path)

    @classmethod
    def _zip_dir(cls, dir_to_zip, target_zip_path):
        zipf = zipfile.ZipFile(target_zip_path, 'w', zipfile.ZIP_DEFLATED)
        try:
            plugin_dir_base_name = os.path.basename(dir_to_zip)
            rootlen = len(dir_to_zip) - len(plugin_dir_base_name)
            for base, dirs, files in os.walk(dir_to_zip):
                for entry in files:
                    fn = os.path.join(base, entry)
                    zipf.write(fn, fn[rootlen:])
        finally:
            zipf.close()


class MaintenanceMode(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
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
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def post(self, maintenance_action, **_):
        maintenance_file_path = get_maintenance_file_path()

        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                state = utils.read_json_file(maintenance_file_path)
                return state, 304

            now = utils.get_formatted_timestamp()

            try:
                user = rest_security.get_username()
            except AttributeError:
                user = ''

            remaining_executions = get_running_executions()
            status = MAINTENANCE_MODE_ACTIVATING \
                if remaining_executions else MAINTENANCE_MODE_ACTIVATED
            activated_at = '' if remaining_executions else now
            utils.mkdirs(config.instance().maintenance_folder)
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
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
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

        manager.extract_steps_from_deployment_update(
            deployment_update.id)

        return manager.commit_deployment_update(
            deployment_update.id,
            skip_install=skip_install,
            skip_uninstall=skip_uninstall,
            workflow_id=workflow_id)


class DeploymentUpdateId(SecuredResource):
    @swagger.operation(
            responseClass=responses_v2_1.DeploymentUpdate,
            nickname="DeploymentUpdate",
            notes='Return a single deployment update',
            parameters=create_filter_params_list_description(
                    models.DeploymentUpdate.fields, 'deployment update'
            )
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def get(self, update_id):
        return \
            get_deployment_updates_manager().get_deployment_update(update_id)


class DeploymentUpdates(SecuredResource):
    @swagger.operation(
            responseClass='List[{0}]'.format(
                    responses_v2_1.DeploymentUpdate.__name__),
            nickname="listDeploymentUpdates",
            notes='Returns a list of deployment updates',
            parameters=create_filter_params_list_description(
                    models.DeploymentUpdate.fields,
                    'deployment updates'
            )
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    @create_filters(models.DeploymentUpdate.fields)
    @paginate
    @sortable
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


class Deployments(resources_v2.Deployments):

    get = override_marshal_with(resources_v2.Deployments.get,
                                responses_v2_1.Deployment)


class DeploymentsId(resources.DeploymentsId):

    get = override_marshal_with(resources.DeploymentsId.get,
                                responses_v2_1.Deployment)

    put = override_marshal_with(resources.DeploymentsId.put,
                                responses_v2_1.Deployment)

    delete = override_marshal_with(resources.DeploymentsId.delete,
                                   responses_v2_1.Deployment)


class Nodes(resources_v2.Nodes):

    get = override_marshal_with(resources_v2.Nodes.get,
                                responses_v2_1.Node)


class NodeInstances(resources_v2.NodeInstances):

    get = override_marshal_with(resources_v2.NodeInstances.get,
                                responses_v2_1.NodeInstance)


class NodeInstancesId(resources.NodeInstancesId):

    get = override_marshal_with(resources.NodeInstancesId.get,
                                responses_v2_1.NodeInstance)

    patch = override_marshal_with(resources.NodeInstancesId.patch,
                                  responses_v2_1.NodeInstance)


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=responses_v2_1.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        verify_json_content_type()
        request_json = request.json
        force = verify_and_convert_bool('force', request_json.get('force',
                                                                  False))
        try:
            return get_blueprints_manager().remove_plugin(plugin_id=plugin_id,
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
