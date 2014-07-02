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

__author__ = 'ran'

from elasticsearch import Elasticsearch
import elasticsearch.exceptions
from manager_rest import manager_exceptions
from manager_rest.models import (BlueprintState,
                                 Deployment,
                                 Execution,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext)

STORAGE_INDEX_NAME = 'cloudify_storage'
NODE_TYPE = 'node'
NODE_INSTANCE_TYPE = 'node_instance'
BLUEPRINT_TYPE = 'blueprint'
DEPLOYMENT_TYPE = 'deployment'
EXECUTION_TYPE = 'execution'
PROVIDER_CONTEXT_TYPE = 'provider_context'
PROVIDER_CONTEXT_ID = 'CONTEXT'

DEFAULT_SEARCH_SIZE = 10000


class ESStorageManager(object):

    def _get_es_conn(self):
        return Elasticsearch()

    def _list_docs(self, doc_type, model_class, query=None, fields=None):
        include = list(fields) if fields else True
        search_result = self._get_es_conn().search(index=STORAGE_INDEX_NAME,
                                                   doc_type=doc_type,
                                                   size=DEFAULT_SEARCH_SIZE,
                                                   body=query,
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
                return self._get_es_conn().get(index=STORAGE_INDEX_NAME,
                                               doc_type=doc_type,
                                               id=doc_id,
                                               _source=[f for f in fields])
            else:
                return self._get_es_conn().get(index=STORAGE_INDEX_NAME,
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
            self._get_es_conn().create(index=STORAGE_INDEX_NAME,
                                       doc_type=doc_type, id=doc_id,
                                       body=value)
        except elasticsearch.exceptions.ConflictError:
            raise manager_exceptions.ConflictError(
                '{0} {1} already exists'.format(doc_type, doc_id))

    def _delete_doc(self, doc_type, doc_id, model_class, id_field='id'):
        try:
            res = self._get_es_conn().delete(STORAGE_INDEX_NAME, doc_type,
                                             doc_id)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "{0} {1} not found".format(doc_type, doc_id))

        fields_data = {
            id_field: res['_id']
        }
        return self._fill_missing_fields_and_deserialize(fields_data,
                                                         model_class)

    def _delete_doc_by_query(self, doc_type, query):
        self._get_es_conn().delete_by_query(index=STORAGE_INDEX_NAME,
                                            doc_type=doc_type,
                                            body=query)

    def _fill_missing_fields_and_deserialize(self, fields_data, model_class):
        for field in model_class.fields:
            if field not in fields_data:
                fields_data[field] = None
        return model_class(**fields_data)

    @staticmethod
    def _build_field_value_filter(key, val):
        # This method is used to create a search filter to receive only
        # results where a specific key holds a specific value.
        # Filters are faster than queries as they are cached and don't
        # influence the score.
        # Since a filter must go along with a query, it's wrapped in a
        # simple 'constant_score' query in this case (similar to match_all
        # query in some ways)
        return {
            'query': {
                'constant_score': {
                    'filter': {
                        'term': {
                            key: val
                        }
                    }
                }
            }
        }

    def node_instances_list(self, include=None):
        search_result = self._get_es_conn().search(index=STORAGE_INDEX_NAME,
                                                   doc_type=NODE_INSTANCE_TYPE,
                                                   size=DEFAULT_SEARCH_SIZE,
                                                   _source=include or True)
        docs_with_versions = \
            map(lambda hit: (hit['_source'], hit['_version']),
                search_result['hits']['hits'])
        return map(
            lambda doc_with_version: DeploymentNodeInstance(
                version=doc_with_version[1], **doc_with_version[0]),
            docs_with_versions)

    def blueprints_list(self, include=None):
        return self._list_docs(BLUEPRINT_TYPE, BlueprintState, fields=include)

    def deployments_list(self, include=None):
        return self._list_docs(DEPLOYMENT_TYPE, Deployment, fields=include)

    def executions_list(self, include=None):
        return self._list_docs(EXECUTION_TYPE, Execution, fields=include)

    def get_blueprint_deployments(self, blueprint_id, include=None):
        return self._list_docs(DEPLOYMENT_TYPE, Deployment,
                               self._build_field_value_filter(
                                   'blueprint_id', blueprint_id),
                               fields=include)

    def get_deployment_executions(self, deployment_id, include=None):
        return self._list_docs(EXECUTION_TYPE, Execution,
                               self._build_field_value_filter(
                                   'deployment_id', deployment_id),
                               fields=include)

    def get_node_instance(self, node_instance_id, include=None):
        doc = self._get_doc(NODE_INSTANCE_TYPE,
                            node_instance_id,
                            fields=include)
        node = DeploymentNodeInstance(version=doc['_version'],
                                      **doc['_source'])
        return node

    def get_node_instances(self, deployment_id, include=None):
        query = None
        if deployment_id:
            query = {'query': {'term': {'deployment_id': deployment_id}}}
        return self._list_docs(NODE_INSTANCE_TYPE,
                               DeploymentNodeInstance,
                               query=query,
                               fields=include)

    def get_nodes(self, deployment_id=None, include=None):
        query = None
        if deployment_id:
            query = {'query': {'term': {'deployment_id': deployment_id}}}
        return self._list_docs(NODE_TYPE,
                               DeploymentNode,
                               query=query,
                               fields=include)

    def get_blueprint(self, blueprint_id, include=None):
        return self._get_doc_and_deserialize(BLUEPRINT_TYPE,
                                             blueprint_id,
                                             BlueprintState,
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

    def put_blueprint(self, blueprint_id, blueprint):
        self._put_doc_if_not_exists(BLUEPRINT_TYPE, str(blueprint_id),
                                    blueprint.to_dict())

    def put_deployment(self, deployment_id, deployment):
        self._put_doc_if_not_exists(DEPLOYMENT_TYPE, str(deployment_id),
                                    deployment.to_dict())

    def put_execution(self, execution_id, execution):
        self._put_doc_if_not_exists(EXECUTION_TYPE, str(execution_id),
                                    execution.to_dict())

    def put_node(self, node):
        node_id = '{0}_{1}'.format(node.deployment_id, node.id)
        doc_data = node.to_dict()
        self._put_doc_if_not_exists(NODE_TYPE, str(node_id), doc_data)

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

    def update_execution_status(self, execution_id, status, error):
        update_doc_data = {'status': status,
                           'error': error}
        update_doc = {'doc': update_doc_data}

        try:
            self._get_es_conn().update(index=STORAGE_INDEX_NAME,
                                       doc_type=EXECUTION_TYPE,
                                       id=str(execution_id),
                                       body=update_doc)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Execution {0} not found".format(execution_id))

    def delete_deployment(self, deployment_id):
        query = {'query': {'term': {'deployment_id': deployment_id}}}
        self._delete_doc_by_query(EXECUTION_TYPE, query)
        self._delete_doc_by_query(NODE_INSTANCE_TYPE, query)
        self._delete_doc_by_query(NODE_TYPE, query)
        return self._delete_doc(DEPLOYMENT_TYPE, deployment_id, Deployment)

    def delete_execution(self, execution_id):
        return self._delete_doc(EXECUTION_TYPE, execution_id, Execution)

    def delete_node(self, node_id):
        return self._delete_doc(NODE_TYPE, node_id, DeploymentNode)

    def delete_node_instance(self, node_instance_id):
        return self._delete_doc(NODE_INSTANCE_TYPE,
                                node_instance_id,
                                DeploymentNodeInstance)

    def update_node_instance(self, node):
        update_doc_data = node.to_dict()
        # deleting version field as it's maintained by ES internally
        del(update_doc_data['version'])
        # removing fields with value None as they're not to be updated
        update_doc_data = \
            {k: v for k, v in update_doc_data.iteritems() if v is not None}
        update_doc = {'doc': update_doc_data}

        try:
            self._get_es_conn().update(index=STORAGE_INDEX_NAME,
                                       doc_type=NODE_INSTANCE_TYPE,
                                       id=str(node.id),
                                       body=update_doc,
                                       version=node.version)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Node {0} not found".format(node.id))
        except elasticsearch.exceptions.ConflictError:
            raise manager_exceptions.ConflictError(
                'Node update conflict: mismatching versions')

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


def create():
    return ESStorageManager()
