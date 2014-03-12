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
                                 DeploymentNode)

STORAGE_INDEX_NAME = 'cloudify_storage'
NODE_TYPE = 'node'
BLUEPRINT_TYPE = 'blueprint'
DEPLOYMENT_TYPE = 'deployment'
EXECUTION_TYPE = 'execution'

DEFAULT_SEARCH_SIZE = 500


class ESStorageManager(object):

    def _get_es_conn(self):
        return Elasticsearch()

    def _list_docs(self, doc_type, model_class):
        search_result = self._get_es_conn().search(index=STORAGE_INDEX_NAME,
                                                   doc_type=doc_type,
                                                   size=DEFAULT_SEARCH_SIZE)
        docs = map(lambda hit: hit['_source'], search_result['hits']['hits'])
        return map(lambda doc: model_class(**doc), docs)

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

    def _fill_missing_fields_and_deserialize(self, fields_data, model_class):
        for field in model_class.fields:
            if field not in fields_data:
                fields_data[field] = None
        return model_class(**fields_data)

    def nodes_list(self):
        search_result = self._get_es_conn().search(index=STORAGE_INDEX_NAME,
                                                   doc_type=NODE_TYPE,
                                                   size=DEFAULT_SEARCH_SIZE)
        docs_with_versions = \
            map(lambda hit: (hit['_source'], hit['_version']),
                search_result['hits']['hits'])
        return map(
            lambda doc_with_version: DeploymentNode(
                state_version=doc_with_version[1], **doc_with_version[0]),
            docs_with_versions)

    def blueprints_list(self):
        return self._list_docs(BLUEPRINT_TYPE, BlueprintState)

    def deployments_list(self):
        return self._list_docs(DEPLOYMENT_TYPE, Deployment)

    def executions_list(self):
        return self._list_docs(EXECUTION_TYPE, Execution)

    def get_blueprint_deployments(self, blueprint_id):
        #TODO: make this using a specific search
        deployments = self.deployments_list()
        return [deployment for deployment in deployments if
                deployment.blueprint_id == blueprint_id]

    def get_deployment_executions(self, deployment_id):
        #TODO: make this using a specific search
        executions = self.executions_list()
        return [execution for execution in executions if
                execution.deployment_id == deployment_id]

    def get_node(self, node_id):
        doc = self._get_doc(NODE_TYPE, node_id)
        node = DeploymentNode(state_version=doc['_version'], **doc['_source'])
        return node

    def get_blueprint(self, blueprint_id, fields=None):
        return self._get_doc_and_deserialize(BLUEPRINT_TYPE, blueprint_id,
                                             BlueprintState, fields)

    def get_deployment(self, deployment_id):
        return self._get_doc_and_deserialize(DEPLOYMENT_TYPE, deployment_id,
                                             Deployment)

    def get_execution(self, execution_id):
        return self._get_doc_and_deserialize(EXECUTION_TYPE, execution_id,
                                             Execution)

    def put_blueprint(self, blueprint_id, blueprint):
        self._put_doc_if_not_exists(BLUEPRINT_TYPE, str(blueprint_id),
                                    blueprint.to_dict())

    def put_deployment(self, deployment_id, deployment):
        self._put_doc_if_not_exists(DEPLOYMENT_TYPE, str(deployment_id),
                                    deployment.to_dict())

    def put_execution(self, execution_id, execution):
        self._put_doc_if_not_exists(EXECUTION_TYPE, str(execution_id),
                                    execution.to_dict())

    def put_node(self, node_id, node):
        doc_data = node.to_dict()
        del(doc_data['state_version'])
        self._put_doc_if_not_exists(NODE_TYPE, str(node_id), doc_data)
        return 1

    def delete_blueprint(self, blueprint_id):
        return self._delete_doc(BLUEPRINT_TYPE, blueprint_id,
                                BlueprintState)

    def update_node(self, node_id, node):
        update_doc_data = node.to_dict()
        del(update_doc_data['state_version'])
        update_doc = {'doc': update_doc_data}

        try:
            self._get_es_conn().update(index=STORAGE_INDEX_NAME,
                                       doc_type=NODE_TYPE,
                                       id=str(node_id),
                                       body=update_doc,
                                       version=node.state_version)
        except elasticsearch.exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                "Node {0} not found".format(node_id))
        except elasticsearch.exceptions.ConflictError:
            raise manager_exceptions.ConflictError(
                'Node update conflict: mismatching versions')


def create():
    return ESStorageManager()
