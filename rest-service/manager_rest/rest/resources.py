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

import collections
import os
import shutil

from datetime import datetime

from flask import (
    abort,
    current_app,
    request,
)
from flask_restful import types
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger
from flask_security import current_user

from sqlalchemy import (
    bindparam,
    func,
    literal_column,
)

from dsl_parser import utils as dsl_parser_utils

from manager_rest.security import SecuredResource
from manager_rest.constants import PROVIDER_CONTEXT_ID, SUPPORTED_ARCHIVE_TYPES
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.storage.models_base import db
from manager_rest.storage.resource_models import (
    Deployment,
    Execution,
    Event,
    Log,
)
from manager_rest.upload_manager import UploadedBlueprintsManager
from manager_rest import (config,
                          manager_exceptions,
                          get_version_data)
from manager_rest.storage import (models,
                                  get_storage_manager,
                                  ManagerElasticsearch)
from manager_rest.resource_manager import (get_resource_manager,
                                           ResourceManager)

from . import responses, requests_schema
from .rest_decorators import (exceptions_handled,
                              marshal_with,
                              insecure_rest_method)
from .rest_utils import (make_streaming_response,
                         verify_and_convert_bool,
                         get_json_and_verify_params,
                         get_args_and_verify_arguments)


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
        get_storage_manager().get(
            models.Blueprint,
            blueprint_id,
            include=['id']
        )

        for arc_type in SUPPORTED_ARCHIVE_TYPES:
            # attempting to find the archive file on the file system
            local_path = os.path.join(
                config.instance.file_server_root,
                config.instance.file_server_uploaded_blueprints_folder,
                blueprint_id,
                '{0}.{1}'.format(blueprint_id, arc_type))

            if os.path.isfile(local_path):
                archive_type = arc_type
                break
        else:
            raise RuntimeError("Could not find blueprint's archive; "
                               "Blueprint ID: {0}".format(blueprint_id))

        blueprint_path = '{0}/{1}/{2}/{2}.{3}'.format(
            config.instance.file_server_resources_uri,
            config.instance.file_server_uploaded_blueprints_folder,
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
        responseClass='List[{0}]'.format(models.Blueprint.__name__),
        nickname="list",
        notes="Returns a list of uploaded blueprints."
    )
    @exceptions_handled
    @marshal_with(models.Blueprint)
    def get(self, _include=None, **kwargs):
        """
        List uploaded blueprints
        """

        return get_storage_manager().list(
            models.Blueprint, include=_include).items


class BlueprintsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="getById",
        notes="Returns a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(models.Blueprint)
    def get(self, blueprint_id, _include=None, **kwargs):
        """
        Get blueprint by id
        """
        return get_storage_manager().get(
            models.Blueprint,
            blueprint_id,
            _include
        )

    @swagger.operation(
        responseClass=models.Blueprint,
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
    @marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        return UploadedBlueprintsManager().\
            receive_uploaded_data(data_id=blueprint_id)

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @exceptions_handled
    @marshal_with(models.Blueprint)
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        # Note: The current delete semantics are such that if a deployment
        # for the blueprint exists, the deletion operation will fail.
        # However, there is no handling of possible concurrency issue with
        # regard to that matter at the moment.
        blueprint = get_resource_manager().delete_blueprint(blueprint_id)

        # Delete blueprint resources from file server
        blueprint_folder = os.path.join(
            config.instance.file_server_root,
            config.instance.file_server_blueprints_folder,
            blueprint.id)
        shutil.rmtree(blueprint_folder)
        uploaded_blueprint_folder = os.path.join(
            config.instance.file_server_root,
            config.instance.file_server_uploaded_blueprints_folder,
            blueprint.id)
        shutil.rmtree(uploaded_blueprint_folder)

        return blueprint, 200


class Executions(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Execution.__name__),
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
    @marshal_with(models.Execution)
    def get(self, _include=None, **kwargs):
        """List executions"""
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False),
             Argument('include_system_workflows', type=types.boolean,
                      default=False)]
        )
        if args.deployment_id:
            get_storage_manager().get(
                models.Deployment,
                args.deployment_id,
                include=['id']
            )
        deployment_id_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id)
        return get_resource_manager().list_executions(
            is_include_system_workflows=args.include_system_workflows,
            include=_include,
            filters=deployment_id_filter).items

    @exceptions_handled
    @marshal_with(models.Execution)
    def post(self, **kwargs):
        """Execute a workflow"""
        request_dict = get_json_and_verify_params({'deployment_id',
                                                   'workflow_id'})

        allow_custom_parameters = verify_and_convert_bool(
            'allow_custom_parameters',
            request_dict.get('allow_custom_parameters', 'false'))
        force = verify_and_convert_bool(
            'force',
            request_dict.get('force', 'false'))

        deployment_id = request_dict['deployment_id']
        workflow_id = request_dict['workflow_id']
        parameters = request_dict.get('parameters', None)

        if parameters is not None and parameters.__class__ is not dict:
            raise manager_exceptions.BadParametersError(
                "request body's 'parameters' field must be a dict but"
                " is of type {0}".format(parameters.__class__.__name__))

        bypass_maintenance = is_bypass_maintenance_mode()
        execution = get_resource_manager().execute_workflow(
            deployment_id, workflow_id, parameters=parameters,
            allow_custom_parameters=allow_custom_parameters, force=force,
            bypass_maintenance=bypass_maintenance)
        return execution, 201


