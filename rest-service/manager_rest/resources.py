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

import os
import zipfile
import urllib
import shutil
from contextlib import contextmanager
from functools import wraps
from os import path

from flask import (
    request,
    make_response,
    current_app as app
)
from flask.ext.restful import Resource, marshal, reqparse
from flask_restful_swagger import swagger
from flask.ext.restful.utils import unpack
from flask_securest.rest_security import SECURED_MODE, SecuredResource

from dsl_parser import utils as dsl_parser_utils
from manager_rest import config
from manager_rest import models
from manager_rest import responses
from manager_rest import requests_schema
from manager_rest import archiving
from manager_rest import manager_exceptions
from manager_rest import utils
from manager_rest import responses_v2
from manager_rest.files import UploadedDataManager
from manager_rest.storage_manager import get_storage_manager
from manager_rest.blueprints_manager import (DslParseException,
                                             get_blueprints_manager,
                                             BlueprintsManager)
from manager_rest import get_version_data
from manager_rest.manager_elasticsearch import ManagerElasticsearch


CONVENTION_APPLICATION_BLUEPRINT_FILE = 'blueprint.yaml'

SUPPORTED_ARCHIVE_TYPES = ['zip', 'tar', 'tar.gz', 'tar.bz2']


def insecure_rest_method(func):
    """block an insecure REST method if manager disabled insecure endpoints
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        cfg = config.instance()
        if cfg.insecure_endpoints_disabled:
            raise manager_exceptions.MethodNotAllowedError()
        return func(*args, **kwargs)
    return wrapper


def exceptions_handled(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except manager_exceptions.ManagerException as e:
            utils.abort_error(e, app.logger)
    return wrapper


def _is_include_parameter_in_request():
    return '_include' in request.args and request.args['_include']


def _get_fields_to_include(model_fields):
    if _is_include_parameter_in_request():
        include = set(request.args['_include'].split(','))
        include_fields = {}
        illegal_fields = None
        for field in include:
            if field not in model_fields:
                if not illegal_fields:
                    illegal_fields = []
                illegal_fields.append(field)
                continue
            include_fields[field] = model_fields[field]
        if illegal_fields:
            raise manager_exceptions.NoSuchIncludeFieldError(
                'Illegal include fields: [{}] - available fields: '
                '[{}]'.format(', '.join(illegal_fields),
                              ', '.join(model_fields.keys())))
        return include_fields
    return model_fields


@contextmanager
def skip_nested_marshalling():
    request.__skip_marshalling = True
    yield
    delattr(request, '__skip_marshalling')


class marshal_with(object):
    def __init__(self, response_class):
        """
        :param response_class: response class to marshal result with.
         class must have a "resource_fields" class variable
        """
        if not hasattr(response_class, 'resource_fields'):
            raise RuntimeError(
                'Response class {0} does not contain a "resource_fields" '
                'class variable'.format(type(response_class)))
        self.response_class = response_class

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if hasattr(request, '__skip_marshalling'):
                return f(*args, **kwargs)

            fields_to_include = _get_fields_to_include(
                self.response_class.resource_fields)
            if _is_include_parameter_in_request():
                # only pushing "_include" into kwargs when the request
                # contained this parameter, to keep things cleaner (identical
                # behavior for passing "_include" which contains all fields)
                kwargs['_include'] = fields_to_include.keys()

            response = f(*args, **kwargs)

            if isinstance(response, responses_v2.ListResponse):
                wrapped_items = self.wrap_with_response_object(response.items)
                response.items = marshal(wrapped_items, fields_to_include)
                return marshal(response,
                               responses_v2.ListResponse.resource_fields)
            if isinstance(response, tuple):
                data, code, headers = unpack(response)
                data = self.wrap_with_response_object(data)
                return marshal(data, fields_to_include), code, headers
            else:
                response = self.wrap_with_response_object(response)
                return marshal(response, fields_to_include)

        return wrapper

    def wrap_with_response_object(self, data):
        if isinstance(data, dict):
            return self.response_class(**data)
        elif isinstance(data, list):
            return map(self.wrap_with_response_object, data)
        elif isinstance(data, models.SerializableObject):
            return self.wrap_with_response_object(data.to_dict())
        raise RuntimeError('Unexpected response data type {0}'.format(
            type(data)))


def verify_json_content_type():
    if request.content_type != 'application/json':
        raise manager_exceptions.UnsupportedContentTypeError(
            'Content type must be application/json')


def verify_parameter_in_request_body(param,
                                     request_json,
                                     param_type=None,
                                     optional=False):
    if param not in request_json:
        if optional:
            return
        raise manager_exceptions.BadParametersError(
            'Missing {0} in json request body'.format(param))
    if param_type and not isinstance(request_json[param], param_type):
        raise manager_exceptions.BadParametersError(
            '{0} parameter is expected to be of type {1} but is of type '
            '{2}'.format(param,
                         param_type.__name__,
                         type(request_json[param]).__name__))


def verify_and_convert_bool(attribute_name, str_bool):
    if isinstance(str_bool, bool):
        return str_bool
    if str_bool.lower() == 'true':
        return True
    if str_bool.lower() == 'false':
        return False
    raise manager_exceptions.BadParametersError(
        '{0} must be <true/false>, got {1}'.format(attribute_name, str_bool))


def make_streaming_response(res_id, res_path, content_length, archive_type):
    response = make_response()
    response.headers['Content-Description'] = 'File Transfer'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = \
        'attachment; filename={0}.{1}'.format(res_id, archive_type)
    response.headers['Content-Length'] = content_length
    response.headers['X-Accel-Redirect'] = res_path
    response.headers['X-Accel-Buffering'] = 'yes'
    return response


class UploadedBlueprintsManager(UploadedDataManager):

    def _get_kind(self):
        return 'blueprint'

    def _get_data_url_key(self):
        return 'blueprint_archive_url'

    def _get_target_dir_path(self):
        return config.instance().file_server_uploaded_blueprints_folder

    def _get_archive_type(self, archive_path):
        return archiving.get_archive_type(archive_path)

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path):
        application_dir = self._extract_file_to_file_server(
            file_server_root,
            archive_target_path)
        return self._prepare_and_submit_blueprint(file_server_root,
                                                  application_dir,
                                                  data_id), None

    @classmethod
    def _process_plugins(cls, file_server_root, blueprint_id):
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
            cls._zip_dir(plugin_dir, target_zip_path)

    @classmethod
    def _zip_dir(cls, dir_to_zip, target_zip_path):
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

    @classmethod
    def _extract_file_to_file_server(cls, file_server_root,
                                     archive_target_path):
        return utils.extract_blueprint_archive_to_mgr(archive_target_path,
                                                      file_server_root)

    @classmethod
    def _prepare_and_submit_blueprint(cls, file_server_root,
                                      app_dir,
                                      blueprint_id):

        app_dir, app_file_name = cls._extract_application_file(
            file_server_root, app_dir)

        file_server_base_url = '{0}/'.format(
            config.instance().file_server_base_uri)

        # add to blueprints manager (will also dsl_parse it)
        try:
            blueprint = get_blueprints_manager().publish_blueprint(
                app_dir,
                app_file_name,
                file_server_base_url,
                blueprint_id)

            # moving the app directory in the file server to be under a
            # directory named after the blueprint id
            shutil.move(os.path.join(file_server_root, app_dir),
                        os.path.join(
                            file_server_root,
                            config.instance().file_server_blueprints_folder,
                            blueprint.id))
            cls._process_plugins(file_server_root, blueprint.id)
            return blueprint
        except DslParseException, ex:
            shutil.rmtree(os.path.join(file_server_root, app_dir))
            raise manager_exceptions.InvalidBlueprintError(
                'Invalid blueprint - {0}'.format(ex.message))

    @classmethod
    def _extract_application_file(cls, file_server_root, application_dir):

        full_application_dir = path.join(file_server_root, application_dir)

        if 'application_file_name' in request.args:
            application_file_name = urllib.unquote(
                request.args['application_file_name']).decode('utf-8')
            application_file = path.join(full_application_dir,
                                         application_file_name)
            if not path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                    '{0} does not exist in the application '
                    'directory'.format(application_file_name)
                )
        else:
            application_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE
            application_file = path.join(full_application_dir,
                                         application_file_name)
            if not path.isfile(application_file):
                raise manager_exceptions.BadParametersError(
                    'application directory is missing blueprint.yaml and '
                    'application_file_name query parameter was not passed')

        # return relative path from the file server root since this path
        # is appended to the file server base uri
        return application_dir, application_file_name


class BlueprintsIdArchive(SecuredResource):

    @swagger.operation(
        nickname="getArchive",
        notes="Downloads blueprint as an archive."
    )
    @exceptions_handled
    def get(self, blueprint_id, **kwargs):
        """
        Download blueprint's archive
        """
        # Verify blueprint exists.
        get_blueprints_manager().get_blueprint(blueprint_id, {'id'})

        for arc_type in SUPPORTED_ARCHIVE_TYPES:
            # attempting to find the archive file on the file system
            local_path = os.path.join(
                config.instance().file_server_root,
                config.instance().file_server_uploaded_blueprints_folder,
                blueprint_id,
                '{0}.{1}'.format(blueprint_id, arc_type))

            if os.path.isfile(local_path):
                archive_type = arc_type
                break
        else:
            raise RuntimeError("Could not find blueprint's archive; "
                               "Blueprint ID: {0}".format(blueprint_id))

        blueprint_path = '{0}/{1}/{2}/{2}.{3}'.format(
            config.instance().file_server_resources_uri,
            config.instance().file_server_uploaded_blueprints_folder,
            blueprint_id,
            archive_type)

        return make_streaming_response(
            blueprint_id,
            blueprint_path,
            os.path.getsize(local_path),
            archive_type
        )


class Blueprints(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.BlueprintState.__name__),
        nickname="list",
        notes="Returns a list of uploaded blueprints."
    )
    @exceptions_handled
    @marshal_with(responses.BlueprintState)
    def get(self, _include=None, **kwargs):
        """
        List uploaded blueprints
        """

        blueprints = get_blueprints_manager().blueprints_list(
            include=_include)
        return blueprints.items


class BlueprintsId(SecuredResource):

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(responses.BlueprintState)
    def get(self, blueprint_id, _include=None, **kwargs):
        """
        Get blueprint by id
        """
        return get_blueprints_manager().get_blueprint(blueprint_id, _include)

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="upload",
        notes="Submitted blueprint should be an archive "
              "containing the directory which contains the blueprint. "
              "Archive format may be zip, tar, tar.gz or tar.bz2."
              " Blueprint archive may be submitted via either URL or by "
              "direct upload.",
        parameters=[{'name': 'application_file_name',
                     'description': 'File name of yaml '
                                    'containing the "main" blueprint.',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query',
                     'defaultValue': 'blueprint.yaml'},
                    {'name': 'blueprint_archive_url',
                     'description': 'url of a blueprint archive file',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'},
                    {
                        'name': 'body',
                        'description': 'Binary form of the tar '
                                       'gzipped blueprint directory',
                        'required': True,
                        'allowMultiple': False,
                        'dataType': 'binary',
                        'paramType': 'body'}],
        consumes=[
            "application/octet-stream"
        ]

    )
    @exceptions_handled
    @marshal_with(responses.BlueprintState)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        return UploadedBlueprintsManager().receive_uploaded_data(blueprint_id)

    @swagger.operation(
        responseClass=responses.BlueprintState,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(responses.BlueprintState)
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
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

        return blueprint, 200


class Executions(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Execution.__name__),
        nickname="list",
        notes="Returns a list of executions for the optionally provided "
              "deployment id.",
        parameters=[{'name': 'deployment_id',
                     'description': 'List execution of a specific deployment',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'defaultValue': None,
                     'paramType': 'query'},
                    {'name': 'include_system_workflows',
                     'description': 'Include executions of system workflows',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'bool',
                     'defaultValue': False,
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(responses.Execution)
    def get(self, _include=None, **kwargs):
        """List executions"""
        deployment_id = request.args.get('deployment_id')
        if deployment_id:
            get_blueprints_manager().get_deployment(deployment_id,
                                                    include=['id'])
        is_include_system_workflows = verify_and_convert_bool(
            'include_system_workflows',
            request.args.get('include_system_workflows', 'false'))

        deployment_id_filter = BlueprintsManager.create_filters_dict(
            deployment_id=deployment_id)
        executions = get_blueprints_manager().executions_list(
            is_include_system_workflows=is_include_system_workflows,
            include=_include,
            filters=deployment_id_filter)
        return executions.items

    @exceptions_handled
    @marshal_with(responses.Execution)
    def post(self, **kwargs):
        """Execute a workflow"""
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('deployment_id', request_json)
        verify_parameter_in_request_body('workflow_id', request_json)

        allow_custom_parameters = verify_and_convert_bool(
            'allow_custom_parameters',
            request_json.get('allow_custom_parameters', 'false'))
        force = verify_and_convert_bool(
            'force',
            request_json.get('force', 'false'))

        deployment_id = request.json['deployment_id']
        workflow_id = request.json['workflow_id']
        parameters = request.json.get('parameters', None)

        if parameters is not None and parameters.__class__ is not dict:
            raise manager_exceptions.BadParametersError(
                "request body's 'parameters' field must be a dict but"
                " is of type {0}".format(parameters.__class__.__name__))

        execution = get_blueprints_manager().execute_workflow(
            deployment_id, workflow_id, parameters=parameters,
            allow_custom_parameters=allow_custom_parameters, force=force)
        return execution, 201


class ExecutionsId(SecuredResource):

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="getById",
        notes="Returns the execution state by its id.",
    )
    @exceptions_handled
    @marshal_with(responses.Execution)
    def get(self, execution_id, _include=None, **kwargs):
        """
        Get execution by id
        """
        return get_blueprints_manager().get_execution(execution_id,
                                                      include=_include)

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="modify_state",
        notes="Modifies a running execution state (currently, only cancel"
              " and force-cancel are supported)",
        parameters=[{'name': 'body',
                     'description': 'json with an action key. '
                                    'Legal values for action are: [cancel,'
                                    ' force-cancel]',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.ModifyExecutionRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.Execution)
    def post(self, execution_id, **kwargs):
        """
        Apply execution action (cancel, force-cancel) by id
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('action', request_json)
        action = request.json['action']

        valid_actions = ['cancel', 'force-cancel']

        if action not in valid_actions:
            raise manager_exceptions.BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        if action in ('cancel', 'force-cancel'):
            return get_blueprints_manager().cancel_execution(
                execution_id, action == 'force-cancel')

    @swagger.operation(
        responseClass=responses.Execution,
        nickname="updateExecutionStatus",
        notes="Updates the execution's status",
        parameters=[{'name': 'status',
                     'description': "The execution's new status",
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'},
                    {'name': 'error',
                     'description': "An error message. If omitted, "
                                    "error will be updated to an empty "
                                    "string",
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.Execution)
    def patch(self, execution_id, **kwargs):
        """
        Update execution status by id
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('status', request_json)

        get_blueprints_manager().update_execution_status(
            execution_id,
            request_json['status'],
            request_json.get('error', ''))

        return get_storage_manager().get_execution(execution_id)


class Deployments(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Deployment.__name__),
        nickname="list",
        notes="Returns a list of existing deployments."
    )
    @exceptions_handled
    @marshal_with(responses.Deployment)
    def get(self, _include=None, **kwargs):
        """
        List deployments
        """
        deployments = get_blueprints_manager().deployments_list(
            include=_include)
        return deployments.items


class DeploymentsId(SecuredResource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('ignore_live_nodes', type=str,
                                       default='false', location='args')

    @swagger.operation(
        responseClass=responses.Deployment,
        nickname="getById",
        notes="Returns a deployment by its id."
    )
    @exceptions_handled
    @marshal_with(responses.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        """
        Get deployment by id
        """
        return get_blueprints_manager().get_deployment(deployment_id,
                                                       include=_include)

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
    @exceptions_handled
    @marshal_with(responses.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('blueprint_id', request_json)
        verify_parameter_in_request_body('inputs',
                                         request_json,
                                         param_type=dict,
                                         optional=True)
        blueprint_id = request.json['blueprint_id']
        deployment = get_blueprints_manager().create_deployment(
            blueprint_id, deployment_id, inputs=request_json.get('inputs', {}))
        return deployment, 201

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
    @exceptions_handled
    @marshal_with(responses.Deployment)
    def delete(self, deployment_id, **kwargs):
        """
        Delete deployment by id
        """
        args = self._args_parser.parse_args()

        ignore_live_nodes = verify_and_convert_bool(
            'ignore_live_nodes', args['ignore_live_nodes'])

        deployment = get_blueprints_manager().delete_deployment(
            deployment_id, ignore_live_nodes)

        # Delete deployment resources from file server
        deployment_folder = os.path.join(
            config.instance().file_server_root,
            config.instance().file_server_deployments_folder,
            deployment.id)
        if os.path.exists(deployment_folder):
            shutil.rmtree(deployment_folder)

        return deployment, 200


class DeploymentModifications(SecuredResource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('deployment_id',
                                       type=str,
                                       required=False,
                                       location='args')

    @swagger.operation(
        responseClass=responses.DeploymentModification,
        nickname="modifyDeployment",
        notes="Modify deployment.",
        parameters=[{'name': 'body',
                     'description': 'Deployment modification specification',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.
                    DeploymentModificationRequest.__name__,
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentModification)
    def post(self, **kwargs):
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('deployment_id', request_json)
        deployment_id = request_json['deployment_id']
        verify_parameter_in_request_body('context',
                                         request_json,
                                         param_type=dict,
                                         optional=True)
        context = request_json.get('context', {})
        verify_parameter_in_request_body('nodes',
                                         request_json,
                                         param_type=dict,
                                         optional=True)
        nodes = request_json.get('nodes', {})
        modification = get_blueprints_manager(). \
            start_deployment_modification(deployment_id, nodes, context)
        return modification, 201

    @swagger.operation(
        responseClass='List[{0}]'.format(
            responses.DeploymentModification.__name__),
        nickname="listDeploymentModifications",
        notes="List deployment modifications.",
        parameters=[{'name': 'deployment_id',
                     'description': 'Deployment id',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentModification)
    def get(self, _include=None, **kwargs):
        args = self._args_parser.parse_args()
        deployment_id = args.get('deployment_id')
        deployment_id_filter = BlueprintsManager.create_filters_dict(
            deployment_id=deployment_id)
        modifications = get_storage_manager().deployment_modifications_list(
            filters=deployment_id_filter, include=_include)
        return modifications.items


class DeploymentModificationsId(SecuredResource):

    @swagger.operation(
        responseClass=responses.DeploymentModification,
        nickname="getDeploymentModification",
        notes="Get deployment modification."
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentModification)
    def get(self, modification_id, _include=None, **kwargs):
        return get_storage_manager().get_deployment_modification(
            modification_id, include=_include)


class DeploymentModificationsIdFinish(SecuredResource):

    @swagger.operation(
        responseClass=responses.DeploymentModification,
        nickname="finishDeploymentModification",
        notes="Finish deployment modification."
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_blueprints_manager().finish_deployment_modification(
            modification_id)


class DeploymentModificationsIdRollback(SecuredResource):

    @swagger.operation(
        responseClass=responses.DeploymentModification,
        nickname="rollbackDeploymentModification",
        notes="Rollback deployment modification."
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_blueprints_manager().rollback_deployment_modification(
            modification_id)


class Nodes(SecuredResource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('deployment_id',
                                       type=str,
                                       required=False,
                                       location='args')
        self._args_parser.add_argument('node_id',
                                       type=str,
                                       required=False,
                                       location='args')

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.Node.__name__),
        nickname="listNodes",
        notes="Returns nodes list according to the provided query parameters.",
        parameters=[{'name': 'deployment_id',
                     'description': 'Deployment id',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(responses.Node)
    def get(self, _include=None, **kwargs):
        """
        List nodes
        """
        args = self._args_parser.parse_args()
        deployment_id = args.get('deployment_id')
        node_id = args.get('node_id')
        if deployment_id and node_id:
            try:
                nodes = [get_storage_manager().get_node(deployment_id,
                                                        node_id)]
            except manager_exceptions.NotFoundError:
                nodes = []
        else:
            deployment_id_filter = BlueprintsManager.create_filters_dict(
                deployment_id=deployment_id)
            nodes = get_storage_manager().get_nodes(
                filters=deployment_id_filter, include=_include).items
        return nodes


class NodeInstances(SecuredResource):

    def __init__(self):
        self._args_parser = reqparse.RequestParser()
        self._args_parser.add_argument('deployment_id',
                                       type=str,
                                       required=False,
                                       location='args')
        self._args_parser.add_argument('node_name',
                                       type=str,
                                       required=False,
                                       location='args')

    @swagger.operation(
        responseClass='List[{0}]'.format(responses.NodeInstance.__name__),
        nickname="listNodeInstances",
        notes="Returns node instances list according to the provided query"
              " parameters.",
        parameters=[{'name': 'deployment_id',
                     'description': 'Deployment id',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'},
                    {'name': 'node_name',
                     'description': 'node name',
                     'required': False,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'query'}]
    )
    @exceptions_handled
    @marshal_with(responses.NodeInstance)
    def get(self, _include=None, **kwargs):
        """
        List node instances
        """
        args = self._args_parser.parse_args()
        deployment_id = args.get('deployment_id')
        node_id = args.get('node_name')
        params_filter = BlueprintsManager.create_filters_dict(
            deployment_id=deployment_id, node_id=node_id)
        node_instances = get_storage_manager().get_node_instances(
            filters=params_filter, include=_include)
        return node_instances.items


class NodeInstancesId(SecuredResource):

    @swagger.operation(
        responseClass=responses.Node,
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
    @exceptions_handled
    @marshal_with(responses.NodeInstance)
    def get(self, node_instance_id, _include=None, **kwargs):
        """
        Get node instance by id
        """
        return get_storage_manager().get_node_instance(node_instance_id,
                                                       include=_include)

    @swagger.operation(
        responseClass=responses.NodeInstance,
        nickname="patchNodeState",
        notes="Update node instance. Expecting the request body to "
              "be a dictionary containing 'version' which is used for "
              "optimistic locking during the update, and optionally "
              "'runtime_properties' (dictionary) and/or 'state' (string) "
              "properties",
        parameters=[{'name': 'node_instance_id',
                     'description': 'Node instance identifier',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': 'string',
                     'paramType': 'path'},
                    {'name': 'version',
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
    @exceptions_handled
    @marshal_with(responses.NodeInstance)
    def patch(self, node_instance_id, **kwargs):
        """
        Update node instance by id
        """
        verify_json_content_type()
        if request.json.__class__ is not dict or \
            'version' not in request.json or \
                request.json['version'].__class__ is not int:

            if request.json.__class__ is not dict:
                message = 'Request body is expected to be a map containing ' \
                          'a "version" field and optionally ' \
                          '"runtimeProperties" and/or "state" fields'
            elif 'version' not in request.json:
                message = 'Request body must be a map containing a ' \
                          '"version" field'
            else:
                message = \
                    "request body's 'version' field must be an int but" \
                    " is of type {0}".format(request.json['version']
                                             .__class__.__name__)
            raise manager_exceptions.BadParametersError(message)

        node = models.DeploymentNodeInstance(
            id=node_instance_id,
            node_id=None,
            relationships=None,
            host_id=None,
            deployment_id=None,
            scaling_groups=None,
            runtime_properties=request.json.get('runtime_properties'),
            state=request.json.get('state'),
            version=request.json['version'])
        get_storage_manager().update_node_instance(node)
        return get_storage_manager().get_node_instance(node_instance_id)


class DeploymentsIdOutputs(SecuredResource):

    @swagger.operation(
        responseClass=responses.DeploymentOutputs.__name__,
        nickname="get",
        notes="Gets a specific deployment outputs."
    )
    @exceptions_handled
    @marshal_with(responses.DeploymentOutputs)
    def get(self, deployment_id, **kwargs):
        """Get deployment outputs"""
        outputs = get_blueprints_manager().evaluate_deployment_outputs(
            deployment_id)
        return dict(deployment_id=deployment_id, outputs=outputs)


class Events(SecuredResource):

    @staticmethod
    def _query_events():
        """
        List events for the provided Elasticsearch query
        """
        verify_json_content_type()
        return ManagerElasticsearch.search_events(body=request.json)

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
    @exceptions_handled
    @insecure_rest_method
    def get(self, **kwargs):
        """
        List events for the provided Elasticsearch query
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
    @exceptions_handled
    @insecure_rest_method
    def post(self, **kwargs):
        """
        List events for the provided Elasticsearch query
        """
        return self._query_events()


class Search(SecuredResource):

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
    @exceptions_handled
    @insecure_rest_method
    def post(self, **kwargs):
        """
        Search using an Elasticsearch query
        """
        verify_json_content_type()
        return ManagerElasticsearch.search(
            index='cloudify_storage',
            body=request.json)


class Status(SecuredResource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of running system services"
    )
    @exceptions_handled
    @marshal_with(responses.Status)
    def get(self, **kwargs):
        """
        Get the status of running system services
        """
        try:
            if self._is_docker_env():
                job_list = {'riemann': 'Riemann',
                            'rabbitmq-server': 'RabbitMQ',
                            'celeryd-cloudify-management': 'Celery Management',
                            'elasticsearch': 'Elasticsearch',
                            'cloudify-ui': 'Cloudify UI',
                            'logstash': 'Logstash',
                            'nginx': 'Webserver',
                            'rest-service': 'Manager Rest-Service',
                            'amqp-influx': 'AMQP InfluxDB'
                            }
                from manager_rest.runitsupervise import get_services
                jobs = get_services(job_list)
            else:
                from manager_rest.systemddbus import get_services
                job_list = {'cloudify-mgmtworker.service': 'Celery Management',
                            'cloudify-restservice.service':
                                'Manager Rest-Service',
                            'cloudify-amqpinflux.service': 'AMQP InfluxDB',
                            'cloudify-influxdb.service': 'InfluxDB',
                            'cloudify-rabbitmq.service': 'RabbitMQ',
                            'cloudify-riemann.service': 'Riemann',
                            'cloudify-webui.service': 'Cloudify UI',
                            'elasticsearch.service': 'Elasticsearch',
                            'logstash.service': 'Logstash',
                            'nginx.service': 'Webserver'
                            }
                jobs = get_services(job_list)
        except ImportError:
            jobs = ['undefined']

        return dict(status='running', services=jobs)

    @staticmethod
    def _is_docker_env():
        return os.getenv('DOCKER_ENV') is not None


class ProviderContext(SecuredResource):

    @swagger.operation(
        responseClass=responses.ProviderContext,
        nickname="getContext",
        notes="Get the provider context"
    )
    @exceptions_handled
    @marshal_with(responses.ProviderContext)
    def get(self, _include=None, **kwargs):
        """
        Get provider context
        """
        return get_storage_manager().get_provider_context(include=_include)

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
    @exceptions_handled
    @marshal_with(responses.ProviderContextPostStatus)
    def post(self, **kwargs):
        """
        Create provider context
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('context', request_json)
        verify_parameter_in_request_body('name', request_json)
        context = models.ProviderContext(name=request.json['name'],
                                         context=request.json['context'])
        update = verify_and_convert_bool(
            'update',
            request.args.get('update', 'false')
        )

        status_code = 200 if update else 201

        try:
            get_blueprints_manager().update_provider_context(update, context)
            return dict(status='ok'), status_code
        except dsl_parser_utils.ResolverInstantiationError, ex:
            raise manager_exceptions.ResolverInstantiationError(str(ex))


class Version(Resource):

    @swagger.operation(
        responseClass=responses.Version,
        nickname="version",
        notes="Returns version information for this rest service"
    )
    @exceptions_handled
    @marshal_with(responses.Version)
    def get(self, **kwargs):
        """
        Get version information
        """
        return get_version_data()


class EvaluateFunctions(SecuredResource):

    @swagger.operation(
        responseClass=responses.EvaluatedFunctions,
        nickname='evaluateFunctions',
        notes="Evaluate provided payload for intrinsic functions",
        parameters=[{'name': 'body',
                     'description': '',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.EvaluateFunctionsRequest.__name__,  # noqa
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.EvaluatedFunctions)
    def post(self, **kwargs):
        """
        Evaluate intrinsic in payload
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('deployment_id', request_json)
        verify_parameter_in_request_body('context', request_json,
                                         optional=True,
                                         param_type=dict)
        verify_parameter_in_request_body('payload', request_json,
                                         param_type=dict)

        deployment_id = request_json['deployment_id']
        context = request_json.get('context', {})
        payload = request_json.get('payload')
        processed_payload = get_blueprints_manager().evaluate_functions(
            deployment_id=deployment_id,
            context=context,
            payload=payload)
        return dict(deployment_id=deployment_id, payload=processed_payload)


class Tokens(SecuredResource):

    @swagger.operation(
        responseClass=responses.Tokens,
        nickname="get auth token for the request user",
        notes="Generate authentication token for the request user",
    )
    @exceptions_handled
    @marshal_with(responses.Tokens)
    def get(self, **kwargs):
        """
        Get authentication token
        """
        if not app.config.get(SECURED_MODE):
            raise manager_exceptions.AppNotSecuredError(
                'token generation not supported, application is not secured')

        if not hasattr(app, 'auth_token_generator'):
            raise manager_exceptions.NoTokenGeneratorError(
                'token generation not supported, an auth token generator was '
                'not registered')

        token = app.auth_token_generator.generate_auth_token()
        return dict(value=token)
