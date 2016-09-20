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

import uuid
from functools import wraps
from flask import current_app
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError

from manager_rest import manager_exceptions
from manager_rest.storage.models import db
from manager_rest.storage.models import (Blueprint,
                                         Snapshot,
                                         Deployment,
                                         DeploymentUpdate,
                                         DeploymentUpdateStep,
                                         DeploymentModification,
                                         Execution,
                                         Node,
                                         NodeInstance,
                                         ProviderContext,
                                         Plugin)

PROVIDER_CONTEXT_ID = 'CONTEXT'
TABLE_LOCK_STR = 'LOCK TABLE {0} IN ACCESS EXCLUSIVE MODE;'


def _close_session(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        finally:
            db.session.close()
            db.engine.dispose()
    return wrapper


@contextmanager
def _lock_table(table_class):
    """Use optimistic lock to lock out a postgres table table

    :param table_class: The SQLAlchemy class
    """
    sql_connection_str = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    sql_dialect = sql_connection_str.split(':')[0]

    # Locking is only relevant for PostgreSQL
    if 'postgresql' in sql_dialect:
        table_name = table_class.__tablename__
        db.session.begin_nested()  # Start nested transaction
        db.session.execute(TABLE_LOCK_STR.format(table_name))
        try:
            yield
        finally:
            db.session.commit()  # Commit the nested transaction
    else:
        yield


class SQLStorageManager(object):
    @staticmethod
    @_close_session
    def _safe_commit(exception=None):
        """Try to commit changes in the session. Roll back if exception raised

        Excepts SQLAlchemy errors and rollbacks if they're caught
        :param exception: Optional exception to raise instead of the
        one raised by SQLAlchemy
        """
        try:
            db.session.flush()
            db.session.expunge_all()
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            if exception:
                full_err = '{0}\nSQL error: {1}'.format(
                    str(exception), str(e)
                )
                exception.args = (full_err,) + exception.args[1:]
                raise exception
            raise

    def _safe_add(self, instance):
        """Add `instance` to the DB session, and attempt to commit

        :param instance: Instance to be added to the DB
        """
        db.session.add(instance)
        custom_exception = manager_exceptions.ConflictError(
            '{0} with ID `{1}` already exists'.format(
                instance.__class__.__name__,
                instance.id
            )
        )
        self._safe_commit(custom_exception)
        return instance

    @staticmethod
    def _get_base_query(model_class, include=None):
        """Create the initial query from the model class and included columns

        :param model_class: SQL DB table class
        :param include: An optional list of columns to include in the query
        :return: An SQLAlchemy AppenderQuery object
        """
        # If all columns should be returned, query directly from the model
        if not include:
            return model_class.query

        for column_name in include:
            if not hasattr(model_class, column_name):
                raise manager_exceptions.BadParametersError(
                    'Class {0} does not have a {1} field'.format(
                        model_class.__name__, column_name
                    )
                )
        # If only some columns are included, query through the session object
        columns_to_query = [getattr(model_class, column) for column in include]
        return db.session.query(*columns_to_query)

    @staticmethod
    def _sort_query(query, model_class, sort=None):
        """Add sorting clauses to the query

        :param query: Base SQL query
        :param model_class: SQL DB table class
        :param sort: An optional dictionary where keys are column names to
        sort by, and values are the order (asc/desc)
        :return: An SQLAlchemy AppenderQuery object
        """
        if sort:
            for sort_param, order in sort.iteritems():
                column = getattr(model_class, sort_param)
                if order == 'desc':
                    column = column.desc()
                query = query.order_by(column)
        return query

    @staticmethod
    def _filter_query(query, model_class, filters=None):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param model_class: SQL DB table class
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :return: An SQLAlchemy AppenderQuery object
        """
        # We need to differentiate between different kinds of filers:
        # if the value of the filter is a list, we'll use SQLAlchemy's `in`
        # operator, to check against multiple values. Otherwise, we use a
        # simple keyword filter
        if not filters:
            return query

        for key, value in filters.iteritems():
            if isinstance(value, (list, tuple)):
                column = getattr(model_class, key)
                query = query.filter(column.in_(value))
            else:
                query = query.filter_by(**{key: value})

        return query

    def _get_query(self,
                   model_class,
                   include=None,
                   filters=None,
                   sort=None):
        """Get an SQL query object based on the params passed

        :param model_class: SQL DB table class
        :param include: An optional list of columns to include in the query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :param sort: An optional dictionary where keys are column names to
        sort by, and values are the order (asc/desc)
        :return: A sorted and filtered query with only the relevant
        columns
        """
        query = self._get_base_query(model_class, include)
        query = self._filter_query(query, model_class, filters)
        query = self._sort_query(query, model_class, sort)
        return query

    @_close_session
    def _get_by_id(self,
                   model_class,
                   element_id,
                   include=None,
                   filters=None):
        """Return a single result based on the model class and element ID
        """
        filters = filters or {'id': element_id}
        result = self._get_query(model_class, include, filters).first()

        if not result:
            raise manager_exceptions.NotFoundError(
                'Requested {0} with ID `{1}` was not found'
                .format(model_class.__name__, element_id)
            )
        return result

    @staticmethod
    def _paginate(query, pagination):
        """Paginate the query by size and offset

        :param query: Current SQLAlchemy query object
        :param pagination: An optional dict with size and offset keys
        :return: A tuple with four elements:
        - results: `size` items starting from `offset`
        - the total count of items
        - `size` [default: 0]
        - `offset` [default: 0]
        """
        if pagination:
            size = pagination.get('size', 0)
            offset = pagination.get('offset', 0)
            total = query.order_by(None).count()  # Fastest way to count
            results = query.limit(size).offset(offset).all()
            return results, total, size, offset
        else:
            results = query.all()
            return results, len(results), 0, 0

    @_close_session
    def _list_results(self,
                      model_class,
                      include=None,
                      filters=None,
                      pagination=None,
                      sort=None):
        """Return a (possibly empty) list of `model_class` results
        """
        query = self._get_query(model_class, include, filters, sort)

        results, total, size, offset = self._paginate(query, pagination)
        pagination = {'total': total, 'size': size, 'offset': offset}

        return ListResult(items=results, metadata={'pagination': pagination})

    @staticmethod
    def _get_instance(model_class, model):
        """Return an instance of `model_class` from a model dict/object
        `model` can be of type `model_class`, be a dict, or implement `to_dict`

        :param model_class: SQL DB table class
        :param model: An instance of a class that has a `to_dict` method, and
        whose attributes match the columns of `model_class`
        :return: An instance of `model_class`
        """
        if isinstance(model, model_class):
            return model
        elif isinstance(model, dict):
            return model_class(**model)
        else:
            raise RuntimeError(
                'Attempt to create a {0} instance '
                'from an object of type {1}'.format(
                    model_class.__name__,
                    type(model)
                )
            )

    def _create_model(self, model_class, model):
        """Create a `model_class` instance from a serializable `model` object

        :param model_class: SQL DB table class
        :param model: An instance of a class that has a `to_dict` method, and
        whose attributes match the columns of `model_class`
        :return: An instance of `model_class`
        """
        instance = self._get_instance(model_class, model)
        return self._safe_add(instance)

    def _delete_instance_by_id(self, model_class, element_id, filters=None):
        """Delete a single result based on the model class and element ID
        """
        try:
            instance = self._get_by_id(
                model_class,
                element_id,
                filters=filters
            )
        except manager_exceptions.NotFoundError:
            raise manager_exceptions.NotFoundError(
                'Could not delete {0} with ID `{1}` - element not found'
                .format(
                    model_class.__name__,
                    element_id
                )
            )
        db.session.delete(instance)
        self._safe_commit()
        return instance

    def list_blueprints(self, include=None, filters=None, pagination=None,
                        sort=None):
        return self._list_results(
            Blueprint,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_snapshots(self, include=None, filters=None, pagination=None,
                       sort=None):
        return self._list_results(
            Snapshot,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_deployments(self, include=None, filters=None, pagination=None,
                         sort=None):
        return self._list_results(
            Deployment,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_deployment_updates(self, include=None, filters=None,
                                pagination=None, sort=None):
        return self._list_results(
            DeploymentUpdate,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_executions(self, include=None, filters=None, pagination=None,
                        sort=None):
        return self._list_results(
            Execution,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_node_instances(self, include=None, filters=None, pagination=None,
                            sort=None):
        return self._list_results(
            NodeInstance,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_plugins(self, include=None, filters=None, pagination=None,
                     sort=None):
        return self._list_results(
            Plugin,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_nodes(self, include=None, filters=None, pagination=None,
                   sort=None):
        return self._list_results(
            Node,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_deployment_modifications(self, include=None, filters=None,
                                      pagination=None, sort=None):
        return self._list_results(
            DeploymentModification,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

    def list_blueprint_deployments(self, blueprint_id, include=None):
        # TODO: Should probably be done this way (doesn't work with
        # closed session)
        # blueprint = self._get_by_id(Blueprint, blueprint_id, include)
        # return ListResult(items=blueprint.deployments, metadata={})

        return self.list_deployments(
            include=include,
            filters={'blueprint_id': blueprint_id}
        )

    def get_node_instance(self, node_instance_id, include=None):
        return self._get_by_id(NodeInstance, node_instance_id, include)

    def get_provider_context(self, include=None):
        return self._get_by_id(ProviderContext, PROVIDER_CONTEXT_ID, include)

    def get_deployment_modification(self, modification_id, include=None):
        return self._get_by_id(
            DeploymentModification,
            modification_id,
            include
        )

    def get_node(self, deployment_id, node_id, include=None):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        filters = {'storage_id': storage_node_id}
        return self._get_by_id(Node, storage_node_id, include, filters=filters)

    def get_blueprint(self, blueprint_id, include=None):
        return self._get_by_id(Blueprint, blueprint_id, include)

    def get_snapshot(self, snapshot_id, include=None):
        return self._get_by_id(Snapshot, snapshot_id, include)

    def get_deployment(self, deployment_id, include=None):
        return self._get_by_id(Deployment, deployment_id, include)

    def get_execution(self, execution_id, include=None):
        return self._get_by_id(Execution, execution_id, include)

    def get_plugin(self, plugin_id, include=None):
        return self._get_by_id(Plugin, plugin_id, include)

    def get_deployment_update(self, deployment_update_id, include=None):
        return self._get_by_id(DeploymentUpdate, deployment_update_id, include)

    def put_blueprint(self, blueprint):
        return self._create_model(Blueprint, blueprint)

    def put_snapshot(self, snapshot):
        return self._create_model(Snapshot, snapshot)

    def put_deployment(self, deployment):
        return self._create_model(Deployment, deployment)

    def put_execution(self, execution):
        return self._create_model(Execution, execution)

    def put_plugin(self, plugin):
        return self._create_model(Plugin, plugin)

    def put_node(self, node):
        # Need to add the storage id separately - only used for relations
        node = self._get_instance(Node, node)
        node.storage_id = self._storage_node_id(
            node.deployment_id,
            node.id
        )
        return self._create_model(Node, node)

    def put_node_instance(self, node_instance):
        # Need to add the storage id separately - only used for relations
        node_instance = self._get_instance(NodeInstance, node_instance)
        node_instance.node_storage_id = self._storage_node_id(
            node_instance.deployment_id,
            node_instance.node_id
        )
        return self._create_model(NodeInstance, node_instance)

    def put_deployment_update(self, deployment_update):
        deployment_update.id = deployment_update.id or '{0}-{1}'.format(
            deployment_update.deployment_id,
            uuid.uuid4()
        )
        return self._create_model(DeploymentUpdate, deployment_update)

    def put_deployment_update_step(self, deployment_update_id, step):
        deployment_update = self._get_by_id(
            DeploymentUpdate,
            deployment_update_id
        )

        deployment_update.steps += [DeploymentUpdateStep(**step.to_dict())]
        return self._safe_add(deployment_update)

    def put_provider_context(self, provider_context):
        # The ID is always the same, and only the name changes
        instance = self._get_instance(ProviderContext, provider_context)
        instance.id = PROVIDER_CONTEXT_ID
        return self._safe_add(instance)

    def put_deployment_modification(self, modification):
        return self._create_model(DeploymentModification, modification)

    def delete_blueprint(self, blueprint_id):
        return self._delete_instance_by_id(Blueprint, blueprint_id)

    def delete_plugin(self, plugin_id):
        return self._delete_instance_by_id(Plugin, plugin_id)

    def delete_snapshot(self, snapshot_id):
        return self._delete_instance_by_id(Snapshot, snapshot_id)

    def delete_deployment(self, deployment_id):
        # Previously deleted all relations manually - now will be handled
        # by SQL with cascade
        return self._delete_instance_by_id(Deployment, deployment_id)

    def delete_node(self, deployment_id, node_id):
        storage_node_id = self._storage_node_id(deployment_id, node_id)
        return self._delete_instance_by_id(
            Node,
            node_id,
            filters={'storage_id': storage_node_id}
        )

    def delete_node_instance(self, node_instance_id):
        return self._delete_instance_by_id(NodeInstance, node_instance_id)

    def update_entity(self, entity):
        return self._safe_add(entity)

    def update_execution_status(self, execution_id, status, error):
        execution = self.get_execution(execution_id)
        execution.status = status
        execution.error = error
        return self._safe_add(execution)

    def update_provider_context(self, provider_context):
        provider_context_instance = self.get_provider_context()
        provider_context_instance.name = provider_context.name
        provider_context_instance.context = provider_context.context
        return self._safe_add(provider_context_instance)

    def update_node_instance(self, node_instance):
        with _lock_table(NodeInstance):
            current = self.get_node_instance(node_instance.id)
            if current.version != node_instance.version:
                raise manager_exceptions.ConflictError(
                    'Node instance update conflict for node instance {0} '
                    '[current_version={1}, updated_version={2}]'.format(
                            current.id, current.version, node_instance.version)
                )

            node_instance.version += 1
            return self._safe_add(node_instance)

    @staticmethod
    def _storage_node_id(deployment_id, node_id):
        return '{0}_{1}'.format(deployment_id, node_id)


def get_storage_manager():
    """Get the current Flask app's storage manager, create if necessary
    """
    manager = current_app.config.get('storage_manager')
    if not manager:
        current_app.config['storage_manager'] = SQLStorageManager()
        manager = current_app.config.get('storage_manager')
    return manager


class ListResult(object):
    """
    a ListResult contains results about the requested items.
    """
    def __init__(self, items, metadata):
        self.items = items
        self.metadata = metadata
