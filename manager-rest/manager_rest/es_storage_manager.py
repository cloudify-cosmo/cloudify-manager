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
import manager_exceptions
from manager_rest.models import BlueprintState, Deployment, Execution, \
    DeploymentNode

STORAGE_INDEX_NAME = 'data'
NODE_TYPE = 'node'
BLUEPRINT_TYPE = 'blueprint'
DEPLOYMENT_TYPE = 'deployment'
EXECUTION_TYPE = 'execution'


class ESStorageManager(object):

    def _get_es_conn(self):
        return Elasticsearch()

    def _list_docs(self, doc_type, model_class):
        search_result = self._get_es_conn().search(index=STORAGE_INDEX_NAME,
                                                   doc_type=doc_type)
        docs = map(lambda hit: hit['_source'], search_result['hits']['hits'])
        return map(lambda doc: model_class(**doc), docs)

    def _get_doc(self, doc_type, doc_id, default_value=None):
        try:
            return self._get_es_conn().get(index=STORAGE_INDEX_NAME,
                                           doc_type=doc_type,
                                           id=doc_id)
        except elasticsearch.exceptions.NotFoundError:
            return default_value

    def _get_doc_and_deserialize(self, doc_type, doc_id, model_class,
                                 default_value=None):
        doc = self._get_doc(doc_type, doc_id, default_value)
        if doc != default_value:
            return model_class(**doc['_source'])
        return default_value

    def _put_doc_if_not_exists(self, doc_type, doc_id, value):
        try:
            self._get_es_conn().create(index=STORAGE_INDEX_NAME,
                                       doc_type=doc_type, id=doc_id,
                                       body=value)
        except elasticsearch.exceptions.ConflictError:
            raise manager_exceptions.ConflictError(
                '{0} {1} already exists'.format(doc_type, doc_id))

    def nodes_list(self):
        return self._list_docs(NODE_TYPE, DeploymentNode)

    def blueprints_list(self):
        return self._list_docs(BLUEPRINT_TYPE, BlueprintState)

    def deployments_list(self):
        return self._list_docs(DEPLOYMENT_TYPE, Deployment)

    def executions_list(self):
        return self._list_docs(EXECUTION_TYPE, Execution)

    def get_deployment_executions(self, deployment_id):
        executions = self.executions_list()
        return [execution for execution in executions if
                execution.deployment_id == deployment_id]

    def get_node(self, node_id):
        return self._get_doc_and_deserialize(NODE_TYPE, node_id,
                                             DeploymentNode)

    def get_blueprint(self, blueprint_id):
        return self._get_doc_and_deserialize(BLUEPRINT_TYPE, blueprint_id,
                                             BlueprintState)

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
        self._put_doc_if_not_exists(NODE_TYPE, str(node_id), node.to_dict())

    def update_node(self, node_id, node):
        doc = self._get_doc(NODE_TYPE, node_id)
        if doc is None:
            self.put_node(node_id, node)
            return node.runtime_info
        else:
            prev_rt_info = DeploymentNode(**doc['_source']).runtime_info
            merged_rt_info = dict(prev_rt_info.items() +
                                  node.runtime_info.items())
            #TODO: merge reachable field?
            node = DeploymentNode(id=node_id, runtime_info=merged_rt_info)
            try:
                self._get_es_conn().update(index=STORAGE_INDEX_NAME,
                                           doc_type=NODE_TYPE,
                                           id=str(node_id),
                                           body=node.to_dict(),
                                           version=doc['_version'])
                return merged_rt_info
            except elasticsearch.exceptions.ConflictError:
                raise manager_exceptions.ConflictError(
                    'Node update conflict: mismatching versions')


def create():
    return ESStorageManager()
