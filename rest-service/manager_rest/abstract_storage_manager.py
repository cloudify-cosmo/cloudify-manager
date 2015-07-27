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


import abc

import inspect
from manager_rest import manager_exceptions
from manager_rest.models import (BlueprintState,
                                 Deployment,
                                 DeploymentModification,
                                 Execution,
                                 DeploymentNode,
                                 DeploymentNodeInstance,
                                 ProviderContext)

BLUEPRINTS_COLLECTION = 'blueprints'
NODES_COLLECTION = 'nodes'
NODE_INSTANCES_COLLECTION = 'node_instances'
EXECUTIONS_COLLECTION = 'executions'
DEPLOYMENTS_COLLECTION = 'deployments'
DEPLOYMENT_MODIFICATIONS_COLLECTION = 'deployment_modifications'
PROVIDER_CONTEXT_COLLECTION = 'provider_context'
PROVIDER_CONTEXT_ID = 111


class AbstractStorageManager(object):

    __metaclass__ = abc.ABCMeta

    # ############################## abstract methods ############################## #

    @abc.abstractmethod
    def _doc_exists(self, collection_name, filter_by):
        raise NotImplementedError

    @abc.abstractmethod
    def _get_id_attribute(self):
        raise NotImplementedError

    @abc.abstractmethod
    def _get_document_by_id(self, collection_name, doc_id, fields=None):
        raise NotImplementedError

    @abc.abstractmethod
    def _list_documents(self, collection_name, filter_by=None,
                        include_fields=None):
        raise NotImplementedError

    @abc.abstractmethod
    def _insert_document(self, collection_name, document):
        raise NotImplementedError

    @abc.abstractmethod
    def _update_documents(self, collection_name, updated_values, filter_by=None):
        raise NotImplementedError

    @abc.abstractmethod
    def _delete_document(self, collection_name, document_id, model_class):
        raise NotImplementedError

    @abc.abstractmethod
    def _delete_documents(self, collection_name, filter_by):
        raise NotImplementedError

    @abc.abstractmethod
    def _db_encode(self, document):
        raise NotImplementedError

    @abc.abstractmethod
    def _db_decode(self, document):
        raise NotImplementedError

    # ############################## static methods ############################## #

    @staticmethod
    def _storage_node_id(deployment_id, node_id):
        return '{0}_{1}'.format(deployment_id, node_id)

    @staticmethod
    def _validate_included_fields(document, include_fields=None):
        if not include_fields:
            return

        missing_fields = [field for field in include_fields if field not
                          in document]
        if missing_fields:
            msg = 'Some or all fields specified for query were missing: {0}'. \
                format(missing_fields)
            print msg
            raise RuntimeError(msg)

    @staticmethod
    def _fill_missing_fields(document, model_class):
        try:
            if model_class == DeploymentNodeInstance:
                if not document.get('version'):
                    document['version'] = 0

            for field in model_class.fields:
                if field not in document:
                    document[field] = None
        except Exception as e:
            print 'Failed to fill missing data, error: {0}'.format(e)
            raise e
        return document

    @staticmethod
    def _deserialize_document(document, model_class):
        AbstractStorageManager._fill_missing_fields(document, model_class)
        instance = model_class(**document)
        return instance

    # ############################## wrapper methods ############################## #

    def _insert_doc_if_not_exists(self, collection_name, document,
                                  filter_by=None):
        id_attr = self._get_id_attribute()
        print 'inserting document: {0}'.format(document)
        filter_by = filter_by or {id_attr: str(document['id'])}
        print 'searching if exists, filtering by: ', filter_by
        if self._doc_exists(collection_name, filter_by):
            print 'document exists, not inserting into {0}'. \
                format(collection_name)
        else:
            print 'document not found, inserting into {0}'.format(
                collection_name)
            self._insert_document(collection_name, self._db_encode(document))

    def _get_document_and_deserialize(self, collection_name, document_id,
                                      model_class, include_fields=None):
        document = self._get_document_by_id(collection_name, document_id,
                                            include_fields)
        self._validate_included_fields(document, include_fields)
        return self._deserialize_document(document, model_class)

    def _list_documents_and_deserialize(self, collection_name, model_class,
                                        filter_by=None, include_fields=None):
        documents = []
        raw_documents = self._list_documents(collection_name, filter_by,
                                             include_fields)
        if raw_documents:
            for doc in raw_documents:
                doc = self._db_decode(doc)
                self._validate_included_fields(doc, include_fields)
                documents.append(self._deserialize_document(doc, model_class))
        return documents

    # ############################## public methods ############################## #

    def get_provider_context(self, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        ctx = self._get_document_and_deserialize(
            collection_name=PROVIDER_CONTEXT_COLLECTION,
            document_id=PROVIDER_CONTEXT_ID, model_class=ProviderContext,
            include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return ctx

    def put_provider_context(self, provider_context):
        print 'starting {0}'.format(inspect.stack()[0][3])
        provider_context_dict = provider_context.to_dict()
        provider_context_dict['id'] = PROVIDER_CONTEXT_ID
        self._insert_doc_if_not_exists(PROVIDER_CONTEXT_COLLECTION,
                                       provider_context_dict)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def update_provider_context(self, provider_context):
        print 'starting {0}'.format(inspect.stack()[0][3])
        filter_by = {'id': PROVIDER_CONTEXT_ID}
        self._update_documents(PROVIDER_CONTEXT_COLLECTION,
                               provider_context.to_dict(),
                               filter_by)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def get_blueprint(self, blueprint_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        blueprint = self._get_document_and_deserialize(
            collection_name=BLUEPRINTS_COLLECTION, document_id=blueprint_id,
            model_class=BlueprintState, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return blueprint

    def put_blueprint(self, blueprint_id, blueprint):
        print 'starting {0}'.format(inspect.stack()[0][3])
        self._insert_doc_if_not_exists(BLUEPRINTS_COLLECTION,
                                       blueprint.to_dict())
        print 'ended {0}'.format(inspect.stack()[0][3])

    def blueprints_list(self, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        blueprints = self._list_documents_and_deserialize(
            collection_name=BLUEPRINTS_COLLECTION, model_class=BlueprintState,
            include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return blueprints

    def delete_blueprint(self, blueprint_id):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deleted = self._delete_document(BLUEPRINTS_COLLECTION, blueprint_id,
                                        BlueprintState)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deleted

    def get_deployment(self, deployment_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deployment = self._get_document_and_deserialize(
            collection_name=DEPLOYMENTS_COLLECTION, document_id=deployment_id,
            model_class=Deployment, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deployment

    def get_blueprint_deployments(self, blueprint_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        filter_by = {'blueprint_id': blueprint_id}
        docs = self._list_documents_and_deserialize(
            collection_name=DEPLOYMENTS_COLLECTION, model_class=Deployment,
            filter_by=filter_by, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return docs

    def put_deployment(self, deployment_id, deployment):
        print 'starting {0}'.format(inspect.stack()[0][3])
        self._insert_doc_if_not_exists(DEPLOYMENTS_COLLECTION,
                                       deployment.to_dict())
        print 'ended {0}'.format(inspect.stack()[0][3])

    def deployments_list(self, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deployments = self._list_documents_and_deserialize(
            collection_name=DEPLOYMENTS_COLLECTION, model_class=Deployment,
            include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deployments

    def delete_deployment(self, deployment_id):
        print 'starting {0}'.format(inspect.stack()[0][3])
        filter_by = {'deployment_id': deployment_id}
        self._delete_documents(EXECUTIONS_COLLECTION, filter_by)
        self._delete_documents(NODE_INSTANCES_COLLECTION, filter_by)
        self._delete_documents(NODES_COLLECTION, filter_by)
        self._delete_documents(DEPLOYMENT_MODIFICATIONS_COLLECTION, filter_by)
        deleted = self._delete_document(DEPLOYMENTS_COLLECTION, deployment_id,
                                        Deployment)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deleted

    def get_deployment_modification(self, modification_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        modification = self._get_document_and_deserialize(
            DEPLOYMENT_MODIFICATIONS_COLLECTION, modification_id,
            DeploymentModification, fields=include)
        return modification

    def put_deployment_modification(self, modification_id, modification):
        print 'starting {0}'.format(inspect.stack()[0][3])
        self._insert_doc_if_not_exists(DEPLOYMENT_MODIFICATIONS_COLLECTION,
                                       modification.to_dict())
        print 'ended {0}'.format(inspect.stack()[0][3])

    def update_deployment_modification(self, modification):
        print('in update_deployment_modification')
        filter_by = {'id': modification.id}
        updated_doc_data = {}
        if modification.status is not None:
            updated_doc_data['status'] = modification.status
        if modification.ended_at is not None:
            updated_doc_data['ended_at'] = modification.ended_at
        if modification.node_instances is not None:
            updated_doc_data['node_instances'] = modification.node_instances

        self._update_documents(
            collection_name=DEPLOYMENT_MODIFICATIONS_COLLECTION,
            updated_values=updated_doc_data, filter_by=filter_by)

    def deployment_modifications_list(self, deployment_id=None, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        query = None
        filter_by = {}
        if deployment_id:
            filter_by['deployment_id'] = deployment_id
        modifications = self._list_documents_and_deserialize(
            collection_name=DEPLOYMENT_MODIFICATIONS_COLLECTION,
            model_class=DeploymentModification, filter_by=filter_by,
            include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return modifications

    def get_node(self, deployment_id, node_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        filter_by = {"storage_node_id": storage_node_id}
        docs = self._list_documents_and_deserialize(
            collection_name=NODES_COLLECTION, model_class=DeploymentNode,
            filter_by=filter_by, include_fields=include)

        # TODO This validation should be done before deserializing, no point
        # in deserializing wrong docs
        if len(docs) != 1:
            print 'expected a single node document matching filter {0}, ' \
                  'but found {1}'.format(filter_by, len(docs))
            raise manager_exceptions.NotFoundError(
                'expected a single node document matching filter {0}, '
                'but found {1}'.format(filter_by, len(docs)))
        print 'ended {0}'.format(inspect.stack()[0][3])
        return docs[0]

    def get_nodes(self, deployment_id=None, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        nodes = self._list_documents_and_deserialize(
            collection_name=NODES_COLLECTION, model_class=DeploymentNode,
            filter_by={"deployment_id": deployment_id}, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return nodes

    def put_node(self, node):
        print 'starting {0}'.format(inspect.stack()[0][3])
        node_dict = node.to_dict()
        storage_node_id = self._storage_node_id(node.deployment_id, node.id)
        node_dict['storage_node_id'] = storage_node_id
        filter_by = {"storage_node_id": storage_node_id}
        self._insert_doc_if_not_exists(NODES_COLLECTION, node_dict, filter_by)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def update_node(self, deployment_id, node_id,
                    number_of_instances=None,
                    planned_number_of_instances=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        filter_by = {"id": storage_node_id}
        updated_doc = {}
        if number_of_instances is not None:
            updated_doc['number_of_instances'] = number_of_instances
        if planned_number_of_instances is not None:
            updated_doc[
                'planned_number_of_instances'] = planned_number_of_instances

        self._update_documents(NODES_COLLECTION, updated_doc, filter_by)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def delete_node(self, node_id):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deleted = self._delete_doc(NODES_COLLECTION, node_id, DeploymentNode)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deleted

    def get_node_instance(self, node_instance_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        instance = self._get_document_and_deserialize(
            collection_name=NODE_INSTANCES_COLLECTION,
            document_id=node_instance_id, model_class=DeploymentNodeInstance,
            include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return instance

    def get_node_instances(self, deployment_id, node_id=None, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        # deployment id is mandatory, so why ask?
        filter_by = {}
        if deployment_id:
            filter_by['deployment_id'] = deployment_id
        if node_id:
            filter_by['node_id'] = node_id
        instances = self._list_documents_and_deserialize(
            collection_name=NODE_INSTANCES_COLLECTION,
            model_class=DeploymentNodeInstance,
            filter_by=filter_by, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return instances

    def put_node_instance(self, node_instance):
        print 'starting {0}'.format(inspect.stack()[0][3])
        node_instance_dict = node_instance.to_dict()
        if not node_instance_dict.get('version'):
            print 'setting node instance version to 0 instead of None'
            node_instance_dict['version'] = 0
        self._insert_doc_if_not_exists(NODE_INSTANCES_COLLECTION,
                                       node_instance_dict)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return 1

    def update_node_instance(self, node):
        print 'starting {0}'.format(inspect.stack()[0][3])
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

        updated_values = {}
        if new_state is not None:
            updated_values['state'] = new_state
        if new_runtime_props is not None:
            updated_values['runtime_properties'] = new_runtime_props
        if new_relationships is not None:
            updated_values['relationships'] = new_relationships

        filter_by = {"node_id": node.id}
        self._update_documents(NODE_INSTANCES_COLLECTION, updated_values,
                               filter_by)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def delete_node_instance(self, node_instance_id):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deleted = self._delete_doc(NODE_INSTANCES_COLLECTION,
                                   node_instance_id,
                                   DeploymentNodeInstance)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deleted

    def get_execution(self, execution_id, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        execution = self._get_document_and_deserialize(
            collection_name=EXECUTIONS_COLLECTION, document_id=execution_id,
            model_class=Execution, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return execution

    def put_execution(self, execution_id, execution):
        print 'starting {0}'.format(inspect.stack()[0][3])
        self._insert_doc_if_not_exists(EXECUTIONS_COLLECTION,
                                       execution.to_dict())
        print 'ended {0}'.format(inspect.stack()[0][3])

    def update_execution_status(self, execution_id, status, error):
        print 'starting {0}'.format(inspect.stack()[0][3])
        updated_values = {"status": status, "error": error}
        filter_by = {"id": str(execution_id)}
        self._update_documents(EXECUTIONS_COLLECTION,
                               updated_values,
                               filter_by)
        print 'ended {0}'.format(inspect.stack()[0][3])

    def executions_list(self, deployment_id=None, include=None):
        print 'starting {0}'.format(inspect.stack()[0][3])
        executions = self._list_documents_and_deserialize(
            collection_name=EXECUTIONS_COLLECTION, model_class=Execution,
            filter_by={"deployment_id": deployment_id}, include_fields=include)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return executions

    def delete_execution(self, execution_id):
        print 'starting {0}'.format(inspect.stack()[0][3])
        deleted = self._delete_document(EXECUTIONS_COLLECTION, execution_id,
                                        Execution)
        print 'ended {0}'.format(inspect.stack()[0][3])
        return deleted
