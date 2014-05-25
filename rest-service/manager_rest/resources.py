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

import os
import tarfile
import zipfile
import urllib
import tempfile
import shutil
import uuid
from functools import wraps
from os import path

import elasticsearch
from flask import request
from flask import make_response
from flask.ext.restful import Resource, abort, marshal_with, marshal, reqparse
from flask_restful_swagger import swagger

from manager_rest import config
from manager_rest import models
from manager_rest import responses
from manager_rest import requests_schema
from manager_rest import chunked
from manager_rest import manager_exceptions
from manager_rest.storage_manager import get_storage_manager
from manager_rest.workflow_client import WorkflowServiceError
from manager_rest.blueprints_manager import (DslParseException,
                                             get_blueprints_manager)


CONVENTION_APPLICATION_BLUEPRINT_FILE = 'blueprint.yaml'


def exceptions_handled(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except manager_exceptions.ConflictError, e:
            abort_conflict(e)
        except manager_exceptions.NotFoundError, e:
            abort_not_found(e)
        except manager_exceptions.DependentExistsError, e:
            abort_dependent_exists(e)
        except manager_exceptions.NonexistentWorkflowError, e:
            abort_nonexistent_workflow(e)
        except WorkflowServiceError, e:
            abort_workflow_service_operation(e)
    return wrapper


def abort_workflow_service_operation(workflow_service_error):
    abort(500,
          message='500: Workflow service failed with status code {0},'
                  ' full response {1}'
                  .format(workflow_service_error.status_code,
                          workflow_service_error.json))


def abort_conflict(conflict_error):
    abort_error(409, conflict_error)


def abort_not_found(not_exists_error):
    abort_error(404, not_exists_error)


def abort_dependent_exists(dependent_exists_error):
    abort_error(400, dependent_exists_error)


def abort_nonexistent_workflow(nonexistent_workflow_error):
    abort_error(400, nonexistent_workflow_error)


def abort_error(status_code, error):
    abort(status_code,
          message='{0}: {1}'.format(status_code, str(error)))


def verify_json_content_type():
    if request.content_type != 'application/json':
        abort(415, message='415: Content type must be application/json')


def verify_and_convert_bool(attribute_name, str_bool):
    if str_bool.lower() == 'true':
        return True
    if str_bool.lower() == 'false':
        return False
    abort(400,
          message='400: {0} must be <true/false>, got {1}'
                  .format(attribute_name, str_bool))


def setup_resources(api):
    api = swagger.docs(api,
                       apiVersion='0.1',
                       basePath='http://localhost:8100')
    api.add_resource(Blueprints,
                     '/blueprints')
    api.add_resource(BlueprintsId,
                     '/blueprints/<string:blueprint_id>')
    api.add_resource(BlueprintsIdArchive,
                     '/blueprints/<string:blueprint_id>/archive')
    api.add_resource(BlueprintsIdSource,
                     '/blueprints/<string:blueprint_id>/source')
    api.add_resource(BlueprintsIdValidate,
                     '/blueprints/<string:blueprint_id>/validate')
    api.add_resource(ExecutionsId,
                     '/executions/<string:execution_id>')
    api.add_resource(Deployments,
                     '/deployments')
    api.add_resource(DeploymentsId,
                     '/deployments/<string:deployment_id>')
    api.add_resource(DeploymentsIdExecutions,
                     '/deployments/<string:deployment_id>/executions')
    api.add_resource(DeploymentsIdWorkflows,
                     '/deployments/<string:deployment_id>/workflows')
    api.add_resource(DeploymentsIdNodes,
                     '/deployments/<string:deployment_id>/nodes')
    api.add_resource(NodesId,
                     '/nodes/<string:node_id>')
    api.add_resource(Events, '/events')
    api.add_resource(Search, '/search')
    api.add_resource(Status, '/status')
    api.add_resource(ProviderContext, '/provider/context')


class BlueprintsUpload(object):
    def do_request(self, blueprint_id=None):
        file_server_root = config.instance().file_server_root
        archive_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            self._save_file_locally(archive_target_path)
            application_dir = self._extract_file_to_file_server(
                file_server_root, archive_target_path)
            blueprint = self._prepare_and_submit_blueprint(file_server_root,
                                                           application_dir,
                                                           blueprint_id)
            self._move_archive_to_uploaded_blueprints_dir(blueprint.id,
                                                          file_server_root,
                                                          archive_target_path)
            return blueprint, 201
        finally:
            if os.path.exists(archive_target_path):
                os.remove(archive_target_path)

    @staticmethod
    def _move_archive_to_uploaded_blueprints_dir(blueprint_id,
                                                 file_server_root,
                                                 archive_path):
        if not os.path.exists(archive_path):
            raise RuntimeError("Archive [{0}] doesn't exist - Cannot move "
                               "archive to uploaded blueprints "
                               "directory".format(archive_path))
        uploaded_blueprint_dir = os.path.join(
            file_server_root,
            config.instance().file_server_uploaded_blueprints_folder,
            blueprint_id)
        os.makedirs(uploaded_blueprint_dir)
        archive_file_name = '{0}.tar.gz'.format(blueprint_id)
        shutil.move(archive_path,
                    os.path.join(uploaded_blueprint_dir, archive_file_name))

    def _process_plugins(self, file_server_root, blueprint_id):
        plugins_directory = path.join(file_server_root,
                                      "blueprints", blueprint_id, "plugins")
        if not path.isdir(plugins_directory):
            return
        plugins = [path.join(plugins_directory, directory)
                   for directory in os.listdir(plugins_directory)
                   if path.isdir(path.join(plugins_directory, directory))]

        for plugin_dir in plugins:
            final_zip_name = '{0}.zip'.format(path.basename(plugin_dir))
            target_zip_path = path.join(file_server_root,
                                        "blueprints", blueprint_id,
                                        'plugins', final_zip_name)
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
        if 'Transfer-Encoding' in request.headers:
            with open(archive_file_name, 'w') as f:
                for buffered_chunked in chunked.decode(request.input_stream):
                    f.write(buffered_chunked)
        else:
            if not request.data:
                abort(400,
                      message='Missing application archive in request body')
            uploaded_file_data = request.data
            with open(archive_file_name, 'w') as f:
                f.write(uploaded_file_data)

    def _extract_file_to_file_server(self, file_server_root,
                                     archive_target_path):
        # extract application to file server
        tar = tarfile.open(archive_target_path)
        tempdir = tempfile.mkdtemp('-blueprint-submit')
        try:
            tar.extractall(tempdir)
            archive_file_list = os.listdir(tempdir)
            if len(archive_file_list) != 1 or not path.isdir(
                    path.join(tempdir, archive_file_list[0])):
                abort(400,
                      message='400: archive must contain exactly 1 directory')
            application_dir_base_name = archive_file_list[0]
            # generating temporary unique name for app dir, to allow multiple
            # uploads of apps with the same name (as it appears in the file
            # system, not the app name field inside the blueprint.
            # the latter is guaranteed to be unique).
            generated_app_dir_name = '{0}-{1}'.format(
                application_dir_base_name, uuid.uuid4())
            temp_application_dir = path.join(tempdir,
                                             application_dir_base_name)
            temp_application_target_dir = path.join(tempdir,
                                                    generated_app_dir_name)
            shutil.move(temp_application_dir, temp_application_target_dir)
            shutil.move(temp_application_target_dir, file_server_root)
            return generated_app_dir_name
        finally:
            shutil.rmtree(tempdir)

    def _prepare_and_submit_blueprint(self, file_server_root,
                                      application_dir,
                                      blueprint_id=None):
        application_file = self._extract_application_file(file_server_root,
                                                          application_dir)

        file_server_base_url = config.instance().file_server_base_uri
        dsl_path = '{0}/{1}'.format(file_server_base_url, application_file)
        alias_mapping = '{0}/{1}'.format(file_server_base_url,
                                         'cloudify/alias-mappings.yaml')
        resources_base = file_server_base_url + '/'

        # add to blueprints manager (will also dsl_parse it)
        try:
            blueprint = get_blueprints_manager().publish_blueprint(
                dsl_path, alias_mapping, resources_base, blueprint_id)

            # moving the app directory in the file server to be under a
            # directory named after the blueprint id
            shutil.move(os.path.join(file_server_root, application_dir),
                        os.path.join(
                            file_server_root,
                            config.instance().file_server_blueprints_folder,
                            blueprint.id))
            self._process_plugins(file_server_root, blueprint.id)
            return blueprint
        except DslParseException, ex:
            shutil.rmtree(os.path.join(file_server_root, application_dir))
            abort(400, message='400: Invalid blueprint - {0}'.format(ex.args))

    def _extract_application_file(self, file_server_root, application_dir):
        if 'application_file_name' in request.args:
            application_file = urllib.unquote(
                request.args['application_file_name']).decode('utf-8')
            application_file = '{0}/{1}'.format(application_dir,
                                                application_file)
            return application_file
        else:
            full_application_dir = path.join(file_server_root, application_dir)
            full_application_file = path.join(
                full_application_dir, CONVENTION_APPLICATION_BLUEPRINT_FILE)
            if path.isfile(full_application_file):
                application_file = path.join(
                    application_dir, CONVENTION_APPLICATION_BLUEPRINT_FILE)
                return application_file
        abort(400, message='Missing application_file_name query parameter or '
                           'application directory is missing blueprint.yaml')


class BlueprintsIdArchive(Resource):

    @swagger.operation(
        nickname="getArchive",
        notes="Downloads blueprint as an archive."
    )
    @exceptions_handled
    def get(self, blueprint_id):
        # Verify blueprint exists.
        get_blueprints_manager().get_blueprint(blueprint_id, {'id'})
        blueprint_path = '{0}/{1}/{2}/{2}.tar.gz'.format(
            config.instance().file_server_resources_uri,
            config.instance().file_server_uploaded_blueprints_folder,
            blueprint_id)

        local_path = os.path.join(
            config.instance().file_server_root,
            config.instance().file_server_uploaded_blueprints_folder,
            blueprint_id,
            '%s.tar.gz' % blueprint_id)

        response = make_response()
        response.headers['Content-Description'] = 'File Transfer'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Content-Disposition'] = \
            'attachment; filename=%s.tar.gz' % blueprint_id
        response.headers['Content-Length'] = os.path.getsize(local_path)
        response.headers['X-Accel-Redirect'] = blueprint_path
        response.headers['X-Accel-Buffering'] = 'yes'
        return response


class Blueprints(Resource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.BlueprintState.__name__),
        nickname="list",
        notes="Returns a list a submitted blueprints."
    )
    def get(self):
        """
        Returns a list of submitted blueprints.
        """
        return [marshal(blueprint,
                        responses.BlueprintState.resource_fields) for
                blueprint in get_blueprints_manager().blueprints_list()]

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="upload",
        notes="Submitted blueprint should be a tar "
              "gzipped directory containing the blueprint.",
        parameters=[{'name': 'application_file_name',
                     'description': 'File name of yaml '
                                    'containing the "main" blueprint.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query',
                     'defaultValue': 'blueprint.yaml'},
                    {
                        'name': 'body',
                        'description': 'Binary form of the tar '
                                       'gzipped blueprint directory',
                        'required': True,
                        'allowMultiple': False,
                        'dataType': 'binary',
                        'paramType': 'body'}
                    ],
        consumes=[
            "application/octet-stream"
        ]

    )
    @marshal_with(responses.BlueprintState.resource_fields)
    @exceptions_handled
    def post(self):
        """
        Submit a new blueprint.
        """
        return BlueprintsUpload().do_request()


