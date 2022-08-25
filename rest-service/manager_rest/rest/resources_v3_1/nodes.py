import pydantic
from collections import defaultdict
from typing import Any, List, Dict, Optional

from flask import request

from ..resources_v3 import (
    Nodes as v3_Nodes,
    NodeInstancesId as v3_NodeInstancesId,
)
from ..resources_v2 import NodeInstances as v2_NodeInstances

from manager_rest.rest import rest_utils
from manager_rest.rest.rest_decorators import only_deployment_update
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_base import db
from manager_rest.security import SecuredResource


class _CreateNodesArgs(pydantic.BaseModel):
    deployment_id: str
    nodes: List[Dict[str, Any]]


class Nodes(v3_Nodes):
    @authorize('node_list')
    def post(self):
        args = _CreateNodesArgs.parse_obj(request.json)
        sm = get_storage_manager()
        raw_nodes = args.nodes

        if not raw_nodes:
            return "", 204
        with sm.transaction():
            deployment_id = args.deployment_id
            deployment = sm.get(models.Deployment, deployment_id)
            self._prepare_raw_nodes(deployment, raw_nodes)
            db.session.execute(
                models.Node.__table__.insert(),
                raw_nodes,
            )
        return "[]", 201

    def _prepare_raw_nodes(self, deployment, raw_nodes):
        if any(item.get('creator') for item in raw_nodes):
            check_user_action_allowed('set_owner')

        valid_params = {'id', 'deploy_number_of_instances',
                        'host_id', 'max_number_of_instances',
                        'min_number_of_instances', 'number_of_instances',
                        'planned_number_of_instances', 'plugins',
                        'plugins_to_install', 'properties', 'relationships',
                        'operations', 'type', 'type_hierarchy', 'visibility',
                        '_tenant_id', '_deployment_fk', '_creator_id'}

        user_lookup_cache: Dict[str, models.User] = {}

        for raw_node in raw_nodes:
            raw_node['_tenant_id'] = deployment._tenant_id

            creator = rest_utils.lookup_and_validate_user(
                raw_node.get('creator'), user_lookup_cache)
            raw_node['_creator_id'] = creator.id
            raw_node['_deployment_fk'] = deployment._storage_id
            raw_node['visibility'] = deployment.visibility

            raw_node.setdefault('type_hierarchy', [])
            if not raw_node['type_hierarchy']:
                raw_node['type_hierarchy'] = [raw_node['type']]

            scalable = raw_node.get(
                'capabilities', {}).get(
                'scalable', {}).get(
                'properties', {})

            rest_utils.remove_invalid_keys(raw_node, valid_params)

            raw_node.setdefault('number_of_instances',
                                scalable.get('current_instances', 1))
            raw_node.setdefault('planned_number_of_instances',
                                scalable.get('current_instances', 1))
            raw_node.setdefault('deploy_number_of_instances',
                                scalable.get('default_instances', 1))
            raw_node.setdefault('min_number_of_instances',
                                scalable.get('min_instances', 1))
            raw_node.setdefault('max_number_of_instances',
                                scalable.get('max_instances', 1))
            raw_node.setdefault('host_id', None)
            raw_node.setdefault('properties', {})
            raw_node.setdefault('operations', {})
            raw_node.setdefault('plugins', {})
            raw_node.setdefault('plugins_to_install', None)
            raw_node['relationships'] = self._prepare_node_relationships(
                raw_node.get('relationships', []),
            )

    def _prepare_node_relationships(self, raw_relationships):
        prepared_relationships = []
        for raw_relationship in raw_relationships:
            relationship = {
                'target_id': raw_relationship['target_id'],
                'type': raw_relationship['type'],
                'type_hierarchy': raw_relationship['type_hierarchy'],
                'properties': raw_relationship['properties'],
                'source_operations': raw_relationship['source_operations'],
                'target_operations': raw_relationship['target_operations'],
            }
            prepared_relationships.append(relationship)
        return prepared_relationships


class _UpdateNodeArgs(pydantic.BaseModel):
    plugins: Optional[Dict[str, Any]] = None
    operations: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    capabilities: Optional[Dict[str, Any]] = None
    relationships: Optional[Any] = None