class ExecutionsId(SecuredResource):

    @swagger.operation(
        responseClass=models.Execution,
        nickname="getById",
        notes="Returns the execution state by its id.",
    )
    @exceptions_handled
    @marshal_with(models.Execution)
    def get(self, execution_id, _include=None, **kwargs):
        """
        Get execution by id
        """
        return get_storage_manager().get(
            models.Execution,
            execution_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Execution,
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
    @marshal_with(models.Execution)
    def post(self, execution_id, **kwargs):
        """
        Apply execution action (cancel, force-cancel) by id
        """
        request_dict = get_json_and_verify_params({'action'})
        action = request_dict['action']

        valid_actions = ['cancel', 'force-cancel']

        if action not in valid_actions:
            raise manager_exceptions.BadParametersError(
                'Invalid action: {0}, Valid action values are: {1}'.format(
                    action, valid_actions))

        if action in ('cancel', 'force-cancel'):
            return get_resource_manager().cancel_execution(
                execution_id, action == 'force-cancel')

    @swagger.operation(
        responseClass=models.Execution,
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
    @marshal_with(models.Execution)
    def patch(self, execution_id, **kwargs):
        """
        Update execution status by id
        """
        request_dict = get_json_and_verify_params({'status'})

        return get_resource_manager().update_execution_status(
            execution_id,
            request_dict['status'],
            request_dict.get('error', '')
        )


class Deployments(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Deployment.__name__),
        nickname="list",
        notes="Returns a list of existing deployments."
    )
    @exceptions_handled
    @marshal_with(models.Deployment)
    def get(self, _include=None, **kwargs):
        """
        List deployments
        """
        return get_storage_manager().list(
            models.Deployment, include=_include).items


class DeploymentsId(SecuredResource):
    @swagger.operation(
        responseClass=models.Deployment,
        nickname="getById",
        notes="Returns a deployment by its id."
    )
    @exceptions_handled
    @marshal_with(models.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        """
        Get deployment by id
        """
        return get_storage_manager().get(
            models.Deployment,
            deployment_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.Deployment,
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
    @marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        request_dict = get_json_and_verify_params({
            'blueprint_id': {},
            'inputs': {'optional': True, 'type': dict}
        })
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = get_args_and_verify_arguments(
            [Argument('private_resource', type=types.boolean, default=False)]
        )
        deployment = get_resource_manager().create_deployment(
            blueprint_id,
            deployment_id,
            inputs=request_dict.get('inputs', {}),
            bypass_maintenance=bypass_maintenance,
            private_resource=args.private_resource
        )
        return deployment, 201

    @swagger.operation(
        responseClass=models.Deployment,
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
    @marshal_with(models.Deployment)
    def delete(self, deployment_id, **kwargs):
        """
        Delete deployment by id
        """
        args = get_args_and_verify_arguments(
            [Argument('ignore_live_nodes', type=types.boolean, default=False)]
        )

        bypass_maintenance = is_bypass_maintenance_mode()

        deployment = get_resource_manager().delete_deployment(
            deployment_id, bypass_maintenance, args.ignore_live_nodes)

        # Delete deployment resources from file server
        deployment_folder = os.path.join(
            config.instance.file_server_root,
            config.instance.file_server_deployments_folder,
            deployment.id)
        if os.path.exists(deployment_folder):
            shutil.rmtree(deployment_folder)

        return deployment, 200


class DeploymentModifications(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
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
    @marshal_with(models.DeploymentModification)
    def post(self, **kwargs):
        request_dict = get_json_and_verify_params({
            'deployment_id': {},
            'context': {'optional': True, 'type': dict},
            'nodes': {'optional': True, 'type': dict}
        })
        deployment_id = request_dict['deployment_id']
        context = request_dict.get('context', {})
        nodes = request_dict.get('nodes', {})
        modification = get_resource_manager(). \
            start_deployment_modification(deployment_id, nodes, context)
        return modification, 201

    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.DeploymentModification.__name__),
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
    @marshal_with(models.DeploymentModification)
    def get(self, _include=None, **kwargs):
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False)]
        )
        deployment_id_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id)
        return get_storage_manager().list(
            models.DeploymentModification,
            filters=deployment_id_filter,
            include=_include
        ).items


