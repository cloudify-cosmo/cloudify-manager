from ..resources_v3 import Nodes as v3_Nodes

from manager_rest import manager_exceptions
from manager_rest.rest import rest_utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import get_storage_manager, models


class Nodes(v3_Nodes):
    @authorize('node_create')
    def post(self):
        request_dict = rest_utils.get_json_and_verify_params({
            'nodes': {'type': list},
        })
        sm = get_storage_manager()
        raw_nodes = request_dict['nodes']
        created = []
        with sm.transaction():
            deployment_id = self._deployment_id_from_nodes(raw_nodes)
            deployment = sm.get(models.Deployment, deployment_id)
            for raw_node in raw_nodes:
                node = self._node_from_raw_node(raw_node)
                node.set_deployment(deployment)
                sm.put(node)
                created.append(node)
        return None, 201

    def _deployment_id_from_nodes(self, raw_nodes):
        deployment_id = raw_nodes[0]['deployment_id']
        if any(n['deployment_id'] != deployment_id for n in raw_nodes):
            raise manager_exceptions.ConflictError(
                'All nodes must belong to the same deployment'
            )
        return deployment_id

    def _node_from_raw_node(self, raw_node):
        node_type = raw_node['type']
        type_hierarchy = raw_node.get('type_hierarchy') or []
        if not type_hierarchy:
            type_hierarchy = [node_type]
        try:
            scalable = raw_node['capabilities']['scalable']['properties']
        except KeyError:
            scalable = {}
        return models.Node(
            id=raw_node['id'],
            type=node_type,
            type_hierarchy=type_hierarchy,
            number_of_instances=scalable.get('current_instances') or 1,
            planned_number_of_instances=scalable.get('current_instances') or 1,
            deploy_number_of_instances=scalable.get('default_instances') or 1,
            min_number_of_instances=scalable.get('min_instances') or 1,
            max_number_of_instances=scalable.get('max_instances') or 1,
            host_id=raw_node.get('host_id'),
            properties=raw_node.get('properties') or {},
            operations=raw_node.get('operations') or {},
            plugins=raw_node.get('plugins') or {},
            plugins_to_install=raw_node.get('plugins_to_install'),
            relationships=self._prepare_node_relationships(raw_node)
        )

    def _prepare_node_relationships(self, raw_node):
        if 'relationships' not in raw_node:
            return []
        prepared_relationships = []
        for raw_relationship in raw_node['relationships']:
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