class NodesId(SecuredResource):
    @authorize('node_update')
    @only_deployment_update
    def patch(self, deployment_id, node_id):
        request_dict = _UpdateNodeArgs.parse_obj(request.json).dict()
        sm = get_storage_manager()
        with sm.transaction():
            deployment = sm.get(models.Deployment, deployment_id)
            node = sm.get(models.Node, None,
                          filters={'id': node_id, 'deployment': deployment})
            if request_dict.get('plugins'):
                node.plugins = request_dict['plugins']
            if request_dict.get('operations'):
                node.operations = request_dict['operations']
            if request_dict.get('relationships'):
                node.relationships = request_dict['relationships']
            if request_dict.get('properties'):
                node.properties = request_dict['properties']
            if request_dict.get('capabilities'):
                scalable = request_dict['capabilities'].get('scalable', {})\
                    .get('properties', {})
                if 'max_instances' in scalable:
                    node.max_number_of_instances = scalable['max_instances']
                if 'min_instances' in scalable:
                    node.min_number_of_instances = scalable['min_instances']
                if 'current_instances' in scalable:
                    node.number_of_instances = scalable['current_instances']
                if 'default_instances' in scalable:
                    node.deploy_number_of_instances = \
                        scalable['default_instances']
                if 'planned_instances' in scalable:
                    node.planned_number_of_instances = \
                        scalable['planned_instances']
            sm.update(node)
        return "", 204

    @authorize('node_delete')
    @only_deployment_update
    def delete(self, deployment_id, node_id):
        sm = get_storage_manager()
        with sm.transaction():
            deployment = sm.get(models.Deployment, deployment_id)
            node = sm.get(models.Node, None,
                          filters={'id': node_id, 'deployment': deployment})
            sm.delete(node)
        return "", 204


class _CreateNodeInstancesArgs(pydantic.BaseModel):
    deployment_id: str
    node_instances: List[Dict[str, Any]]


class NodeInstances(v2_NodeInstances):
    @authorize('node_list')
    def post(self):
        args = _CreateNodeInstancesArgs.parse_obj(request.json)
        sm = get_storage_manager()
        raw_instances = args.node_instances
        if not raw_instances:
            return "", 204
        with sm.transaction():
            deployment_id = args.deployment_id
            deployment = sm.get(models.Deployment, deployment_id)
            self._prepare_raw_instances(sm, deployment, raw_instances)
            db.session.execute(
                models.NodeInstance.__table__.insert(),
                raw_instances,
            )
        return "[]", 201

    def _prepare_raw_instances(self, sm, deployment, raw_instances):
        if any(item.get('creator') for item in raw_instances):
            check_user_action_allowed('set_owner')

        existing_instances = sm.list(
            models.NodeInstance,
            filters={'deployment_id': deployment.id},
            include=['index', 'node_id'],
            get_all_results=True)
        current_node_index: Dict[str, int] = defaultdict(int)
        for ni in existing_instances:
            if ni.index > current_node_index[ni.node_id]:
                current_node_index[ni.node_id] = ni.index

        nodes = {node.id: node for node in deployment.nodes}

        valid_params = {'id', 'runtime_properties', 'state', 'version',
                        'relationships', 'scaling_groups', 'host_id',
                        'index', 'visibility', 'is_status_check_ok',
                        'system_properties', 'has_configuration_drift',
                        '_tenant_id', '_node_fk', '_creator_id'}

        user_lookup_cache: Dict[str, models.User] = {}

        for raw_instance in raw_instances:
            node_id = raw_instance.pop('node_id')
            index = raw_instance.get('index', current_node_index[node_id] + 1)
            raw_instance['index'] = current_node_index[node_id] = index

            raw_instance['_tenant_id'] = deployment._tenant_id
            node = nodes[node_id]
            raw_instance['_node_fk'] = node._storage_id
            raw_instance['visibility'] = node.visibility
            creator = rest_utils.lookup_and_validate_user(
                raw_instance.get('creator'), user_lookup_cache)
            raw_instance['_creator_id'] = creator.id

            rest_utils.remove_invalid_keys(raw_instance, valid_params)

            raw_instance.setdefault('runtime_properties', {})
            raw_instance.setdefault('state', 'uninitialized')
            raw_instance.setdefault('version', 1)
            raw_instance.setdefault('relationships', [])
            raw_instance.setdefault('scaling_groups', [])
            raw_instance.setdefault('host_id', None)


class NodeInstancesId(v3_NodeInstancesId):
    @authorize('node_instance_delete')
    @only_deployment_update
    def delete(self, node_instance_id):
        sm = get_storage_manager()
        with sm.transaction():
            instance = sm.get(models.NodeInstance, node_instance_id)
            sm.delete(instance)
        return "", 204