class DeploymentModificationsId(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="getDeploymentModification",
        notes="Get deployment modification."
    )
    @exceptions_handled
    @marshal_with(models.DeploymentModification)
    def get(self, modification_id, _include=None, **kwargs):
        return get_storage_manager().get(
            models.DeploymentModification,
            modification_id,
            include=_include
        )


class DeploymentModificationsIdFinish(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="finishDeploymentModification",
        notes="Finish deployment modification."
    )
    @exceptions_handled
    @marshal_with(models.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_resource_manager().finish_deployment_modification(
            modification_id)


class DeploymentModificationsIdRollback(SecuredResource):

    @swagger.operation(
        responseClass=models.DeploymentModification,
        nickname="rollbackDeploymentModification",
        notes="Rollback deployment modification."
    )
    @exceptions_handled
    @marshal_with(models.DeploymentModification)
    def post(self, modification_id, **kwargs):
        return get_resource_manager().rollback_deployment_modification(
            modification_id)


class Nodes(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.Node.__name__),
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
    @marshal_with(models.Node)
    def get(self, _include=None, **kwargs):
        """
        List nodes
        """
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False),
             Argument('node_id', type=str, required=False)]
        )

        deployment_id = args.get('deployment_id')
        node_id = args.get('node_id')
        if deployment_id and node_id:
            try:
                nodes = [get_resource_manager().get_node(
                    deployment_id,
                    node_id
                )]
            except manager_exceptions.NotFoundError:
                nodes = []
        else:
            deployment_id_filter = ResourceManager.create_filters_dict(
                deployment_id=deployment_id)
            nodes = get_storage_manager().list(
                models.Node,
                filters=deployment_id_filter,
                include=_include
            ).items
        return nodes