class BlueprintsIdSource(Resource):

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="getBlueprintSource",
        notes="Returns a blueprint's source by the blueprint's id."
    )
    @marshal_with(responses.BlueprintState.resource_fields)
    @exceptions_handled
    def get(self, blueprint_id):
        """
        Returns a blueprint by its id.
        """
        fields = {'id', 'source'}
        blueprint = get_blueprints_manager().get_blueprint(blueprint_id,
                                                           fields)
        return responses.BlueprintState(**blueprint.to_dict())


class BlueprintsId(Resource):

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @marshal_with(responses.BlueprintState.resource_fields)
    @exceptions_handled
    def get(self, blueprint_id):
        """
        Returns a blueprint by its id.
        """
        fields = {'id', 'plan', 'created_at', 'updated_at'}
        blueprint = get_blueprints_manager().get_blueprint(blueprint_id,
                                                           fields)
        return responses.BlueprintState(**blueprint.to_dict())

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="upload",
        notes="Submitted blueprint should be a tar "
              "gzipped directory containing the blueprint.",
        parameters=[{'name': 'application_file_name',
                     'description': 'File name of yaml '
                                    'containing the "main" blueprint.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query',
                     'defaultValue': 'blueprint.yaml'},
                    {
                        'name': 'body',
                        'description': 'Binary form of the tar '
                                       'gzipped blueprint directory',
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
    @exceptions_handled
    def put(self, blueprint_id):
        """
        Submit a new blueprint with a blueprint_id.
        """
        return BlueprintsUpload().do_request(blueprint_id=blueprint_id)

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @marshal_with(responses.BlueprintState.resource_fields)
    @exceptions_handled
    def delete(self, blueprint_id):
        # Note: The current delete semantics are such that if a deployment
        # for the blueprint exists, the deletion operation will fail.
        # However, there is no handling of possible concurrency issue with
        # regard to that matter at the moment.
        blueprint = get_blueprints_manager().delete_blueprint(blueprint_id)

        # Delete blueprint resources from file server
        blueprint_folder = os.path.join(
            config.instance().file_server_root,
            config.instance().file_server_blueprints_folder,
            blueprint.id)
        shutil.rmtree(blueprint_folder)
        uploaded_blueprint_folder = os.path.join(
            config.instance().file_server_root,
            config.instance().file_server_uploaded_blueprints_folder,
            blueprint.id)
        shutil.rmtree(uploaded_blueprint_folder)

        return responses.BlueprintState(**blueprint.to_dict()), 200


class BlueprintsIdValidate(Resource):

    @swagger.operation(
        responseClass=responses.BlueprintValidationStatus,
        nickname="validate",
        notes="Validates a given blueprint."
    )
    @marshal_with(responses.BlueprintValidationStatus.resource_fields)
    @exceptions_handled
    def get(self, blueprint_id):
        """
        Validates a given blueprint.
        """
        return get_blueprints_manager().validate_blueprint(blueprint_id)


class ExecutionsId(Resource):

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="getById",
        notes="Returns the execution state by its id.",
    )
    @marshal_with(responses.Execution.resource_fields)
    @exceptions_handled
    def get(self, execution_id):
        """
        Returns the execution state by its id.
        """
        execution = get_blueprints_manager().get_workflow_state(execution_id)
        return responses.Execution(**execution.to_dict())

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="modify_state",
        notes="Modifies a running execution state (currently, only cancel"
              " is supported)",
        parameters=[{'name': 'body',
                     'description': 'json with an action key. '
                                    'Legal values for action are: [cancel]',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.ModifyExecutionRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @marshal_with(responses.Execution.resource_fields)
    @exceptions_handled
    def post(self, execution_id):
        """
        Modify a running execution state.
        """
        verify_json_content_type()
        request_json = request.json
        if 'action' not in request_json:
            abort(400, message='400: Missing action in json request body')
        action = request.json['action']

        valid_actions = ['cancel']

        if action not in valid_actions:
            abort(400, message='400: Invalid action: {0}, '
                               'Valid action values are: {1}'
                               .format(action, valid_actions))

        if action == 'cancel':
            return get_blueprints_manager().cancel_workflow(execution_id), 201


class DeploymentsIdNodes(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('state', type=str,
                                       default='false', location='args')

    @swagger.operation(
        responseClass=responses.DeploymentNodes,
        nickname="list",
        notes="Returns an object containing nodes associated with "
              "this deployment.",
        parameters=[{'name': 'state',
                     'description': 'Specifies whether to return state '
                                    'for the nodes.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @marshal_with(responses.DeploymentNodes.resource_fields)
    @exceptions_handled
    def get(self, deployment_id):
        """
        Returns an object containing nodes associated with this deployment.
        """
        args = self._args_parser.parse_args()
        get_state = verify_and_convert_bool(
            'state', args['state'])

        deployment = get_blueprints_manager().get_deployment(deployment_id)
        node_ids = map(lambda node: node['id'],
                       deployment.plan['nodes'])

        nodes = []
        for node_id in node_ids:
            node_result = responses.DeploymentNode(id=node_id,
                                                   state=None,
                                                   state_version=None,
                                                   runtime_info=None)
            if get_state:
                node = get_storage_manager().get_node(node_id)
                node_result.state = node.state
                node_result.state_version = node.state_version
            nodes.append(node_result)
        return responses.DeploymentNodes(deployment_id=deployment_id,
                                         nodes=nodes)


class Deployments(Resource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Deployment.__name__),
        nickname="list",
        notes="Returns a list existing deployments."
    )
    def get(self):
        """
        Returns a list of existing deployments.
        """
        return [marshal(responses.Deployment(**deployment.to_dict()),
                        responses.Deployment.resource_fields) for
                deployment in get_blueprints_manager().deployments_list()]


class DeploymentsId(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('ignore_live_nodes', type=str,
                                       default='false', location='args')

    @swagger.operation(
        responseClass=responses.Deployment,
        nickname="getById",
        notes="Returns a deployment by its id."
    )
    @marshal_with(responses.Deployment.resource_fields)
    @exceptions_handled
    def get(self, deployment_id):
        """
        Returns a deployment by its id.
        """
        deployment = get_blueprints_manager().get_deployment(deployment_id)
        return responses.Deployment(**deployment.to_dict())

    @swagger.operation(
        responseClass=responses.Deployment,
        nickname="createDeployment",
        notes="Created a new deployment of the given blueprint.",
        parameters=[{'name': 'body',
                     'description': 'Deployment blue print',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.DeploymentRequest.__name__,
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @marshal_with(responses.Deployment.resource_fields)
    @exceptions_handled
    def put(self, deployment_id):
        """
        Creates a new deployment
        """
        verify_json_content_type()
        request_json = request.json
        if 'blueprintId' not in request_json:
            abort(400, message='400: Missing blueprintId in json request body')
        blueprint_id = request.json['blueprintId']
        return get_blueprints_manager().create_deployment(blueprint_id,
                                                          deployment_id), 201

    @swagger.operation(
        responseClass=responses.Deployment,
        nickname="deleteById",
        notes="deletes a deployment by its id.",
        parameters=[{'name': 'ignore_live_nodes',
                     'description': 'Specifies whether to ignore live nodes,'
                                    'or raise an error upon such nodes '
                                    'instead.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @marshal_with(responses.Deployment.resource_fields)
    @exceptions_handled
    def delete(self, deployment_id):
        args = self._args_parser.parse_args()

        ignore_live_nodes = verify_and_convert_bool(
            'ignore_live_nodes', args['ignore_live_nodes'])

        deployment = get_blueprints_manager().delete_deployment(
            deployment_id, ignore_live_nodes)
        return responses.Deployment(**deployment.to_dict()), 200


class NodesId(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('state_and_runtime_properties',
                                       type=str,
                                       default='true',
                                       location='args')

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="getNodeInstance",
        notes="Returns node state/runtime properties "
              "according to the provided query parameters.",
        parameters=[{'name': 'node_id',
                     'description': 'Node Id',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'},
                    {'name': 'state_and_runtime_properties',
                     'description': 'Specifies whether to return state and '
                                    'runtime properties',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': True,
                     'paramType': 'query'}]
    )
    @marshal_with(responses.DeploymentNode.resource_fields)
    @exceptions_handled
    def get(self, node_id):
        """
        Gets node runtime or state.
        """
        args = self._args_parser.parse_args()
        get_state_and_runtime_properties = verify_and_convert_bool(
            'state_and_runtime_properties',
            args['state_and_runtime_properties'])

        state = None
        runtime_info = None
        state_version = None

        if get_state_and_runtime_properties:
            node = get_storage_manager().get_node(node_id)
            runtime_info = node.runtime_info
            state_version = node.state_version
            state = node.state

        return responses.DeploymentNode(id=node_id,
                                        state=state,
                                        runtime_info=runtime_info,
                                        state_version=state_version)

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="putNodeInstance",
        notes="Put node instance",
        parameters=[{'name': 'node_id',
                     'description': 'Node Id',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'}]
    )
    @marshal_with(responses.DeploymentNode.resource_fields)
    @exceptions_handled
    def put(self, node_id):
        """
        Puts node runtime state.
        """
        verify_json_content_type()
        if request.json.__class__ is not dict:
            abort(400, message='request body is expected to be'
                               ' of key/value map type but is {0}'
                               .format(request.json.__class__.__name__))

        node = models.DeploymentNode(id=node_id, runtime_info=request.json,
                                     state='uninitialized',
                                     state_version=None)
        node.state_version = get_storage_manager().put_node(node_id, node)
        return responses.DeploymentNode(**node.to_dict()), 201

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="patchNodeState",
        notes="Update node runtime state. Expecting the request body to "
              "be a dictionary containing 'state_version' which is used for "
              "optimistic locking during the update, and optionally "
              "'runtime_info' (dictionary) and/or 'state' (string) "
              "properties",
        parameters=[{'name': 'node_id',
                     'description': 'Node Id',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'},
                    {'name': 'state_version',
                     'description': 'used for optimistic locking during '
                                    'update',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'int',
                     'paramType': 'body'},
                    {'name': 'runtime_properties',
                     'description': 'a dictionary of runtime properties. If '
                                    'omitted, the runtime properties wont be '
                                    'updated',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'dict',
                     'paramType': 'body'},
                    {'name': 'state',
                     'description': "the new node's state. If omitted, "
                                    "the state wont be updated",
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=["application/json"]
    )
    @marshal_with(responses.DeploymentNode.resource_fields)
    @exceptions_handled
    def patch(self, node_id):
        """
        Updates node instance
        """
        verify_json_content_type()
        if request.json.__class__ is not dict or \
                'state_version' not in request.json or \
                request.json['state_version'].__class__ is not int:

            if request.json.__class__ is not dict:
                message = 'request body is expected to be a map containing ' \
                          'a "state_version" field and optionally ' \
                          '"runtime_info" and/or "state" fields'
            elif 'state_version' not in request.json:
                message = 'request body must be a map containing a ' \
                          '"state_version" field'
            else:
                message = \
                    "request body's 'state_version' field must be an int but" \
                    " is of type {0}".format(request.json['state_version']
                                             .__class__.__name__)
            abort(400, message=message)

        node = models.DeploymentNode(
            id=node_id, runtime_info=request.json.get('runtime_info'),
            state=request.json.get('state'),
            state_version=request.json['state_version'])
        get_storage_manager().update_node(node_id, node)
        return responses.DeploymentNode(
            **get_storage_manager().get_node(node_id).to_dict())


class DeploymentsIdExecutions(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('statuses', type=str,
                                       default='false', location='args')

        self._post_args_parser = reqparse.RequestParser()
        self._post_args_parser.add_argument('force', type=str,
                                            default='false', location='args')

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions related to the provided"
              " deployment.",
        parameters=[{'name': 'statuses',
                     'description': 'Specifies whether to return '
                                    'current statuses and errors data for '
                                    "the deployment's executions",
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @exceptions_handled
    def get(self, deployment_id):
        """
        Returns a list of executions related to the provided deployment.
        """
        args = self._args_parser.parse_args()
        get_executions_statuses = verify_and_convert_bool(
            'statuses', args['statuses'])

        # simple call to verify deployment actually exists
        # if it doesnt, a 404 will be raised by the underlying storage
        # manager with the deployment relevant details
        get_storage_manager().get_deployment(deployment_id, fields=['id'])

        executions = self._get_executions(deployment_id,
                                          get_executions_statuses)

        return [marshal(execution, responses.Execution.resource_fields) for
                execution in executions]

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="execute",
        notes="Executes the provided workflow under the given deployment "
              "context.",
        parameters=[{'name': 'body',
                     'description': 'Workflow execution request',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.ExecutionRequest.__name__,
                     'paramType': 'body'},
                    {'name': 'force',
                     'description': 'Specifies whether to force workflow '
                                    'execution even if there is an ongoing '
                                    'workflow executing for the same '
                                    'deployment',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'}],
        consumes=[
            "application/json"
        ]
    )
    @marshal_with(responses.Execution.resource_fields)
    @exceptions_handled
    def post(self, deployment_id):
        """
        Execute a workflow
        """
        verify_json_content_type()
        request_json = request.json
        if 'workflowId' not in request_json:
            abort(400, message='400: Missing workflowId in json request body')

        args = self._post_args_parser.parse_args()
        force = verify_and_convert_bool('force', args['force'])

        # validate no execution is currently in progress
        if not force:
            executions = self._get_executions(deployment_id,
                                              statuses=True)
            running = [e.id for e in executions
                       if e.status not in ['failed', 'terminated']]
            if len(running) > 0:
                abort_error(400, 'The following executions are currently '
                                 'running for this deployment: {0}. To '
                                 'execute this workflow anyway, '
                                 'pass "force=true" as a query parameter to'
                                 ' this request'.format(running))

        workflow_id = request.json['workflowId']
        execution = get_blueprints_manager().execute_workflow(deployment_id,
                                                              workflow_id)
        return responses.Execution(**execution.to_dict()), 201

    def _get_executions(self, deployment_id, statuses=False):
        executions = [responses.Execution(**execution.to_dict()) for
                      execution in
                      get_storage_manager().get_deployment_executions(
                          deployment_id)]

        if statuses:
            statuses_response = get_blueprints_manager() \
                .get_workflows_states_by_internal_workflows_ids(
                    [execution.internal_workflow_id for execution
                     in executions])

            status_by_id = {status['id']: status for status in
                            statuses_response}
            for execution in executions:
                if execution.internal_workflow_id in status_by_id:
                    status = status_by_id[execution.internal_workflow_id]
                    execution.status = status['state']
                    execution.error = status['error']
                else:
                    # execution not found in workflow service, return unknown
                    # values
                    execution.status, execution.error = None, None
        else:
            # setting None values to dynamic fields which weren't requested
            for execution in executions:
                execution.status, execution.error = None, None
        return executions


class DeploymentsIdWorkflows(Resource):

    @swagger.operation(
        responseClass='Workflows',
        nickname="workflows",
        notes="Returns a list of workflows related to the provided deployment."
    )
    @marshal_with(responses.Workflows.resource_fields)
    @exceptions_handled
    def get(self, deployment_id):
        """
        Returns a list of workflows related to the provided deployment.
        """
        deployment = get_blueprints_manager().get_deployment(deployment_id)
        deployment_workflows = deployment.plan['workflows']
        workflows = [responses.Workflow(name=wf_name, created_at=None) for
                     wf_name in
                     deployment_workflows.keys()]

        return {
            'workflows': workflows,
            'blueprint_id': deployment.blueprint_id,
            'deployment_id': deployment.id
        }


def _query_elastic_search(index=None, doc_type=None, body=None):
    """Query ElasticSearch with the provided index and query body.

    Returns:
    ElasticSearch result as is (Python dict).
    """
    es = elasticsearch.Elasticsearch()
    return es.search(index=index, doc_type=doc_type, body=body)


class Events(Resource):

    def _query_events(self):
        """
        Returns events for the provided ElasticSearch query
        """
        verify_json_content_type()
        return _query_elastic_search(index='cloudify_events',
                                     body=request.json)

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    def get(self):
        """
        Returns events for the provided ElasticSearch query
        """
        return self._query_events()

    @swagger.operation(
        nickname='events',
        notes='Returns a list of events for the provided ElasticSearch query. '
              'The response format is as ElasticSearch response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    def post(self):
        """
        Returns events for the provided ElasticSearch query
        """
        return self._query_events()


class Search(Resource):

    @swagger.operation(
        nickname='search',
        notes='Returns results from the storage for the provided '
              'ElasticSearch query. The response format is as ElasticSearch '
              'response format.',
        parameters=[{'name': 'body',
                     'description': 'ElasticSearch query.',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=['application/json']
    )
    def post(self):
        """
        Returns results for the provided ElasticSearch query
        """
        verify_json_content_type()
        return _query_elastic_search(index='cloudify_storage',
                                     body=request.json)


class Status(Resource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of running system services"
    )
    @marshal_with(responses.Status.resource_fields)
    @exceptions_handled
    def get(self):
        """
        Returns state of running system services
        """
        job_list = {'rsyslog': 'Syslog',
                    'manager': 'Cloudify Manager',
                    'workflow': 'Workflow Service',
                    'riemann': 'Riemann',
                    'rabbitmq-server': 'RabbitMQ',
                    'celeryd-cloudify-management': 'Celery Managment',
                    'ssh': 'SSH',
                    'elasticsearch': 'Elasticsearch',
                    'cloudify-ui': 'Cloudify UI',
                    'logstash': 'Logstash',
                    'nginx': 'Webserver'
                    }

        try:
            from manager_rest.upstartdbus import get_jobs
            jobs = get_jobs(job_list.keys(), job_list.values())
        except ImportError:
            jobs = ['undefined']

        return responses.Status(status='running', services=jobs)


class ProviderContext(Resource):

    @swagger.operation(
        responseClass=responses.ProviderContext,
        nickname="getContext",
        notes="Get the provider context"
    )
    @marshal_with(responses.ProviderContext.resource_fields)
    @exceptions_handled
    def get(self):
        """
        Get the provider context.
        """
        context = get_storage_manager().get_provider_context()
        return responses.ProviderContext(**context.to_dict())

    @swagger.operation(
        responseClass=responses.ProviderContextPostStatus,
        nickname='postContext',
        notes="Post the provider context",
        parameters=[{'name': 'body',
                     'description': 'Provider context',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.PostProviderContextRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @marshal_with(responses.ProviderContextPostStatus.resource_fields)
    @exceptions_handled
    def post(self):
        """
        Post the provider context
        """
        verify_json_content_type()
        request_json = request.json
        if 'context' not in request_json:
            abort(400, message='400: Missing context in json request body')
        if 'name' not in request_json:
            abort(400, message='400: Missing provider in json request body')
        context = models.ProviderContext(name=request.json['name'],
                                         context=request.json['context'])
        get_storage_manager().put_provider_context(context)
        return responses.ProviderContextPostStatus(status='ok'), 201
