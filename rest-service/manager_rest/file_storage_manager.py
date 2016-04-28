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

import os
import json

from manager_rest.storage_manager import ListResult
from manager_rest.models import (BlueprintState,
                                 Deployment,
                                 DeploymentModification,
                                 Execution,
                                 Plugin,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext,
                                 Snapshot,
                                 DeploymentUpdate)
from manager_rest import manager_exceptions

STORAGE_FILE_PATH = '/tmp/manager-rest-tests-storage.json'

NODES = 'nodes'
NODE_INSTANCES = 'node_instances'
BLUEPRINTS = 'blueprints'
DEPLOYMENTS = 'deployments'
DEPLOYMENT_UPDATES = 'deployment_updates'
DEPLOYMENT_MODIFICATIONS = 'deployment_modifications'
EXECUTIONS = 'executions'
PLUGINS = 'plugins'
SNAPSHOTS = 'snapshots'
PROVIDER_CONTEXT = 'provider_context'
PROVIDER_CONTEXT_ID = '1'


def sort_list(list_of_objects, sort=None):
    if not sort:
        return list_of_objects

    # multiple sorting has to begin from the last sort key
    for key in reversed(sort):
        order = sort[key]
        is_reversed = True if order == "desc" else False
        list_of_objects = sorted(list_of_objects,
                                 key=lambda obj: getattr(obj, key),
                                 reverse=is_reversed)
    return list_of_objects


def paginate_list(list_of_objects, pagination=None):
    total = len(list_of_objects)
    if pagination:
        offset = pagination.get('offset')
        size = pagination.get('size')
        if offset is not None:
            list_of_objects = list_of_objects[offset:]
        if size is not None:
            list_of_objects = list_of_objects[:size]
    else:
        offset = None
        size = None

    pagination = {'total': total,
                  'size': size,
                  'offset': offset}
    meta = {'pagination': pagination}
    return ListResult(list_of_objects, meta)