class NodeInstances(SecuredResource):

    @swagger.operation(
        responseClass='List[{0}]'.format(models.NodeInstance.__name__),
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
    @marshal_with(models.NodeInstance)
    def get(self, _include=None, **kwargs):
        """
        List node instances
        """
        args = get_args_and_verify_arguments(
            [Argument('deployment_id', type=str, required=False),
             Argument('node_name', type=str, required=False)]
        )
        deployment_id = args.get('deployment_id')
        node_id = args.get('node_name')
        params_filter = ResourceManager.create_filters_dict(
            deployment_id=deployment_id, node_id=node_id)
        return get_storage_manager().list(
            models.NodeInstance,
            filters=params_filter,
            include=_include
        ).items


class NodeInstancesId(SecuredResource):

    @swagger.operation(
        responseClass=models.Node,
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
    @marshal_with(models.NodeInstance)
    def get(self, node_instance_id, _include=None, **kwargs):
        """
        Get node instance by id
        """
        return get_storage_manager().get(
            models.NodeInstance,
            node_instance_id,
            include=_include
        )

    @swagger.operation(
        responseClass=models.NodeInstance,
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
    @marshal_with(models.NodeInstance)
    def patch(self, node_instance_id, **kwargs):
        """Update node instance by id."""
        request_dict = get_json_and_verify_params(
            {'version': {'type': int}}
        )

        if not isinstance(request.json, collections.Mapping):
            raise manager_exceptions.BadParametersError(
                'Request body is expected to be a map containing a "version" '
                'field and optionally "runtimeProperties" and/or "state" '
                'fields')

        # Added for backwards compatibility with older client versions that
        # had version=0 by default
        version = request_dict['version'] or 1

        instance = get_storage_manager().get(
            models.NodeInstance,
            node_instance_id,
            locking=True
        )
        # Only update if new values were included in the request
        instance.runtime_properties = request_dict.get(
            'runtime_properties',
            instance.runtime_properties
        )
        instance.state = request_dict.get('state', instance.state)
        instance.version = version + 1
        return get_storage_manager().update(instance)


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
        outputs = get_resource_manager().evaluate_deployment_outputs(
            deployment_id)
        return dict(deployment_id=deployment_id, outputs=outputs)


class Events(SecuredResource):

    """Events resource.

    Throgh the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    @staticmethod
    def _build_select_query(_include, filters, pagination, sort):
        """Build query used to list events for a given execution.

        :param _include:
            Projection used to get records from database (not currently used)
        :type _include: list(str)
        :param filters:
            Filter selection. It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}
        :type filters: dict(str, str)
        :param pagination:
            Parameters used to limit results returned in a single query.
            Expected values `size` and `offset` are mapped into SQL as `LIMIT`
            and `OFFSET`.
        :type pagination: dict(str, int)
        :param sort:
            Result sorting order. The only allowed and expected value is to
            sort by timestamp in ascending order:
                {'timestamp': 'asc'}
        :type sort: dict(str, str)
        :returns:
            A SQL query that returns the events found that match the conditions
            passed as arguments.
        :rtype: :class:`sqlalchemy.sql.elements.TextClause`

        """
        if _include is not None:
            current_app.logger.error(
                'Projections with `_include` parameter are not supported')
            return abort(400)

        if not isinstance(filters, dict) or 'type' not in filters:
            current_app.logger.error('Filter by type is expected')
            return abort(400)

        if 'cloudify_event' not in filters['type']:
            current_app.logger.error(
                'At least `type=cloudify_event` filter is expected')
            return abort(400)

        query = (
            db.session.query(
                Event.timestamp.label('timestamp'),
                (
                    db.session.query(Deployment.id.label('deployment_id'))
                    .filter(Deployment.storage_id == Event.deployment_fk)
                    .subquery('deployment')
                ),
                Event.message,
                Event.message_code,
                Event.event_type,
                literal_column('NULL').label('logger'),
                literal_column('NULL').label('level'),
                literal_column("'cloudify_event'").label('type'),
            )
            .filter(
                Event.execution_fk == Execution.storage_id,
                Execution.id == bindparam('execution_id'),
            )
        )

        if 'cloudify_log' in filters['type']:
            query = query.union(
                db.session.query(
                    Log.timestamp.label('timestamp'),
                    (
                        db.session.query(Deployment.id.label('deployment_id'))
                        .filter(Deployment.storage_id == Log.deployment_fk)
                        .subquery('deployment')
                    ),
                    Log.message,
                    literal_column('NULL').label('message_code'),
                    literal_column('NULL').label('event_type'),
                    Log.logger,
                    Log.level,
                    literal_column("'cloudify_log'").label('type'),
                )
                .filter(
                    Log.execution_fk == Execution.storage_id,
                    Execution.id == bindparam('execution_id'),
                )
            )

        if (not isinstance(sort, dict) or
                '@timestamp' not in sort or
                sort['@timestamp'] != 'asc'):
            current_app.logger.error(
                'Sorting ascending by `timestamp` is expected')
            return abort(400)
        query = query.order_by('timestamp')

        if not isinstance(pagination, dict):
            current_app.logger.error(
                'Expected `pagination` parameter')
            return abort(400)

        if 'size' not in pagination:
            current_app.logger.error(
                'Expected `size` pagination parameter')
            return abort(400)

        query = query.limit(bindparam('limit'))

        if 'offset' not in pagination:
            current_app.logger.error(
                'Expected `offset` pagination parameter')
            return abort(400)

        query = query.offset(bindparam('offset'))

        return query

    @staticmethod
    def _build_count_query(filters):
        """Build query used to count events for a given execution.

        :param filters:
            Filter selection. It's used to decide if events:
                {'type': ['cloudify_event']}
            or both events and logs should be returned:
                {'type': ['cloudify_event', 'cloudify_log']}
        :type filters: dict(str, str)
        :returns:
            A SQL query that returns the number of events found that match the
            conditions passed as arguments.
        :rtype: :class:`sqlalchemy.sql.elements.TextClause`

        """
        if not isinstance(filters, dict) or 'type' not in filters:
            current_app.logger.error('Filter by type is expected')
            return abort(400)

        if 'cloudify_event' not in filters['type']:
            current_app.logger.error(
                'At least `type=cloudify_event` filter is expected')
            return abort(400)

        events_query = (
            db.session.query(func.count('*').label('count'))
            .filter(
                Event.execution_fk == Execution.storage_id,
                Execution.id == bindparam('execution_id'),
            )
        )

        if 'cloudify_log' in filters['type']:
            logs_query = (
                db.session.query(func.count('*').label('count'))
                .filter(
                    Log.execution_fk == Execution.storage_id,
                    Execution.id == bindparam('execution_id'),
                )
            )
            query = db.session.query(
                events_query.subquery().c.count +
                logs_query.subquery().c.count
            )
        else:
            query = db.session.query(events_query.subquery().c.count)

        return query

    @staticmethod
    def _map_event_to_es(sql_event):
        """Restructure event data as if it was returned by elasticsearch.

        This restructuration is needed because the API in the past used
        elasticsearch as the backend and the client implementation still
        expects data that has the same shape as elasticsearch would return.

        :param sql_event: Event data returned when SQL query was executed
        :type sql_event: :class:`sqlalchemy.util._collections.result`
        :returns: Event as would have returned by elasticsearch
        :rtype: dict(str)

        """
        event = {
            attr: getattr(sql_event, attr)
            for attr in sql_event.keys()
        }

        event['message'] = {
            'text': event['message']
        }
        event['context'] = {
            'deployment_id': event['deployment_id']
        }
        del event['deployment_id']
        if event['type'] == 'cloudify_event':
            event['message']['arguments'] = None
            del event['logger']
            del event['level']
        elif event['type'] == 'cloudify_log':
            del event['event_type']

        for key, value in event.items():
            if isinstance(value, datetime):
                event[key] = '{}Z'.format(value.isoformat()[:-3])
        return event

    def _query_events(self):
        """Query events using a SQL backend.

        :returns:
            Results using a format that resembles the one used by elasticsearch
            (more information about the format in :meth:`.._map_event_to_es`)
        :rtype: dict(str)

        """
        request_dict = get_json_and_verify_params()

        es_query = request_dict['query']['bool']

        _include = None
        # This is a trick based on the elasticsearch query pattern
        # - when only a filter is used it's in a 'must' section
        # - when multiple filters are used they're in a 'should' section
        if 'should' in es_query:
            filters = {'type': ['cloudify_event', 'cloudify_log']}
        else:
            filters = {'type': ['cloudify_event']}
        pagination = {
            'size': request_dict['size'],
            'offset': request_dict['from'],
        }
        sort = {
            field: value['order']
            for es_sort in request_dict['sort']
            for field, value in es_sort.items()
        }

        params = {
            'execution_id': (
                es_query['must'][0]['match']['context.execution_id']),
            'limit': request_dict['size'],
            'offset': request_dict['from'],
        }

        count_query = self._build_count_query(filters)
        total = db.engine.execute(count_query, params).scalar()

        select_query = self._build_select_query(
            _include, filters, pagination, sort)

        events = [
            self._map_event_to_es(event)
            for event in select_query.params(**params).all()
        ]

        results = {
            'hits': {
                'hits': [
                    {'_source': event}
                    for event in events
                ],
                'total': total,
            },
        }

        return results

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
        """List events using a SQL backend.

        :returns: Events found in the SQL backend
        :rtype: dict(str)

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
        request_dict = get_json_and_verify_params()
        return ManagerElasticsearch.search(
            index='cloudify_storage',
            body=request_dict)


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
                            'nginx.service': 'Webserver',
                            'postgresql-9.5.service': 'PostgreSQL'
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
        responseClass=models.ProviderContext,
        nickname="getContext",
        notes="Get the provider context"
    )
    @exceptions_handled
    @marshal_with(models.ProviderContext)
    def get(self, **kwargs):
        """
        Get provider context
        """
        return get_storage_manager().get(
            models.ProviderContext,
            PROVIDER_CONTEXT_ID
        )

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
        request_dict = get_json_and_verify_params({'context', 'name'})
        args = get_args_and_verify_arguments(
            [Argument('update', type=types.boolean, default=False)]
        )
        update = args['update']
        context = dict(
            id=PROVIDER_CONTEXT_ID,
            name=request_dict['name'],
            context=request_dict['context']
        )

        status_code = 200 if update else 201

        try:
            get_resource_manager().update_provider_context(update, context)
            return dict(status='ok'), status_code
        except dsl_parser_utils.ResolverInstantiationError, ex:
            raise manager_exceptions.ResolverInstantiationError(str(ex))


class Version(SecuredResource):

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
        request_dict = get_json_and_verify_params({
            'deployment_id': {},
            'context': {'optional': True, 'type': dict},
            'payload': {'type': dict}
        })

        deployment_id = request_dict['deployment_id']
        context = request_dict.get('context', {})
        payload = request_dict.get('payload')
        processed_payload = get_resource_manager().evaluate_functions(
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
        return dict(value=current_user.get_auth_token())
