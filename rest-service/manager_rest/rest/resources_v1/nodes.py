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

from typing import Any, Dict, Optional

import pydantic
from flask import request

from manager_rest import manager_exceptions
from manager_rest.resource_manager import ResourceManager
from manager_rest.rest import swagger
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import is_deployment_update
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (
    get_storage_manager,
    models,
    get_node
)


class _NodesListQuery(pydantic.BaseModel):
    deployment_id: Optional[str] = None
    node_id: Optional[str] = None


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
    @authorize('node_list')
    @marshal_with(models.Node)
    def get(self, _include=None, **kwargs):
        """List nodes"""
        args = _NodesListQuery.parse_obj(request.args)

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


class _InstancesListQuery(pydantic.BaseModel):
    deployment_id: Optional[str] = None
    node_name: Optional[str] = None


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
    @authorize('node_instance_list')
    @marshal_with(models.NodeInstance)
    def get(self, _include=None, **kwargs):
        """List node instances"""
        args = _InstancesListQuery.parse_obj(request.args)
        params_filter = ResourceManager.create_filters_dict(
            deployment_id=args.deployment_id, node_id=args.node_id)
        return get_storage_manager().list(
            models.NodeInstance,
            filters=params_filter,
            include=_include
        ).items


class _NodeInstanceUpdateArgs(pydantic.BaseModel):
    version: int
    runtime_properties: Optional[Dict[str, Any]] = None
    system_properties: Optional[Dict[str, Any]] = None
    relationships: Optional[Any] = None
    state: Optional[str] = None


class _NodeInstanceUpdateQuery(pydantic.BaseModel):
    force: Optional[bool] = False


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
    @authorize('node_instance_get')
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
    @authorize('node_instance_update')
    @marshal_with(models.NodeInstance)
    def patch(self, node_instance_id, **kwargs):
        """Update node instance by id."""
        request_dict = _NodeInstanceUpdateArgs.parse_obj(request.json).dict()
        version = request_dict['version'] or 1
        force = _NodeInstanceUpdateQuery.parse_obj(request.args).force

        sm = get_storage_manager()
        with sm.transaction():
            instance = sm.get(
                models.NodeInstance,
                node_instance_id,
                locking=True,
            )
            if request_dict.keys() | {
                'runtime_properties', 'state', 'system_properties'
            }:
                # Added for backwards compatibility with older client versions
                # that had version=0 by default
                if not force and instance.version > version:
                    raise manager_exceptions.ConflictError(
                        'Node instance update conflict [current version='
                        f'{instance.version}, update version={version}]'
                    )
                if request_dict['runtime_properties'] is not None:
                    instance.runtime_properties = \
                        request_dict['runtime_properties']
                if request_dict['system_properties'] is not None:
                    old_properties = instance.system_properties
                    instance.system_properties = \
                        request_dict['system_properties']
                    self._process_system_properties(instance, old_properties)
                if request_dict['state'] is not None:
                    instance.state = request_dict['state']
            if request_dict['relationships'] is not None:
                if not is_deployment_update():
                    raise manager_exceptions.OnlyDeploymentUpdate()
                instance.relationships = request_dict['relationships']
            return sm.update(instance)

    def _process_system_properties(self, instance, old_properties):
        if instance.system_properties == old_properties:
            # nothing changed, so nothing to do
            return
        instance.update_configuration_drift()
        instance.update_status_check()
