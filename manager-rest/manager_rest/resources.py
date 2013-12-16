#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dan'

from blueprints_manager import DslParseException
from workflow_client import WorkflowServiceError
from file_server import PORT as file_server_port
import config

from flask_restful_swagger import swagger

from flask import request
from flask.ext.restful import Resource, abort, marshal_with, marshal
import os
from os import path
import responses
import requests
import tarfile
import zipfile
import urllib
import tempfile
import shutil
import uuid

CONVENTION_APPLICATION_BLUEPRINT_FILE = 'blueprint.yaml'


def blueprints_manager():
    import blueprints_manager
    return blueprints_manager.instance()


def events_manager():
    import events_manager
    return events_manager.instance()


def verify_json_content_type():
    if request.content_type != 'application/json':
        abort(415, message='415: Content type must be application/json')


def verify_blueprint_exists(blueprint_id):
    if blueprints_manager().get_blueprint(blueprint_id) is None:
        abort(404, message='404: blueprint {0} not found'.format(blueprint_id))


def verify_deployment_exists(deployment_id):
    if blueprints_manager().get_deployment(deployment_id) is None:
        abort(404, message='404: deployment {0} not found'.format(deployment_id))


def verify_execution_exists(execution_id):
    if blueprints_manager().get_execution(execution_id) is None:
        abort(404, message='404: execution_id {0} not found'.format(execution_id))


def abort_workflow_service_operation(workflow_service_error):
    abort(500, message='500: Workflow service failed with status code {0}'.format(workflow_service_error.status_code))


def setup_resources(api):
    api = swagger.docs(api,
                       apiVersion='0.1',
                       basePath='http://localhost:8100')

    api.add_resource(Blueprints, '/blueprints')
    api.add_resource(BlueprintsId, '/blueprints/<string:blueprint_id>')
    api.add_resource(BlueprintsIdExecutions, '/blueprints/<string:blueprint_id>/executions')
    api.add_resource(ExecutionsId, '/executions/<string:execution_id>')
    api.add_resource(BlueprintsIdValidate, '/blueprints/<string:blueprint_id>/validate')
    api.add_resource(DeploymentIdEvents, '/deployments/<string:deployment_id>/events')
    api.add_resource(Deployments, '/deployments')
    api.add_resource(DeploymentsId, '/deployments/<string:deployment_id>')


