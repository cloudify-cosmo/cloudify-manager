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


import elasticsearch.exceptions
from elasticsearch import Elasticsearch

from manager_rest import config
from manager_rest import manager_exceptions
from manager_rest.storage.storage_manager import ListResult
from manager_rest.models import (BlueprintState,
                                 Snapshot,
                                 Deployment,
                                 DeploymentModification,
                                 Execution,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext,
                                 Plugin,
                                 DeploymentUpdate,
                                 Event)
from manager_rest.storage.manager_elasticsearch import ManagerElasticsearch

STORAGE_INDEX_NAME = 'cloudify_storage'
NODE_TYPE = 'node'
NODE_INSTANCE_TYPE = 'node_instance'
PLUGIN_TYPE = 'plugin'
BLUEPRINT_TYPE = 'blueprint'
SNAPSHOT_TYPE = 'snapshot'
DEPLOYMENT_TYPE = 'deployment'
DEPLOYMENT_UPDATE_TYPE = 'deployment_update'
DEPLOYMENT_MODIFICATION_TYPE = 'deployment_modification'
EXECUTION_TYPE = 'execution'
PROVIDER_CONTEXT_TYPE = 'provider_context'
PROVIDER_CONTEXT_ID = 'CONTEXT'


MUTATE_PARAMS = {
    'refresh': True
}