class FileStorageManager(object):
    """
    file based storage manager for tests.
    """

    entities = {
        NODES: DeploymentNode,
        NODE_INSTANCES: DeploymentNodeInstance,
        BLUEPRINTS: BlueprintState,
        DEPLOYMENTS: Deployment,
        DEPLOYMENT_MODIFICATIONS: DeploymentModification,
        EXECUTIONS: Execution,
        PLUGINS: Plugin,
        PROVIDER_CONTEXT: ProviderContext,
        SNAPSHOTS: Snapshot,
        DEPLOYMENT_UPDATES: DeploymentUpdate
    }

    def __init__(self, storage_path):
        self._storage_path = storage_path
        if os.path.isfile(storage_path):
            os.remove(storage_path)

    def _init_file(self):
        data = {}
        for entity_name in FileStorageManager.entities.keys():
            data[entity_name] = {}
        self._dump_data(data)

    def _load_data(self):
        if not os.path.isfile(self._storage_path):
            self._init_file()
        with open(self._storage_path, 'r') as f:
            data = json.load(f)
            deserialized_data = dict()
            for entity_name, model in FileStorageManager.entities.iteritems():
                deserialized_data[entity_name] = \
                    {key: model(**val) for key, val in
                     data[entity_name].iteritems()}
            return deserialized_data

    def _dump_data(self, data):
        with open(self._storage_path, 'w') as f:
            serialized_data = dict()
            for entity_name in FileStorageManager.entities.keys():
                serialized_data[entity_name] = \
                    {key: val.to_dict() for key, val in
                     data[entity_name].iteritems()}
            json.dump(serialized_data, f)

    def get_node_instance(self, node_id, **_):
        data = self._load_data()
        if node_id in data[NODE_INSTANCES]:
            return data[NODE_INSTANCES][node_id]
        raise manager_exceptions.NotFoundError(
            "Node {0} not found".format(node_id))

    def get_node_instances(self, filters=None, pagination=None,
                           sort=None, **_):
        instances = self._load_data()[NODE_INSTANCES].values()
        instances = sort_list(instances, sort)
        result = self.filter_data(instances, filters)
        return paginate_list(result,
                             pagination=pagination)

    def get_nodes(self, filters=None, pagination=None,
                  sort=None, **_):
        nodes = self._load_data()[NODES].values()
        nodes = sort_list(nodes, sort)
        result = self.filter_data(nodes, filters)
        return paginate_list(result,
                             pagination=pagination)

    def get_plugins(self, include=None, filters=None, pagination=None,
                    sort=None):
        plugins = self._load_data()[PLUGINS].values()
        plugins = sort_list(plugins, sort)
        result = self.filter_data(plugins, filters)
        return paginate_list(result,
                             pagination=pagination)

    def snapshots_list(self, include=None, filters=None, pagination=None,
                       sort=None):
        snapshots = self._load_data()[SNAPSHOTS].values()
        snapshots = sort_list(snapshots, sort)
        result = self.filter_data(snapshots, filters)
        return paginate_list(result,
                             pagination=pagination)

    def get_node(self, deployment_id, node_id, **_):
        data = self._load_data()
        node_id = '{}_{}'.format(deployment_id, node_id)
        if node_id in data[NODES]:
            return data[NODES][node_id]
        raise manager_exceptions.NotFoundError(
            "Deployment {0} not found".format(deployment_id))

    def put_node(self, node):
        data = self._load_data()
        node_id = '{0}_{1}'.format(node.deployment_id, node.id)
        if str(node_id) in data[NODES]:
            raise manager_exceptions.ConflictError(
                'Node {0} already exists'.format(node_id))
        data[NODES][str(node_id)] = node
        self._dump_data(data)
        return 1

    def put_node_instance(self, node):
        data = self._load_data()
        node_id = node.id
        if str(node_id) in data[NODE_INSTANCES]:
            raise manager_exceptions.ConflictError(
                'Node {0} already exists'.format(node_id))
        data[NODE_INSTANCES][str(node_id)] = node
        self._dump_data(data)
        return 1

    def update_execution_status(self, execution_id, status, error):
        data = self._load_data()
        if execution_id not in data[EXECUTIONS]:
            raise manager_exceptions.NotFoundError(
                "Execution {0} not found".format(execution_id))

        execution = data[EXECUTIONS][execution_id]
        execution.status = status
        execution.error = error
        data[EXECUTIONS][execution_id] = execution
        self._dump_data(data)

    def update_node(self, deployment_id, node_id,
                    number_of_instances=None,
                    planned_number_of_instances=None):
        data = self._load_data()
        storage_node_id = '{0}_{1}'.format(deployment_id, node_id)
        if storage_node_id not in data[NODES]:
            raise manager_exceptions.NotFoundError(
                'Node {0} not found'.format(node_id))
        node = data[NODES][storage_node_id]
        if number_of_instances is not None:
            node.number_of_instances = number_of_instances
        if planned_number_of_instances is not None:
            node.planned_number_of_instances = planned_number_of_instances
        self._dump_data(data)

    def update_node_instance(self, node_update):
        data = self._load_data()
        if node_update.id not in data[NODE_INSTANCES]:
            raise manager_exceptions.NotFoundError(
                "Node {0} not found".format(node_update.id))
        node = data[NODE_INSTANCES][node_update.id]

        if node_update.state is not None:
            node.state = node_update.state
        if node_update.runtime_properties is not None:
            node.runtime_properties = node_update.runtime_properties
        if node_update.relationships is not None:
            node.relationships = node_update.relationships

        data[NODE_INSTANCES][node.id] = node
        self._dump_data(data)

    def blueprints_list(self, filters=None, pagination=None,
                        sort=None, **_):
        blueprints = self._load_data()[BLUEPRINTS].values()
        blueprints = sort_list(blueprints, sort)
        result = self.filter_data(blueprints, filters)
        return paginate_list(result,
                             pagination=pagination)

    @staticmethod
    def filter_data(items_lst, filters=None):
        result = []
        if filters:
            for item in items_lst:
                for key, val_lst in filters.iteritems():
                    # filter keys have already been verified
                    if getattr(item, key) not in val_lst:
                        break
                else:
                    result.append(item)
        else:
            result = items_lst
        return result

    def deployments_list(self, filters=None, pagination=None,
                         sort=None, **_):
        deployments = self._load_data()[DEPLOYMENTS].values()
        deployments = sort_list(deployments, sort)
        result = self.filter_data(deployments, filters)
        return paginate_list(result,
                             pagination=pagination)

    def deployment_updates_list(self, filters=None, pagination=None,
                                sort=None, **_):
        deployment_updates = self._load_data()[DEPLOYMENT_UPDATES].values()
        deployment_updates = sort_list(deployment_updates, sort)
        result = self.filter_data(deployment_updates, filters)
        return paginate_list(result,
                             pagination=pagination)

    def executions_list(self, filters=None, pagination=None,
                        sort=None, **_):
        executions = self._load_data()[EXECUTIONS].values()
        executions = sort_list(executions, sort)
        result = self.filter_data(executions, filters)
        return paginate_list(result,
                             pagination=pagination)

    def get_blueprint_deployments(self, blueprint_id, **_):
        return self.deployments_list(filters={'blueprint_id': blueprint_id})

    def get_blueprint(self, blueprint_id, include=None):
        data = self._load_data()
        if blueprint_id in data[BLUEPRINTS]:
            bp = data[BLUEPRINTS][blueprint_id]
            if include:
                for field in BlueprintState.fields:
                    if field not in include:
                        setattr(bp, field, None)
            return bp
        raise manager_exceptions.NotFoundError(
            "Blueprint {0} not found".format(blueprint_id))

    def get_plugin(self, plugin_id, include=None):
        data = self._load_data()
        if plugin_id in data[PLUGINS]:
            plugin = data[PLUGINS][plugin_id]
            if include:
                for field in Plugin.fields:
                    if field not in include:
                        setattr(plugin, field, None)
            return plugin
        raise manager_exceptions.NotFoundError(
            "Plugin {0} not found".format(plugin_id))

    def get_deployment(self, deployment_id, include=None):
        data = self._load_data()
        if deployment_id in data[DEPLOYMENTS]:
            dep = data[DEPLOYMENTS][deployment_id]
            if include:
                for field in Deployment.fields:
                    if field not in include:
                        setattr(dep, field, None)
            return dep
        raise manager_exceptions.NotFoundError(
            "Deployment {0} not found".format(deployment_id))

    def get_deployment_update(self, deployment_update_id, include=None):
        data = self._load_data()
        if deployment_update_id in data[DEPLOYMENT_UPDATES]:
            dep = data[DEPLOYMENT_UPDATES][deployment_update_id]
            if include:
                for field in DeploymentUpdate.fields:
                    if field not in include:
                        setattr(dep, field, None)
            return dep
        raise manager_exceptions.NotFoundError(
            "Deployment Update {0} not found".format(deployment_update_id))

    def get_execution(self, execution_id, **_):
        data = self._load_data()
        if execution_id in data[EXECUTIONS]:
            return data[EXECUTIONS][execution_id]
        raise manager_exceptions.NotFoundError(
            "Execution {0} not found".format(execution_id))

    def put_blueprint(self, blueprint_id, blueprint):
        data = self._load_data()
        if str(blueprint_id) in data[BLUEPRINTS]:
            raise manager_exceptions.ConflictError(
                'Blueprint {0} already exists'.format(blueprint_id))
        data[BLUEPRINTS][str(blueprint_id)] = blueprint
        self._dump_data(data)

    def put_deployment(self, deployment_id, deployment):
        data = self._load_data()
        if str(deployment_id) in data[DEPLOYMENTS]:
            raise manager_exceptions.ConflictError(
                'Deployment {0} already exists'.format(deployment_id))
        data[DEPLOYMENTS][str(deployment_id)] = deployment
        self._dump_data(data)

    def put_deployment_update(self, deployment_update):
        data = self._load_data()
        if str(deployment_update.id) in data[DEPLOYMENT_UPDATES]:
            raise manager_exceptions.ConflictError(
                'Deployment Update {0} already exists'
                .format(deployment_update.id))
        data[DEPLOYMENT_UPDATES][str(deployment_update.id)] = deployment_update
        self._dump_data(data)

    def put_deployment_update_step(self, deployment_update_id, step):
        data = self._load_data()
        if str(deployment_update_id) not in data[DEPLOYMENT_UPDATES]:
            raise manager_exceptions.NotFoundError(
                "Deployment Update {0} doesn't exist"
                .format(deployment_update_id))
        data[DEPLOYMENT_UPDATES][str(deployment_update_id)].steps.append(
            step
        )

        self._dump_data(data)

    def put_execution(self, execution_id, execution):
        data = self._load_data()
        if str(execution_id) in data[EXECUTIONS]:
            raise manager_exceptions.ConflictError(
                'Execution {0} already exists'.format(execution_id))
        data[EXECUTIONS][str(execution_id)] = execution
        self._dump_data(data)

    def put_plugin(self, plugin):
        data = self._load_data()
        if str(plugin.id) in data[PLUGINS]:
            raise manager_exceptions.ConflictError(
                'Plugin {0} already exists'.format(plugin.id))
        data[PLUGINS][str(plugin.id)] = plugin
        self._dump_data(data)

    def put_snapshot(self, snapshot_id, snapshot):
        data = self._load_data()
        if str(snapshot_id) in data[SNAPSHOTS]:
            raise manager_exceptions.ConflictError(
                'Snapshot {0} already exists'.format(snapshot_id))
        data[SNAPSHOTS][str(snapshot_id)] = snapshot
        self._dump_data(data)

    def delete_blueprint(self, blueprint_id):
        return self._delete_object(blueprint_id, BLUEPRINTS, 'Blueprint')

    def delete_plugin(self, plugin_id):
        return self._delete_object(plugin_id, PLUGINS, 'Plugin')

    def delete_deployment(self, deployment_id):
        data = self._load_data()
        for instance in data[NODE_INSTANCES].values():
            if instance.deployment_id == deployment_id:
                del data[NODE_INSTANCES][instance.id]
        for node in data[NODES].values():
            if node.deployment_id == deployment_id:
                node_id = '{0}_{1}'.format(deployment_id, node.id)
                del data[NODES][node_id]
        for execution in data[EXECUTIONS].values():
            if execution.deployment_id == deployment_id:
                del data[EXECUTIONS][execution.id]
        for modification in data[DEPLOYMENT_MODIFICATIONS].values():
            if modification.deployment_id == deployment_id:
                del data[DEPLOYMENT_MODIFICATIONS][modification.id]
        self._dump_data(data)
        return self._delete_object(deployment_id, DEPLOYMENTS, 'Deployment')

    def delete_execution(self, execution_id):
        return self._delete_object(execution_id, EXECUTIONS, 'Execution')

    def delete_node(self, node_id):
        return self._delete_object(node_id, NODES, 'Node')

    def delete_node_instance(self, node_instance_id):
        return self._delete_object(node_instance_id, NODE_INSTANCES, 'Node')

    def _delete_object(self, object_id, object_type, object_type_name):
        data = self._load_data()
        if object_id in data[object_type]:
            obj = data[object_type][object_id]
            del(data[object_type][object_id])
            self._dump_data(data)
            return obj
        raise manager_exceptions.NotFoundError(
            "{0} {1} not found".format(object_type_name, object_id))

    def put_provider_context(self, provider_context):
        data = self._load_data()
        if PROVIDER_CONTEXT_ID in data[PROVIDER_CONTEXT]:
            raise manager_exceptions.ConflictError(
                'Provider context already set')
        data[PROVIDER_CONTEXT][PROVIDER_CONTEXT_ID] = provider_context
        self._dump_data(data)

    def update_provider_context(self, provider_context):
        data = self._load_data()
        if PROVIDER_CONTEXT_ID not in data[PROVIDER_CONTEXT]:
            raise manager_exceptions.NotFoundError('Provider Context not '
                                                   'found')
        data[PROVIDER_CONTEXT][PROVIDER_CONTEXT_ID] = provider_context
        self._dump_data(data)

    def get_provider_context(self, **_):
        data = self._load_data()
        if PROVIDER_CONTEXT_ID in data[PROVIDER_CONTEXT]:
            return data[PROVIDER_CONTEXT][PROVIDER_CONTEXT_ID]
        raise manager_exceptions.NotFoundError(
            "Provider context not set")

    def put_deployment_modification(self, modification_id, modification):
        data = self._load_data()
        if str(modification_id) in data[DEPLOYMENT_MODIFICATIONS]:
            raise manager_exceptions.ConflictError(
                'Deployment modification {0} already exists'
                .format(modification_id))
        data[DEPLOYMENT_MODIFICATIONS][str(modification_id)] = modification
        self._dump_data(data)

    def get_deployment_modification(self, modification_id, include=None):
        data = self._load_data()
        if modification_id in data[DEPLOYMENT_MODIFICATIONS]:
            return data[DEPLOYMENT_MODIFICATIONS][modification_id]
        raise manager_exceptions.NotFoundError(
            "Deployment modification {0} not found".format(modification_id))

    def deployment_modifications_list(self, include=None, filters=None,
                                      pagination=None, sort=None):
        modifications = self._load_data()[DEPLOYMENT_MODIFICATIONS].values()
        modifications = sort_list(modifications, sort)
        result = self.filter_data(modifications, filters)
        return paginate_list(result,
                             pagination=pagination)

    def update_deployment_modification(self, modification):
            modification_id = modification.id
            data = self._load_data()
            if modification_id not in data[DEPLOYMENT_MODIFICATIONS]:
                raise manager_exceptions.NotFoundError(
                    'Deployment modification {0} not found'
                    .format(modification_id))
            updated_modification = \
                data[DEPLOYMENT_MODIFICATIONS][modification_id]
            if modification.status is not None:
                updated_modification.status = modification.status
            if modification.ended_at is not None:
                updated_modification.ended_at = modification.ended_at
            if modification.node_instances is not None:
                updated_modification.node_instances = \
                    modification.node_instances
            self._dump_data(data)

    def update_deployment(self, deployment):
        deployment_id = deployment.id
        data = self._load_data()
        if deployment_id not in data[DEPLOYMENTS]:
            raise manager_exceptions.NotFoundError(
                'Deployment {0} not found'
                .format(deployment_id))
        updated_deployment = data[DEPLOYMENTS][deployment_id]
        if deployment.scaling_groups is not None:
            updated_deployment.scaling_groups = deployment.scaling_groups
        self._dump_data(data)


def create():
    return FileStorageManager(STORAGE_FILE_PATH)
