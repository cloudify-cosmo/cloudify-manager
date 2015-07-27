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


import inspect

import elasticsearch.exceptions
from elasticsearch import Elasticsearch

from manager_rest import config
from manager_rest import manager_exceptions
from manager_rest.abstract_storage_manager import AbstractStorageManager
from manager_rest.models import (BlueprintState,
                                 Deployment,
                                 DeploymentModification,
                                 Execution,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext)


STORAGE_INDEX_NAME = 'cloudify_storage'
NODE_INSTANCE_TYPE = 'node_instance'
DEFAULT_SEARCH_SIZE = 10000

MUTATE_PARAMS = {
    'refresh': True
}
ID_ATTRIBUTE = 'id'

'''
NODE_TYPE = 'node'
BLUEPRINT_TYPE = 'blueprint'
DEPLOYMENT_TYPE = 'deployment'
DEPLOYMENT_MODIFICATION_TYPE = 'deployment_modification'

PROVIDER_CONTEXT_ID = 'CONTEXT'

'''


class ESStorageManager(AbstractStorageManager):

    def __init__(self, host, port):
        self.es_host = host
        self.es_port = port

    @property
    def _connection(self):
        return Elasticsearch(hosts=[{'host': self.es_host,
                                     'port': self.es_port}])

    def _doc_exists(self, collection_name, filter_by):
        query = self._build_field_value_filter(filter_by)
        count_result = self._connection.count(index=STORAGE_INDEX_NAME,
                                              doc_type=collection_name,
                                              body=query)
        print 'got count result: {0}'.format(count_result)
        count = count_result['count']
        print 'returning value: {0}'.format(count > 0)
        return count > 0

    def _get_id_attribute(self):
        return ID_ATTRIBUTE

    def _get_document_by_id(self, collection_name, doc_id, fields=None):
        document = self._connection.get(index=STORAGE_INDEX_NAME,
                                      id=doc_id,
                                      doc_type=collection_name,
                                      fields=fields)
        print 'returning document: {0}'.format(document)
        return document

    def _list_documents(self, collection_name, filter_by=None, include_fields=None):
        include = list(include_fields) if include_fields else True
        query = self._build_field_value_filter(filter_by)
        search_result = self._connection.search(index=STORAGE_INDEX_NAME,
                                                doc_type=collection_name,
                                                size=DEFAULT_SEARCH_SIZE,
                                                body=query,
                                                _source=include)
        return map(lambda hit: hit['_source'], search_result['hits']['hits'])

    @staticmethod
    def _fill_missing_fields(document, model_class):
        try:
            if model_class == DeploymentNodeInstance:
                if not document.get('version'):
                    document['version'] = None

            for field in model_class.fields:
                if field not in document:
                    document[field] = None
        except Exception as e:
            print 'Failed to fill missing data, error: {0}'.format(e)
            raise e
        return document

    def _insert_document(self, collection_name, document):
        self._connection.create(index=STORAGE_INDEX_NAME,
                                doc_type=collection_name,
                                body=document,
                                id=document['id'],
                                **MUTATE_PARAMS)

    def _update_documents(self, collection_name, updated_values, filter_by=None):
        # implemented here as update document (a single document)
        updated_doc = {'doc': updated_values}
        document_id = filter_by['id']
        try:
            self._connection.update(index=STORAGE_INDEX_NAME,
                                    doc_type=collection_name,
                                    id=document_id,
                                    body=updated_doc,
                                    **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Document id {0} not found in {1}".format(document_id,
                                                          collection_name))

    def _delete_documents(self, collection_name, filter_by):
        query = self._build_field_value_filter(filter_by)
        self._connection.delete_by_query(index=STORAGE_INDEX_NAME,
                                         doc_type=collection_name,
                                         body=query)

    def _delete_document(self, collection_name, document_id, model_class):
        try:
            res = self._connection.delete(STORAGE_INDEX_NAME, collection_name,
                                          document_id,
                                          **MUTATE_PARAMS)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "{0} {1} not found".format(collection_name, document_id))

        fields_data = {
            self._get_id_attribute(): res['_id']
        }
        return self._fill_missing_fields_and_deserialize(fields_data,
                                                         model_class)

    def _db_encode(self, document):
        return document

    def _db_decode(self, document):
        return document

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
    def _build_field_value_filter(filter_by):
        # This method is used to create a search filter to receive only
        # results where a specific key holds a specific value.
        # Filters are faster than queries as they are cached and don't
        # influence the score.
        # Since a filter must go along with a query, it's wrapped in a
        # simple 'constant_score' query in this case (similar to match_all
        # query in some ways)
        query = None
        if not filter:
            return query

        if len(filter_by) == 1:
            key, val = filter_by.iteritems().next()
            query = {
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
        elif len(filter_by) > 1:
            terms = []
            for key, val in filter_by.iteritems():
                terms.append({'term': {key: val}})
            query = {'query': {'bool': {'must': terms}}}

        return query

    def node_instances_list(self, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        search_result = self._connection.search(index=STORAGE_INDEX_NAME,
                                                doc_type=NODE_INSTANCE_TYPE,
                                                size=DEFAULT_SEARCH_SIZE,
                                                _source=include or True)
        docs_with_versions = \
            map(lambda hit: (hit['_source'], hit['_version']),
                search_result['hits']['hits'])
        print 'ended {0}'.format(inspect.stack()[0][3])
        return map(
            lambda doc_with_version: DeploymentNodeInstance(
                version=doc_with_version[1], **doc_with_version[0]),
            docs_with_versions)

    def get_node_instance(self, node_instance_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        document = self._get_document_by_id(NODE_INSTANCE_TYPE, node_instance_id,
                                            include)
        self._validate_included_fields(document, include)
        node = DeploymentNodeInstance(version=document['_version'],
                                      **document['_source'])
        print 'ended {0}'.format(inspect.stack()[0][3])
        return node

    def get_node_instances(self, deployment_id, node_id=None, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        query = None
        # deployment id is mandatory, so why ask?
        if deployment_id or node_id:
            terms = []
            if deployment_id:
                terms.append({'term': {'deployment_id': deployment_id}})
            if node_id:
                terms.append({'term': {'node_id': node_id}})
            query = {'query': {'bool': {'must': terms}}}
        docs = self._list_docs(NODE_INSTANCE_TYPE,
                               DeploymentNodeInstance,
                               query=query,
                               fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return docs

    def put_node_instance(self, node_instance):
        print 'starting {0}'.format(inspect.stack()[0][3])
        node_instance_id = node_instance.id
        doc_data = node_instance.to_dict()
        del(doc_data['version'])
        self._put_doc_if_not_exists(NODE_INSTANCE_TYPE,
                                    str(node_instance_id),
                                    doc_data)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return 1

    def update_node_instance(self, node):
        print('in update_node_instance')
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


def create():
    return ESStorageManager(
        config.instance().db_address,
        config.instance().db_port
    )