class ESStorageManager(object):

    def __init__(self, host, port):
        self.es_host = host
        self.es_port = port
        self._es_connection = None

    @property
    def _connection(self):
        if self._es_connection is None:
            self._es_connection = Elasticsearch(
                hosts=[{'host': self.es_host, 'port': self.es_port}])
        return self._es_connection

    def _list_docs(self, doc_type, model_class, body=None, fields=None):
        include = list(fields) if fields else True
        result = self._connection.search(index=STORAGE_INDEX_NAME,
                                         doc_type=doc_type,
                                         body=body,
                                         _source=include)
        docs = ManagerElasticsearch.extract_search_result_values(result)

        # ES doesn't return _version if using its search API.
        if doc_type == NODE_INSTANCE_TYPE:
            for doc in docs:
                doc['version'] = None
        items = [self._fill_missing_fields_and_deserialize(doc, model_class)
                 for doc in docs]
        metadata = ManagerElasticsearch.build_list_result_metadata(body,
                                                                   result)
        return ListResult(items, metadata)

    def _get_doc(self, doc_type, doc_id, fields=None):
        try:
            if fields:
                return self._connection.get(index=STORAGE_INDEX_NAME,
                                            doc_type=doc_type,
                                            id=doc_id,
                                            _source=[f for f in fields])
            else:
                return self._connection.get(index=STORAGE_INDEX_NAME,
                                            doc_type=doc_type,
                                            id=doc_id)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                '{0} {1} not found'.format(doc_type, doc_id))

    def _append_doc_list_field(self, doc_type, doc_id, field, value):
        """
        Appends a value to a list field in a document (or creates the list)
        NOTE: append.groovy file has to be located in es scripts path
        :param doc_type: document type
        :param doc_id: document id
        :param field: name of field which stores the list
        :param value: value to append to list
        """
        self._connection.update(
            index=STORAGE_INDEX_NAME,
            doc_type=doc_type,
            id=doc_id,
            script='append',
            body={
                'params': {
                    'key': field,
                    'value': value
                }})

    def _update_doc(self, doc_type, doc_id, update_doc):
        return self._connection.update(index=STORAGE_INDEX_NAME,
                                       doc_type=doc_type,
                                       id=str(doc_id),
                                       body={'doc': update_doc.to_dict()})

    def _get_doc_and_deserialize(self, doc_type, doc_id, model_class,
                                 fields=None):
        doc = self._get_doc(doc_type, doc_id, fields)
        if not fields:
            return model_class(**doc['_source'])
        else:
            if len(fields) != len(doc['_source']):
                missing_fields = [field for field in fields if field not
                                  in doc['_source']]
                raise RuntimeError('Some or all fields specified for query '
                                   'were missing: {0}'.format(missing_fields))
            fields_data = doc['_source']
            return self._fill_missing_fields_and_deserialize(fields_data,
                                                             model_class)

    def _put_doc_if_not_exists(self, doc_type, doc_id, value):
        try:
            self._connection.create(index=STORAGE_INDEX_NAME,
                                    doc_type=doc_type, id=doc_id,
                                    body=value,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.ConflictError:
            raise manager_exceptions.ConflictError(
                '{0} {1} already exists'.format(doc_type, doc_id))

    def _delete_doc(self,
                    doc_type,
                    doc_id,
                    model_class,
                    id_field='id',
                    index=STORAGE_INDEX_NAME):
        try:
            res = self._connection.delete(index, doc_type,
                                          doc_id,
                                          **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "{0} {1} not found".format(doc_type, doc_id))

        fields_data = {
            id_field: res['_id']
        }
        return self._fill_missing_fields_and_deserialize(fields_data,
                                                         model_class)

    def _delete_doc_by_query(self, doc_type, query):
        self._connection.delete_by_query(index=STORAGE_INDEX_NAME,
                                         doc_type=doc_type,
                                         body=query)

    @staticmethod
    def _fill_missing_fields_and_deserialize(fields_data, model_class):
        for field in model_class.fields:
            if field not in fields_data:
                fields_data[field] = None
        return model_class(**fields_data)

    def list_blueprints(self, include=None, filters=None, pagination=None,
                        sort=None):
        return self._get_items_list(BLUEPRINT_TYPE,
                                    BlueprintState,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include,
                                    sort=sort)

    def list_snapshots(self, include=None, filters=None, pagination=None,
                       sort=None):
        return self._get_items_list(SNAPSHOT_TYPE,
                                    Snapshot,
                                    include=include,
                                    filters=filters,
                                    pagination=pagination,
                                    sort=sort)

    def list_deployments(self, include=None, filters=None, pagination=None,
                         sort=None):
        return self._get_items_list(DEPLOYMENT_TYPE,
                                    Deployment,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include,
                                    sort=sort)

    def list_deployment_updates(self, include=None, filters=None,
                                pagination=None, sort=None):
        return self._get_items_list(DEPLOYMENT_UPDATE_TYPE,
                                    DeploymentUpdate,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include,
                                    sort=sort)

    def list_executions(self, include=None, filters=None, pagination=None,
                        sort=None):
        return self._get_items_list(EXECUTION_TYPE,
                                    Execution,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include,
                                    sort=sort)

    def list_blueprint_deployments(self, blueprint_id, include=None):
        deployment_filters = {'blueprint_id': blueprint_id}
        return self._get_items_list(DEPLOYMENT_TYPE,
                                    Deployment,
                                    filters=deployment_filters,
                                    include=include)

    def get_node_instance(self, node_instance_id, include=None):
        doc = self._get_doc(NODE_INSTANCE_TYPE,
                            node_instance_id,
                            fields=include)
        node = DeploymentNodeInstance(version=doc['_version'],
                                      **doc['_source'])
        return node

    def get_node(self, deployment_id, node_id, include=None):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        return self._get_doc_and_deserialize(doc_id=storage_node_id,
                                             doc_type=NODE_TYPE,
                                             model_class=DeploymentNode,
                                             fields=include)

    def list_node_instances(self, include=None, filters=None, pagination=None,
                            sort=None):
        return self._get_items_list(NODE_INSTANCE_TYPE,
                                    DeploymentNodeInstance,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination,
                                    sort=sort)

    def list_plugins(self, include=None, filters=None, pagination=None,
                     sort=None):
        return self._get_items_list(PLUGIN_TYPE,
                                    Plugin,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination,
                                    sort=sort)

    def list_nodes(self, include=None, filters=None, pagination=None,
                   sort=None):
        return self._get_items_list(NODE_TYPE,
                                    DeploymentNode,
                                    filters=filters,
                                    pagination=pagination,
                                    include=include,
                                    sort=sort)

    def _get_items_list(self, doc_type, model_class, include=None,
                        filters=None, pagination=None, sort=None):
        body = ManagerElasticsearch.build_request_body(filters=filters,
                                                       pagination=pagination,
                                                       sort=sort)
        return self._list_docs(doc_type,
                               model_class,
                               body=body,
                               fields=include)

    def get_blueprint(self, blueprint_id, include=None):
        return self._get_doc_and_deserialize(BLUEPRINT_TYPE,
                                             blueprint_id,
                                             BlueprintState,
                                             fields=include)

    def get_snapshot(self, snapshot_id, include=None):
        return self._get_doc_and_deserialize(SNAPSHOT_TYPE,
                                             snapshot_id,
                                             Snapshot,
                                             fields=include)

    def get_deployment(self, deployment_id, include=None):
        return self._get_doc_and_deserialize(DEPLOYMENT_TYPE,
                                             deployment_id,
                                             Deployment,
                                             fields=include)

    def get_execution(self, execution_id, include=None):
        return self._get_doc_and_deserialize(EXECUTION_TYPE,
                                             execution_id,
                                             Execution,
                                             fields=include)

    def get_plugin(self, plugin_id, include=None):
        return self._get_doc_and_deserialize(PLUGIN_TYPE,
                                             plugin_id,
                                             Plugin,
                                             fields=include)

    def put_blueprint(self, blueprint_id, blueprint):
        self._put_doc_if_not_exists(BLUEPRINT_TYPE, str(blueprint_id),
                                    blueprint.to_dict())

    def put_snapshot(self, snapshot_id, snapshot):
        self._put_doc_if_not_exists(SNAPSHOT_TYPE, str(snapshot_id),
                                    snapshot.to_dict())

    def put_deployment(self, deployment_id, deployment):
        self._put_doc_if_not_exists(DEPLOYMENT_TYPE, str(deployment_id),
                                    deployment.to_dict())

    def put_execution(self, execution_id, execution):
        self._put_doc_if_not_exists(EXECUTION_TYPE, str(execution_id),
                                    execution.to_dict())

    def put_plugin(self, plugin):
        self._put_doc_if_not_exists(PLUGIN_TYPE, str(plugin.id),
                                    plugin.to_dict())

    def put_node(self, node):
        storage_node_id = self._storage_node_id(node.deployment_id, node.id)
        doc_data = node.to_dict()
        self._put_doc_if_not_exists(NODE_TYPE, storage_node_id, doc_data)

    def put_node_instance(self, node_instance):
        node_instance_id = node_instance.id
        doc_data = node_instance.to_dict()
        del(doc_data['version'])
        self._put_doc_if_not_exists(NODE_INSTANCE_TYPE,
                                    str(node_instance_id),
                                    doc_data)
        return 1

    def get_deployment_update(self, deployment_update_id):
        return self._get_doc_and_deserialize(DEPLOYMENT_UPDATE_TYPE,
                                             deployment_update_id,
                                             DeploymentUpdate)

    def put_deployment_update(self, deployment_update):
        return self._put_doc_if_not_exists(DEPLOYMENT_UPDATE_TYPE,
                                           str(deployment_update.id),
                                           deployment_update.to_dict())

    def update_deployment_update(self, deployment_update):
        return self._update_doc(DEPLOYMENT_UPDATE_TYPE,
                                deployment_update.id,
                                deployment_update)

    def put_deployment_update_step(self, deployment_update_id, step):
        self._append_doc_list_field(doc_type=DEPLOYMENT_UPDATE_TYPE,
                                    doc_id=deployment_update_id,
                                    field='steps',
                                    value=step.to_dict())

    def delete_blueprint(self, blueprint_id):
        return self._delete_doc(BLUEPRINT_TYPE, blueprint_id,
                                BlueprintState)

    def delete_plugin(self, plugin_id):
        return self._delete_doc(PLUGIN_TYPE, plugin_id, Plugin)

    def delete_snapshot(self, snapshot_id):
        return self._delete_doc(SNAPSHOT_TYPE, snapshot_id,
                                Snapshot)

    # TODO: Move this to manager_elasticsearch.py, to make it independent
    # of the storage manager (in order to use sql storage manager)
    def delete_events(self, events_list):
        for event in events_list:
            self._delete_doc(event['doc_type'],
                             event['id'],
                             Event,
                             index=event['index'])

    def update_snapshot_status(self, snapshot_id, status, error):
        update_doc_data = {'status': status,
                           'error': error}
        update_doc = {'doc': update_doc_data}
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=SNAPSHOT_TYPE,
                                    id=str(snapshot_id),
                                    body=update_doc,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Snapshot {0} not found".format(snapshot_id))

    def update_execution_status(self, execution_id, status, error):
        update_doc_data = {'status': status,
                           'error': error}
        update_doc = {'doc': update_doc_data}

        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=EXECUTION_TYPE,
                                    id=str(execution_id),
                                    body=update_doc,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Execution {0} not found".format(execution_id))

    def update_provider_context(self, provider_context):
        doc_data = {'doc': provider_context.to_dict()}
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=PROVIDER_CONTEXT_TYPE,
                                    id=PROVIDER_CONTEXT_ID,
                                    body=doc_data,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                'Provider Context not found')

    def delete_deployment(self, deployment_id):
        query = ManagerElasticsearch.build_request_body(
            filters={'deployment_id': deployment_id},
            skip_size=True
        )
        self._delete_doc_by_query(EXECUTION_TYPE, query)
        self._delete_doc_by_query(NODE_INSTANCE_TYPE, query)
        self._delete_doc_by_query(NODE_TYPE, query)
        self._delete_doc_by_query(DEPLOYMENT_MODIFICATION_TYPE, query)
        self._delete_doc_by_query(DEPLOYMENT_UPDATE_TYPE, query)
        return self._delete_doc(DEPLOYMENT_TYPE, deployment_id, Deployment)

    def delete_execution(self, execution_id):
        return self._delete_doc(EXECUTION_TYPE, execution_id, Execution)

    def delete_node(self, deployment_id, node_id):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        return self._delete_doc(NODE_TYPE, storage_node_id, DeploymentNode)

    def delete_node_instance(self, node_instance_id):
        return self._delete_doc(NODE_INSTANCE_TYPE,
                                node_instance_id,
                                DeploymentNodeInstance)

    def update_node(self, deployment_id, node_id,
                    number_of_instances=None,
                    planned_number_of_instances=None,
                    relationships=None,
                    operations=None,
                    plugins=None,
                    properties=None):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        update_doc_data = {}
        if relationships:
            update_doc_data['relationships'] = relationships
        if operations:
            update_doc_data['operations'] = operations
        if plugins:
            update_doc_data['plugins'] = plugins
        if properties:
            update_doc_data['properties'] = properties
        if number_of_instances is not None:
            update_doc_data['number_of_instances'] = number_of_instances
        if planned_number_of_instances is not None:
            update_doc_data[
                'planned_number_of_instances'] = planned_number_of_instances
        update_doc = {'doc': update_doc_data}
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=NODE_TYPE,
                                    id=storage_node_id,
                                    body=update_doc,
                                    **MUTATE_PARAMS)
            return update_doc_data
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Node {0} not found".format(node_id))

    def update_node_instance(self, node):
        new_state = node.state
        new_runtime_props = node.runtime_properties
        new_relationships = node.relationships

        current = self.get_node_instance(node.id)
        if new_state is not None:
            current.state = new_state

        if new_runtime_props is not None:
            current.runtime_properties = new_runtime_props

        if new_relationships is not None:
            current.relationships = new_relationships

        updated = current.to_dict()
        del updated['version']

        try:
            self._connection.index(index=STORAGE_INDEX_NAME,
                                   doc_type=NODE_INSTANCE_TYPE,
                                   id=node.id,
                                   body=updated,
                                   version=node.version,
                                   **MUTATE_PARAMS)
        except elasticsearch.exceptions.TransportError as e:
            if e.status_code == 409:
                raise manager_exceptions.ConflictError(
                    'Node instance update conflict [current_version={0}, '
                    'updated_version={1}]'.format(
                        current.version, node.version))
            else:
                raise

    def put_provider_context(self, provider_context):
        doc_data = provider_context.to_dict()
        self._put_doc_if_not_exists(PROVIDER_CONTEXT_TYPE,
                                    PROVIDER_CONTEXT_ID,
                                    doc_data)

    def get_provider_context(self, include=None):
        return self._get_doc_and_deserialize(PROVIDER_CONTEXT_TYPE,
                                             PROVIDER_CONTEXT_ID,
                                             ProviderContext,
                                             fields=include)

    def put_deployment_modification(self, modification_id, modification):
        self._put_doc_if_not_exists(DEPLOYMENT_MODIFICATION_TYPE,
                                    modification_id,
                                    modification.to_dict())

    def get_deployment_modification(self, modification_id, include=None):
        return self._get_doc_and_deserialize(DEPLOYMENT_MODIFICATION_TYPE,
                                             modification_id,
                                             DeploymentModification,
                                             fields=include)

    def update_deployment_modification(self, modification):

        modification_id = modification.id
        update_doc_data = {}
        if modification.status is not None:
            update_doc_data['status'] = modification.status
        if modification.ended_at is not None:
            update_doc_data['ended_at'] = modification.ended_at
        if modification.node_instances is not None:
            update_doc_data['node_instances'] = modification.node_instances

        update_doc = {'doc': update_doc_data}
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=DEPLOYMENT_MODIFICATION_TYPE,
                                    id=modification_id,
                                    body=update_doc,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Modification {0} not found".format(modification_id))

    def list_deployment_modifications(self, include=None, filters=None,
                                      pagination=None, sort=None):
        return self._get_items_list(DEPLOYMENT_MODIFICATION_TYPE,
                                    DeploymentModification,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination,
                                    sort=sort)

    def update_deployment(self, deployment):
        deployment_id = deployment.id
        update_doc = \
            {'doc': {k: v for k, v in deployment.to_dict().iteritems()
                     if v is not None}}
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=DEPLOYMENT_TYPE,
                                    id=deployment_id,
                                    body=update_doc,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Deployment {0} not found".format(deployment_id))

    @staticmethod
    def _storage_node_id(deployment_id, node_id):
        return '{0}_{1}'.format(deployment_id, node_id)


def create():
    return ESStorageManager(
        config.instance().db_address,
        config.instance().db_port
    )
