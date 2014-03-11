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
from os import path
import tarfile
import zipfile
import urllib
import tempfile
import shutil
import uuid
from functools import wraps

import elasticsearch

from flask import request
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
from manager_rest.riemann_client import get_riemann_client


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
    abort(409,
          message='409: Conflict occurred - {0}'.format(str(conflict_error)))


def abort_not_found(not_exists_error):
    abort(404,
          message='404: {0}'.format(str(not_exists_error)))


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
    api.add_resource(BlueprintsSource,
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


class BlueprintsUpload(object):
    def do_request(self, blueprint_id=None):
        file_server_root = config.instance().file_server_root
        archive_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            self._save_file_locally(archive_target_path)
            application_dir = self._extract_file_to_file_server(
                file_server_root, archive_target_path)
        finally:
            if os.path.exists(archive_target_path):
                os.remove(archive_target_path)
        self._process_plugins(file_server_root, application_dir)

        return self._prepare_and_submit_blueprint(file_server_root,
                                                  application_dir,
                                                  blueprint_id), 201

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
            #generating temporary unique name for app dir, to allow multiple
            #uploads of apps with the same name (as it appears in the file
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

            #moving the app directory in the file server to be under a
            # directory named after the blueprint's app name field
            shutil.move(os.path.join(file_server_root, application_dir),
                        os.path.join(file_server_root, blueprint.id))
            return blueprint
        except DslParseException, ex:
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
                        'paramType': 'body',
                    }],
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