class Blueprints(Resource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.BlueprintState.__name__),
        nickname="list",
        notes="Returns a list a submitted blueprints."
    )
    def get(self):
        """
        Returns a list a submitted blueprints.
        """
        return [marshal(blueprint, responses.BlueprintState.resource_fields) for
                blueprint in blueprints_manager().blueprints_list()]

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="upload",
        notes="Submitted blueprint should be a tar gzipped directory containing the blueprint.",
        parameters=[{
            'name': 'application_file_name',
            'description': 'File name of yaml containing the "main" blueprint.',
            'required': False,
            'allowMultiple': False,
            'dataType': 'string',
            'paramType': 'query',
            'defaultValue': 'blueprint.yaml'
        }, {
            'name': 'body',
            'description': 'Binary form of the tar gzipped blueprint directory',
            'required': True,
            'allowMultiple': False,
            'dataType': 'binary',
            'paramType': 'body',
        }],
        consumes=[
            "application/octet-stream"
        ]
    )
    @marshal_with(responses.BlueprintState.resource_fields)
    def post(self):
        """
        Submit a new blueprint.
        """
        file_server_root = config.instance().file_server_root

        blueprint_id = uuid.uuid4()

        archive_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            self._save_file_locally(archive_target_path)
            application_dir = self._extract_file_to_file_server(file_server_root, archive_target_path, blueprint_id)
        finally:
            if os.path.exists(archive_target_path):
                os.remove(archive_target_path)
        self._process_plugins(file_server_root, application_dir)

        return self._prepare_and_submit_blueprint(file_server_root, application_dir, blueprint_id)

    def _process_plugins(self, file_server_root, application_dir):
        blueprint_directory = path.join(file_server_root, application_dir)
        plugins_directory = path.join(blueprint_directory, 'plugins')
        if not path.isdir(plugins_directory):
            return
        plugins = [path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if path.isdir(path.join(plugins_directory, directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(path.basename(plugin_dir))
            target_zip_path = path.join(file_server_root, final_zip_name)
            self._zip_dir(plugin_dir, target_zip_path)

    def _zip_dir(self, dir_to_zip, target_zip_path):
        zipf = zipfile.ZipFile(target_zip_path, 'w', zipfile.ZIP_DEFLATED)
        try:
            plugin_dir_base_name = path.basename(dir_to_zip)
            rootlen = len(dir_to_zip) - len(plugin_dir_base_name)
            for base, dirs, files in os.walk(dir_to_zip):
                for entry in files:
                    fn = os.path.join(base, entry)
                    zipf.write(fn, fn[rootlen:])
        finally:
            zipf.close()

    def _save_file_locally(self, archive_file_name):
        # save uploaded file
        if not request.data:
            abort(400, message='Missing application archive in request body')
        uploaded_file_data = request.data
        with open(archive_file_name, 'w') as f:
            f.write(uploaded_file_data)

    def _extract_file_to_file_server(self, file_server_root, archive_target_path, blueprint_id):
        # extract application to file server
        tar = tarfile.open(archive_target_path)
        tempdir = tempfile.mkdtemp('-blueprint-submit')
        try:
            tar.extractall(tempdir)
            archive_file_list = os.listdir(tempdir)
            if len(archive_file_list) != 1 or not path.isdir(path.join(tempdir, archive_file_list[0])):
                abort(400, message='400: archive must contain exactly 1 directory')
            application_dir_base_name = archive_file_list[0]
            generated_application_dir_base_name = '{0}-{1}'.format(application_dir_base_name, blueprint_id)
            temp_application_dir = path.join(tempdir, application_dir_base_name)
            target_temp_application_dir = path.join(tempdir, generated_application_dir_base_name)
            shutil.move(temp_application_dir, target_temp_application_dir)
            shutil.move(target_temp_application_dir, file_server_root)
            return generated_application_dir_base_name
        finally:
            shutil.rmtree(tempdir)

    def _prepare_and_submit_blueprint(self, file_server_root, application_dir, blueprint_id):
        application_file = self._extract_application_file(file_server_root, application_dir)

        file_server_base_url = 'http://localhost:{0}'.format(file_server_port)
        dsl_path = '{0}/{1}'.format(file_server_base_url, application_file)
        alias_mapping = '{0}/{1}'.format(file_server_base_url, 'cloudify/alias-mappings.yaml')
        resources_base = file_server_base_url + '/'

        # add to blueprints manager (will also dsl_parse it)
        try:
            return blueprints_manager().publish_blueprint(blueprint_id, dsl_path, alias_mapping, resources_base), 201
        except DslParseException:
            abort(400, message='400: Invalid blueprint')

    def _extract_application_file(self, file_server_root, application_dir):
        if 'application_file_name' in request.args:
            application_file = urllib.unquote(request.args['application_file_name']).decode('utf-8')
            application_file = '{0}/{1}'.format(application_dir, application_file)
            return application_file
        else:
            full_application_dir = path.join(file_server_root, application_dir)
            full_application_file = path.join(full_application_dir, CONVENTION_APPLICATION_BLUEPRINT_FILE)
            if path.isfile(full_application_file):
                application_file = path.join(application_dir, CONVENTION_APPLICATION_BLUEPRINT_FILE)
                return application_file
        abort(400, message='Missing application_file_name query parameter or application directory is missing '
                           'blueprint.yaml')


class BlueprintsId(Resource):

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @marshal_with(responses.BlueprintState.resource_fields)
    def get(self, blueprint_id):
        """
        Returns a blueprint by its id.
        """
        verify_blueprint_exists(blueprint_id)
        return blueprints_manager().get_blueprint(blueprint_id)


class BlueprintsIdValidate(Resource):

    @swagger.operation(
        responseClass=responses.BlueprintValidationStatus,
        nickname="validate",
        notes="Validates a given blueprint."
    )
    @marshal_with(responses.BlueprintValidationStatus.resource_fields)
    def get(self, blueprint_id):
        """
        Validates a given blueprint.
        """
        verify_blueprint_exists(blueprint_id)
        return blueprints_manager().validate_blueprint(blueprint_id)


class BlueprintsIdExecutions(Resource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions related to the provided blueprint."
    )
    def get(self, blueprint_id):
        """
        Returns a list of executions related to the provided blueprint.
        """
        verify_blueprint_exists(blueprint_id)
        return [marshal(execution, responses.Execution.resource_fields) for
                execution in blueprints_manager().get_blueprint(blueprint_id).executions_list()]

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="execute",
        notes="Executes the provided workflow and creates a new deployment for this executions.",
        parameters=[{
            'name': 'body',
            'description': 'Workflow execution request',
            'required': True,
            'allowMultiple': False,
            'dataType': requests.ExecutionRequest.__name__,
            'paramType': 'body'
        }],
        consumes=[
            "application/json"
        ]
    )
    @marshal_with(responses.Execution.resource_fields)
    def post(self, blueprint_id):
        """
        Execute a workflow
        """
        verify_json_content_type()
        verify_blueprint_exists(blueprint_id)
        request_json = request.json
        if 'workflowId' not in request_json:
            abort(400, message='400: Missing workflowId in json request body')
        workflow_id = request.json['workflowId']
        try:
            return blueprints_manager().execute_workflow(blueprint_id, workflow_id), 201
        except WorkflowServiceError, e:
            abort_workflow_service_operation(e)


class ExecutionsId(Resource):

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="getById",
        notes="Returns the execution state by its id."
    )
    @marshal_with(responses.Execution.resource_fields)
    def get(self, execution_id):
        """
        Returns the execution state by its id.
        """
        verify_execution_exists(execution_id)
        try:
            return blueprints_manager().get_workflow_state(execution_id)
        except WorkflowServiceError, e:
            abort_workflow_service_operation(e)


class DeploymentIdEvents(Resource):

    def __init__(self):
        from flask.ext.restful import reqparse
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('from', type=int, default=0, location='args')
        self._args_parser.add_argument('count', type=int, default=500, location='args')

    @swagger.operation(
        responseClass=responses.DeploymentEvents,
        nickname="readEvents",
        notes="Returns all available events for the given deployment matching the provided parameters.",
        parameters=[{
            'name': 'from',
            'description': 'Index of the first request event.',
            'required': False,
            'allowMultiple': False,
            'dataType': 'int',
            'paramType': 'query',
            'defaultValue': 0
        }, {
            'name': 'count',
            'description': 'Maximum number of events to read.',
            'required': False,
            'allowMultiple': False,
            'dataType': 'int',
            'paramType': 'query',
            'defaultValue': 500
        }]
    )
    @marshal_with(responses.DeploymentEvents.resource_fields)
    def get(self, deployment_id):
        """
        Returns deployments events.
        """
        args = self._args_parser.parse_args()

        first_event = args['from']
        events_count = args['count']

        if first_event < 0:
            abort(400, message='from argument cannot be negative')
        if events_count < 0:
            abort(400, message='count argument cannot be negative')

        try:
            result = events_manager().get_deployment_events(deployment_id,
                                                            first_event=first_event,
                                                            events_count=events_count,
                                                            only_bytes=request.method == 'HEAD')
            return result, 200, {'Deployment-Events-Bytes': result.deployment_events_bytes}
        except BaseException as e:
            abort(500, message=e.message)


class Deployments(Resource):

    def get(self):
        return [marshal(deployment, responses.Deployment.resource_fields) for
                deployment in blueprints_manager().deployments_list()]


class DeploymentsId(Resource):

    @marshal_with(responses.Deployment.resource_fields)
    def get(self, deployment_id):
        verify_deployment_exists(deployment_id)
        return blueprints_manager().get_deployment(deployment_id)
