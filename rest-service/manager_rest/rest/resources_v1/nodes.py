#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

from flask import request
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from manager_rest import manager_exceptions
from manager_rest.resource_manager import ResourceManager
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
)
from manager_rest.security import SecuredResource
from manager_rest.storage import (
    get_storage_manager,
    models,
    get_node
)


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
                nodes = [get_node(deployment_id, node_id)]
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
