from collections import defaultdict

from flask_security import current_user

from ..resources_v3 import Nodes as v3_Nodes
from ..resources_v2 import NodeInstances as v2_NodeInstances

from manager_rest.rest import rest_utils
from manager_rest.rest.rest_decorators import only_deployment_update
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_base import db
from manager_rest.security import SecuredResource


class Nodes(v3_Nodes):
    @authorize('node_list')
    def post(self):
        request_dict = rest_utils.get_json_and_verify_params({
            'deployment_id': {'type': str},
            'nodes': {'type': list},
        })
        sm = get_storage_manager()
        raw_nodes = request_dict['nodes']

        if not raw_nodes:
            return None, 204
        with sm.transaction():
            deployment_id = request_dict['deployment_id']
            deployment = sm.get(models.Deployment, deployment_id)
            for raw_node in raw_nodes:
                node = self._node_from_raw_node(raw_node)
                node.set_deployment(deployment)
                sm.put(node)
        return None, 201

    def _node_from_raw_node(self, raw_node):
        node_type = raw_node['type']
        type_hierarchy = raw_node.get('type_hierarchy') or []
        if not type_hierarchy:
            type_hierarchy = [node_type]
        try:
            scalable = raw_node['capabilities']['scalable']['properties']
        except KeyError:
            scalable = {}

        def _get_instance_num(attribute):
            value = scalable.get(attribute)
            return 1 if value is None else value

        return models.Node(
            id=raw_node['id'],
            type=node_type,
            type_hierarchy=type_hierarchy,
            number_of_instances=_get_instance_num('current_instances'),
            planned_number_of_instances=_get_instance_num('current_instances'),
            deploy_number_of_instances=_get_instance_num('default_instances'),
            min_number_of_instances=_get_instance_num('min_instances'),
            max_number_of_instances=_get_instance_num('max_instances'),
            host_id=raw_node.get('host_id'),
            properties=raw_node.get('properties') or {},
            operations=raw_node.get('operations') or {},
            plugins=raw_node.get('plugins') or [],
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


class NodesId(SecuredResource):
    @authorize('node_update')
    @only_deployment_update
    def patch(self, deployment_id, node_id):
        request_dict = rest_utils.get_json_and_verify_params({
            'plugins': {'optional': True},
            'operations': {'optional': True},
            'relationships': {'optional': True},
            'properties': {'optional': True},
        })
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
            sm.update(node)
        return None, 204

    @authorize('node_delete')
    @only_deployment_update
    def delete(self, deployment_id, node_id):
        sm = get_storage_manager()
        with sm.transaction():
            deployment = sm.get(models.Deployment, deployment_id)
            node = sm.get(models.Node, None,
                          filters={'id': node_id, 'deployment': deployment})
            sm.delete(node)
        return None, 204


class NodeInstances(v2_NodeInstances):
    @authorize('node_list')
    def post(self):
        request_dict = rest_utils.get_json_and_verify_params({
            'deployment_id': {'type': str},
            'node_instances': {'type': list},
        })
        sm = get_storage_manager()
        raw_instances = request_dict['node_instances']
        if not raw_instances:
            return None, 204
        with sm.transaction():
            deployment_id = request_dict['deployment_id']
            deployment = sm.get(models.Deployment, deployment_id)
            self._prepare_raw_instances(sm, deployment, raw_instances)
            db.session.execute(
                models.NodeInstance.__table__.insert(),
                raw_instances,
            )
            db.session.commit()
        return None, 201

    def _prepare_raw_instances(self, sm, deployment, raw_instances):
        if any(item.get('creator') for item in raw_instances):
            check_user_action_allowed('set_owner')

        existing_instances = sm.list(
            models.NodeInstance,
            filters={'deployment_id': deployment.id},
            include=['index', 'node_id'],
            get_all_results=True)
        current_node_index = defaultdict(int)
        for ni in existing_instances:
            if ni.index > current_node_index[ni.node_id]:
                current_node_index[ni.node_id] = ni.index

        nodes = {node.id: node._storage_id for node in deployment.nodes}

        valid_params = {'id', 'runtime_properties', 'state', 'version',
                        'relationships', 'scaling_groups', 'host_id',
                        'index', 'visibility',
                        '_tenant_id', '_node_fk', '_creator_id'}

        user_lookup = {}

        for raw_instance in raw_instances:
            node_id = raw_instance['node_id']
            index = raw_instance.get('index', current_node_index[node_id] + 1)
            raw_instance['index'] = current_node_index[node_id] = index

            raw_instance['_tenant_id'] = deployment._tenant_id
            raw_instance['_node_fk'] = nodes[raw_instance.pop('node_id')]
            creator = raw_instance.get('creator')
            if creator:
                if creator not in user_lookup:
                    user_lookup[creator] = rest_utils.valid_user(creator)
                user = user_lookup[creator]
            else:
                user = current_user
            raw_instance['_creator_id'] = user.id

            clear = raw_instance.keys() - valid_params
            for param in clear:
                raw_instance.pop(param)

            raw_instance.setdefault('runtime_properties', {})
            raw_instance.setdefault('state', 'uninitialized')
            raw_instance.setdefault('version', 1)
            raw_instance.setdefault('relationships', [])
            raw_instance.setdefault('scaling_groups', [])
            raw_instance.setdefault('host_id', None)
