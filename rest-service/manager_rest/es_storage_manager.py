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
from manager_rest.models import (BlueprintState,
                                 Snapshot,
                                 Deployment,
                                 DeploymentModification,
                                 Execution,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext,
                                 Plugin)

STORAGE_INDEX_NAME = 'cloudify_storage'
NODE_TYPE = 'node'
NODE_INSTANCE_TYPE = 'node_instance'
PLUGIN_TYPE = 'plugin'
BLUEPRINT_TYPE = 'blueprint'
SNAPSHOT_TYPE = 'snapshot'
DEPLOYMENT_TYPE = 'deployment'
DEPLOYMENT_MODIFICATION_TYPE = 'deployment_modification'
EXECUTION_TYPE = 'execution'
PROVIDER_CONTEXT_TYPE = 'provider_context'
PROVIDER_CONTEXT_ID = 'CONTEXT'

DEFAULT_SEARCH_SIZE = 10000

MUTATE_PARAMS = {
    'refresh': True
}


class ESStorageManager(object):

    def __init__(self, host, port):
        self.es_host = host
        self.es_port = port

    @property
    def _connection(self):
        return Elasticsearch(hosts=[{'host': self.es_host,
                                     'port': self.es_port}])

    def _list_docs(self, doc_type, model_class, body=None, fields=None):
        include = list(fields) if fields else True
        search_result = self._connection.search(index=STORAGE_INDEX_NAME,
                                                doc_type=doc_type,
                                                body=body,
                                                _source=include)
        docs = map(lambda hit: hit['_source'], search_result['hits']['hits'])

        # ES doesn't return _version if using its search API.
        if doc_type == NODE_INSTANCE_TYPE:
            for doc in docs:
                doc['version'] = None
        return [self._fill_missing_fields_and_deserialize(doc, model_class)
                for doc in docs]

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

    def _delete_doc(self, doc_type, doc_id, model_class, id_field='id'):
        try:
            res = self._connection.delete(STORAGE_INDEX_NAME, doc_type,
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

    @staticmethod
    def _build_request_body(filters=None, pagination=None, skip_size=False):
        """
        This method is used to create an elasticsearch request based on the
        Query DSL.
        It performs two actions:
        1. Based on the `filters` param passed to it, it builds a filter based
        query to only return elements that match the provided filters.
        Filters are faster than queries as they are cached and don't
        influence the score.
        2. Based on the `pagination` param, it sets the `size` and `from`
        parameters of the built query to make use of elasticsearch paging
        capabilities.

        :param filters: A dictionary containing filter keys and their expected
                        value.
        :param pagination: A dictionary with optional `page_size` and `offset`
                           keys.
        :param skip_size: If set to `True`, will not add `size` to the
                          body result.
        :return: An elasticsearch Query DSL body.
        """
        terms_lst = []
        body = {}
        if pagination:
            if not skip_size:
                body['size'] = pagination.get('page_size', DEFAULT_SEARCH_SIZE)
            if 'offset' in pagination:
                body['from'] = pagination['offset']
        elif not skip_size:
            body['size'] = DEFAULT_SEARCH_SIZE
        if filters:
            for key, val in filters.iteritems():
                filter_type = 'terms' if isinstance(val, list) else 'term'
                terms_lst.append({filter_type: {key: val}})
            body['query'] = {
                'filtered': {
                    'filter': {
                        'bool': {
                            'must':  terms_lst
                        }
                    }
                }
            }
        return body

    def blueprints_list(self, include=None, filters=None, pagination=None):
        return self._get_items_list(BLUEPRINT_TYPE,
                                    BlueprintState,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include)

    def snapshots_list(self, include=None, filters=None, pagination=None):
        return self._get_items_list(SNAPSHOT_TYPE,
                                    Snapshot,
                                    include=include,
                                    filters=filters,
                                    pagination=pagination)

    def deployments_list(self, include=None, filters=None, pagination=None):
        return self._get_items_list(DEPLOYMENT_TYPE,
                                    Deployment,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include)

    def executions_list(self, include=None, filters=None, pagination=None):
        return self._get_items_list(EXECUTION_TYPE,
                                    Execution,
                                    pagination=pagination,
                                    filters=filters,
                                    include=include)

    def get_blueprint_deployments(self, blueprint_id, include=None):
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

    def get_node_instances(self, include=None, filters=None, pagination=None):
        return self._get_items_list(NODE_INSTANCE_TYPE,
                                    DeploymentNodeInstance,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination)

    def get_plugins(self, include=None, filters=None, pagination=None):
        return self._get_items_list(PLUGIN_TYPE,
                                    Plugin,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination)

    def get_nodes(self, include=None, filters=None, pagination=None):
        return self._get_items_list(NODE_TYPE,
                                    DeploymentNode,
                                    filters=filters,
                                    pagination=pagination,
                                    include=include)

    def _get_items_list(self, doc_type, model_class, include=None,
                        filters=None, pagination=None):
        body = self._build_request_body(filters=filters,
                                        pagination=pagination)
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

    def delete_blueprint(self, blueprint_id):
        return self._delete_doc(BLUEPRINT_TYPE, blueprint_id,
                                BlueprintState)

    def delete_plugin(self, plugin_id):
        return self._delete_doc(PLUGIN_TYPE, plugin_id, Plugin)

    def delete_snapshot(self, snapshot_id):
        return self._delete_doc(SNAPSHOT_TYPE, snapshot_id,
                                Snapshot)

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
        query = self._build_request_body(filters={'deployment_id':
                                                  deployment_id},
                                         skip_size=True)
        self._delete_doc_by_query(EXECUTION_TYPE, query)
        self._delete_doc_by_query(NODE_INSTANCE_TYPE, query)
        self._delete_doc_by_query(NODE_TYPE, query)
        self._delete_doc_by_query(DEPLOYMENT_MODIFICATION_TYPE, query)
        return self._delete_doc(DEPLOYMENT_TYPE, deployment_id, Deployment)

    def delete_execution(self, execution_id):
        return self._delete_doc(EXECUTION_TYPE, execution_id, Execution)

    def delete_node(self, node_id):
        return self._delete_doc(NODE_TYPE, node_id, DeploymentNode)

    def delete_node_instance(self, node_instance_id):
        return self._delete_doc(NODE_INSTANCE_TYPE,
                                node_instance_id,
                                DeploymentNodeInstance)

    def update_node(self, deployment_id, node_id,
                    number_of_instances=None,
                    planned_number_of_instances=None):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        update_doc_data = {}
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
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Node {0} not found".format(node_id))

    def update_node_instance(self, node):
        new_state = node.state
        new_runtime_props = node.runtime_properties
        new_relationships = node.relationships

        current = self.get_node_instance(node.id)
        # Validate version - this is not 100% safe since elasticsearch
        # update doesn't accept the version field.
        if node.version != 0 and current.version != node.version:
            raise manager_exceptions.ConflictError(
                'Node instance update conflict [current_version={0}, updated_'
                'version={1}]'.format(current.version, node.version))

        if new_state is not None:
            current.state = new_state

        if new_runtime_props is not None:
            current.runtime_properties = new_runtime_props

        if new_relationships is not None:
            current.relationships = new_relationships

        updated = current.to_dict()
        del updated['version']

        self._connection.index(index=STORAGE_INDEX_NAME,
                               doc_type=NODE_INSTANCE_TYPE,
                               id=node.id,
                               body=updated,
                               **MUTATE_PARAMS)

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

    def deployment_modifications_list(self, include=None, filters=None,
                                      pagination=None):
        return self._get_items_list(DEPLOYMENT_MODIFICATION_TYPE,
                                    DeploymentModification,
                                    filters=filters,
                                    include=include,
                                    pagination=pagination)

    @staticmethod
    def _storage_node_id(deployment_id, node_id):
        return '{0}_{1}'.format(deployment_id, node_id)


def create():
    return ESStorageManager(
        config.instance().db_address,
        config.instance().db_port
    )