class BlueprintsSource(Resource):

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
                 'description': 'json with an action key. Legal values for '
                                'action are: [cancel]',
                 'required': True,
                 'allowMultiple': False,
                 'dataType': requests_schema.ModifyExecutionRequest.__name__,
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
        self._args_parser.add_argument('reachable', type=str,
                                       default='false', location='args')

    @swagger.operation(
        responseClass=responses.DeploymentNodes,
        nickname="list",
        notes="Returns an object containing nodes associated with "
              "this deployment.",
        parameters=[{'name': 'reachable',
                     'description': 'Specifies whether to return reachable '
                                    'state for the nodes.',
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
        get_reachable_state = verify_and_convert_bool(
            'reachable', args['reachable'])

        deployment = get_blueprints_manager().get_deployment(deployment_id)
        node_ids = map(lambda node: node['id'],
                       deployment.plan['nodes'])

        reachable_states = {}
        if get_reachable_state:
            reachable_states = get_riemann_client().get_nodes_state(node_ids)

        nodes = []
        for node_id in node_ids:
            node_result = responses.DeploymentNode(id=node_id,
                                                   state_version=None,
                                                   reachable=None,
                                                   runtime_info=None)
            if get_reachable_state:
                state = reachable_states[node_id]
                node_result.reachable = state['reachable']
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


class NodesId(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('state', type=str,
                                       default='false', location='args')
        self._args_parser.add_argument('reachable', type=str,
                                       default='false', location='args')
        self._args_parser.add_argument('runtime', type=str,
                                       default='true', location='args')

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="getNodeState",
        notes="Returns node runtime/reachable state "
              "according to the provided query parameters.",
        parameters=[{'name': 'node_id',
                     'description': 'Node Id',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'},
                    {'name': 'reachable',
                     'description': 'Specifies whether to return reachable '
                                    'state.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'boolean',
                     'defaultValue': False,
                     'paramType': 'query'},
                    {'name': 'runtime',
                     'description': 'Specifies whether to return runtime '
                                    'information.',
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
        Gets node runtime or reachable state.
        """
        args = self._args_parser.parse_args()
        get_reachable_state = verify_and_convert_bool(
            'reachable', args['reachable'])
        get_runtime_state = verify_and_convert_bool(
            'runtime', args['runtime'])
        get_state = verify_and_convert_bool('state', args['state'])

        reachable_state = None
        state = None
        if get_reachable_state or get_state:
            state = get_riemann_client().get_node_state(node_id)
            reachable_state = state['reachable']
            state = state['state']

        runtime_state = None
        state_version = None
        if get_runtime_state:
            try:
                node = get_storage_manager().get_node(node_id)
                runtime_state = node.runtime_info
                state_version = node.state_version
            except manager_exceptions.NotFoundError:
                runtime_state = {}

        return responses.DeploymentNode(id=node_id,
                                        state=state,
                                        reachable=reachable_state,
                                        runtime_info=runtime_state,
                                        state_version=state_version)

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="putNodeState",
        notes="Put node runtime state (state will be entirely replaced) " +
              "with the provided dictionary of keys and values.",
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
                                     reachable=None, state_version=None)
        node.state_version = get_storage_manager().put_node(node_id, node)
        return responses.DeploymentNode(**node.to_dict()), 201

    @swagger.operation(
        responseClass=responses.DeploymentNode,
        nickname="patchNodeState",
        notes="Update node runtime state. Expecting the request body to "
              "be a dictionary containing both 'runtime_info' - which is the"
              "updated keys/values information (possibly partial update), "
              "and 'state_version', which is used for optimistic locking "
              "during the update",
        parameters=[{'name': 'node_id',
                     'description': 'Node Id',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'},
                    {'name': 'body',
                     'description': 'Node state updated keys/values and '
                                    'state version',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=["application/json"]
    )
    @marshal_with(responses.DeploymentNode.resource_fields)
    @exceptions_handled
    def patch(self, node_id):
        """
        Updates node runtime state.
        """
        verify_json_content_type()
        if request.json.__class__ is not dict or len(request.json) > 2 \
            or 'runtime_info' not in request.json \
            or 'state_version' not in request.json \
            or request.json['runtime_info'].__class__ is not dict \
                or request.json['state_version'].__class__ is not int:

            if request.json.__class__ is not dict or len(request.json) > 2:
                message = 'request body is expected to be a map containing ' \
                          'only "runtime_info" and "state_version" fields'
            elif 'runtime_info' not in request.json:
                message = 'request body must be a map containing a ' \
                          '"runtime_info" field'
            elif 'state_version' not in request.json:
                message = 'request body must be a map containing a ' \
                          '"state_version" field'
            elif request.json['runtime_info'].__class__ is not dict:
                message = "request body's 'runtime_info' field must be a " \
                          "map but is of type {0}".format(
                              request.json['runtime_info'].__class__.__name__)
            else:
                message = "request body's 'state_version' field must be an " \
                          "int but is of type {0}".format(
                              request.json['state_version'].__class__.__name__)
            abort(400, message=message)

        node = models.DeploymentNode(
            id=node_id, runtime_info=request.json['runtime_info'],
            state_version=request.json['state_version'], reachable=None)
        get_storage_manager().update_node(node_id, node)
        return responses.DeploymentNode(
            **get_storage_manager().get_node(node_id).to_dict())


class DeploymentsIdExecutions(Resource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('statuses', type=str,
                                       default='false', location='args')

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions related to the provided"
              " deployment.",
        parameters=[{'name': 'statuses',
                     'description': 'Specifies whether to return reachable '
                                    'state for the nodes.',
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

        executions = [responses.Execution(**execution.to_dict()) for
                      execution in
                      get_storage_manager().get_deployment_executions(
                          deployment_id)]

        if get_executions_statuses:
            statuses_response = get_blueprints_manager()\
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
                    #execution not found in workflow service, return unknown
                    # values
                    execution.status, execution.error = None, None
        else:
            #setting None values to dynamic fields which weren't requested
            for execution in executions:
                execution.status, execution.error = None, None

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
                     'paramType': 'body'}],
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
        workflow_id = request.json['workflowId']
        execution = get_blueprints_manager().execute_workflow(deployment_id,
                                                              workflow_id)
        return responses.Execution(**execution.to_dict()), 201


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
