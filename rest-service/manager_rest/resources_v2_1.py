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

from flask.ext.restful_swagger import swagger

from flask_securest.rest_security import SecuredResource
from flask import request

from manager_rest.files import UploadedDataManager
from manager_rest.resources import (marshal_with,
                                    exceptions_handled,
                                    verify_json_content_type,
                                    CONVENTION_APPLICATION_BLUEPRINT_FILE)

from manager_rest import models
from manager_rest import responses_v2_1
from manager_rest import config
from manager_rest import archiving
from manager_rest import manager_exceptions
from manager_rest.blueprints_manager import (get_blueprints_manager,
                                             DslParseException)
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVE,
                                    MAINTENANCE_MODE_STATUS_FILE,
                                    ACTIVATING_MAINTENANCE_MODE,
                                    NOT_IN_MAINTENANCE_MODE)

from manager_rest import utils
from deployment_update.manager import get_deployment_updates_manager
from manager_rest.resources_v2 import create_filters, paginate, sortable
from manager_rest.utils import create_filter_params_list_description


class UploadedBlueprintsDeploymentUpdateManager(UploadedDataManager):

    def _get_kind(self):
        return 'deployment'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return config.instance().file_server_deployments_folder

    def _get_archive_type(self, archive_path):
        return archiving.get_archive_type(archive_path)

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path):
        application_dir = self._extract_file_to_file_server(
            archive_target_path,
            file_server_root
        )
        return self._prepare_and_submit_blueprint(file_server_root,
                                                  application_dir,
                                                  data_id), archive_target_path

    def _move_archive_to_uploaded_dir(self, *args, **kwargs):
        pass

    @classmethod
    def _prepare_and_submit_blueprint(cls, file_server_root,
                                      app_dir,
                                      deployment_id):

        app_dir, app_file_name = \
            cls._extract_application_file(file_server_root, app_dir)

        # add to deployment update manager (will also dsl_parse it)
        try:
            cls._process_plugins(file_server_root, deployment_id)
            update = get_deployment_updates_manager().stage_deployment_update(
                    deployment_id,
                    app_dir,
                    app_file_name,
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
                os.makedirs(dest_dir)

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
        except DslParseException, ex:
            shutil.rmtree(os.path.join(file_server_root, app_dir))
            raise manager_exceptions.InvalidBlueprintError(
                    'Invalid deployment update - {0}'.format(ex.message))

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
    def _process_plugins(cls, file_server_root, blueprint_id):
        plugins_directory = \
            os.path.join(file_server_root,
                         "blueprints", blueprint_id, "plugins")
        if not os.path.isdir(plugins_directory):
            return
        plugins = [os.path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if os.path.isdir(os.path.join(plugins_directory,
                                                 directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(os.path.basename(plugin_dir))
            target_zip_path = os.path.join(file_server_root,
                                           "blueprints", blueprint_id,
                                           "plugins", final_zip_name)
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
    def get(self, **kwargs):
        maintenance_file_path = get_maintenance_file_path()
        if os.path.isfile(maintenance_file_path):
            with open(maintenance_file_path, 'r') as f:
                status = f.read()

            if status == MAINTENANCE_MODE_ACTIVE:
                return {'status': MAINTENANCE_MODE_ACTIVE}
            if status == ACTIVATING_MAINTENANCE_MODE:
                executions = get_blueprints_manager().executions_list(
                        is_include_system_workflows=True).items
                for execution in executions:
                    if execution.status not in models.Execution.END_STATES:
                        return {'status': ACTIVATING_MAINTENANCE_MODE}

                write_maintenance_state(MAINTENANCE_MODE_ACTIVE)
                return {'status': MAINTENANCE_MODE_ACTIVE}
        else:
            return {'status': NOT_IN_MAINTENANCE_MODE}


class MaintenanceModeAction(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def post(self, maintenance_action, **kwargs):
        maintenance_file_path = get_maintenance_file_path()

        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                return {'status': MAINTENANCE_MODE_ACTIVE}, 304

            utils.mkdirs(config.instance().maintenance_folder)
            write_maintenance_state(ACTIVATING_MAINTENANCE_MODE)

            return {'status': ACTIVATING_MAINTENANCE_MODE}

        if maintenance_action == 'deactivate':
            if not os.path.isfile(maintenance_file_path):
                return {'status': NOT_IN_MAINTENANCE_MODE}, 304
            os.remove(maintenance_file_path)
            return {'status': NOT_IN_MAINTENANCE_MODE}


class DeploymentUpdateSteps(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdateStep)
    def post(self, update_id):
        verify_json_content_type()
        request_json = request.json

        manager = get_deployment_updates_manager()
        update_step = \
            manager.create_deployment_update_step(
                    update_id,
                    request_json.get('operation'),
                    request_json.get('entity_type'),
                    request_json.get('entity_id')
            )
        return update_step


class DeploymentUpdate(SecuredResource):

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
            get_deployment_updates_manager().deployment_updates_list(
                    include=None, filters=None, pagination=None,
                    sort=None, **kwargs)
        return deployment_updates

    @swagger.operation(
            responseClass=responses_v2_1.DeploymentUpdate,
            nickname="uploadDeploymentUpdate",
            notes="Uploads an archive for staging",
            parameters=[{'name': 'deployment_id',
                         'description': 'The deployment id to update',
                         'required': True,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'query'},
                        {'name': 'application_file_name',
                         'description': 'The name of the app blueprint',
                         'required': False,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'string',
                         'defaultValue': 'blueprint.yaml'},
                        {'name': 'blueprint_archive_url',
                         'description': 'The path of the archive (only if the '
                                        'archive is an online resource',
                         'required': False,
                         'allowMultiple': False,
                         'dataType': 'string',
                         'paramType': 'query'}
                        ]
    )
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, **kwargs):
        """
        Receives an archive to stage. This archive must contain a
        main blueprint file, and specify its name in the application_file_name,
        defaults to 'blueprint.yaml'

        :param kwargs:
        :return: update response
        """
        return UploadedBlueprintsDeploymentUpdateManager().\
            receive_uploaded_data(request.args['deployment_id'])


class DeploymentUpdateCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.commit_deployment_update(update_id)


class DeploymentUpdateFinalizeCommit(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.DeploymentUpdate)
    def post(self, update_id):
        manager = get_deployment_updates_manager()
        return manager.finalize_commit(update_id)


def get_maintenance_file_path():
    return os.path.join(
        config.instance().maintenance_folder,
        MAINTENANCE_MODE_STATUS_FILE)


def write_maintenance_state(state):
    maintenance_file_path = get_maintenance_file_path()
    with open(maintenance_file_path, 'w') as f:
        f.write(state)
