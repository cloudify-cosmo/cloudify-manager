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

from collections import OrderedDict

from flask import current_app
from flask_security import current_user

from manager_rest import manager_exceptions
from manager_rest.storage.models_base import db

from sqlalchemy.sql.elements import Label
from sqlite3 import DatabaseError as SQLiteDBError
from sqlalchemy.exc import SQLAlchemyError

try:
    from psycopg2 import DatabaseError as Psycopg2DBError
    sql_errors = (SQLAlchemyError, SQLiteDBError, Psycopg2DBError)
except ImportError:
    sql_errors = (SQLAlchemyError, SQLiteDBError)
    Psycopg2DBError = None


class SQLStorageManager(object):
    @staticmethod
    def _safe_commit():
        """Try to commit changes in the session. Roll back if exception raised
        Excepts SQLAlchemy errors and rollbacks if they're caught
        """
        try:
            db.session.commit()
        except sql_errors as e:
            db.session.rollback()
            raise manager_exceptions.SQLStorageException(
                'SQL Storage error: {0}'.format(str(e))
            )

    @staticmethod
    def _get_base_query(model_class, include, joins):
        """Create the initial query from the model class and included columns

        :param model_class: SQL DB table class
        :param include: A (possibly empty) list of columns to include in
        the query
        :param joins: A (possibly empty) list of models on which the query
        should join
        :return: An SQLAlchemy AppenderQuery object
        """

        # If only some columns are included, query through the session object
        if include:
            query = db.session.query(*include)
        else:
            # If all columns should be returned, query directly from the model
            query = model_class.query

        # Add any joins that might be necessary
        for join_model in joins:
            query = query.join(join_model)

        return query

    @staticmethod
    def _sort_query(query, sort=None):
        """Add sorting clauses to the query

        :param query: Base SQL query
        :param sort: An optional dictionary where keys are column names to
        sort by, and values are the order (asc/desc)
        :return: An SQLAlchemy AppenderQuery object
        """
        if sort:
            for column, order in sort.iteritems():
                if order == 'desc':
                    column = column.desc()
                query = query.order_by(column)
        return query

    @staticmethod
    def _filter_query(query, filters):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :return: An SQLAlchemy AppenderQuery object
        """
        for column, value in filters.iteritems():
            # If there are multiple values, use `in_`, otherwise, use `eq`
            if isinstance(value, (list, tuple)):
                query = query.filter(column.in_(value))
            else:
                query = query.filter(column == value)

        return query

    @staticmethod
    def _filter_by_tenant(query, model_class):
        """
        Filter by the tenant ID associated with `model_class` (either
        directly via a relationship with the tenants table, or via an
        ancestor who has such a relationship)
        """
        # System administrators should see all resources, regardless of tenant.
        # Queries of elements that aren't resources (tenants, users, etc.),
        # or resources that are independent of tenants (e.g. provider context)
        # shouldn't be filtered as well
        if current_user.is_sys_admin() or \
                not model_class.is_resource or \
                ('tenant_id' not in model_class.join_properties and
                 not hasattr(model_class, 'tenant_id')):
            return query

        # Other users should only see resources for which they were granted
        # privileges via association with a tenant
        tenant_ids = [tenant.id for tenant in current_user.get_all_tenants()]
        current_app.logger.debug('Filtering tenants for {0}'
                                 ''.format(model_class))

        if 'tenant_id' in model_class.join_properties:
            tenant_column = model_class.join_properties['tenant_id']['column']
        else:
            tenant_column = model_class.tenant_id

        # Filter by the `tenant_id` column
        query = query.filter(tenant_column.in_(tenant_ids))
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

        include = include or []
        filters = filters or dict()
        sort = sort or OrderedDict()

        joins = self._get_join_models_list(model_class, include, filters, sort)
        include, filters, sort = self._get_columns_from_field_names(
            model_class, include, filters, sort
        )

        query = self._get_base_query(model_class, include, joins)
        query = self._filter_by_tenant(query, model_class)
        query = self._filter_query(query, filters)
        query = self._sort_query(query, sort)
        return query

    def _get_columns_from_field_names(self,
                                      model_class,
                                      include,
                                      filters,
                                      sort):
        """Go over the optional parameters (include, filters, sort), and
        replace column names with actual SQLA column objects
        """
        all_includes = [self._get_column(model_class, c) for c in include]
        include = []
        # Columns that are inferred from properties (Labels) should be included
        # last for the following joins to work properly
        for col in all_includes:
            if isinstance(col, Label):
                include.append(col)
            else:
                include.insert(0, col)

        filters = {self._get_column(model_class, c): filters[c]
                   for c in filters}
        sort = OrderedDict((self._get_column(model_class, c), sort[c])
                           for c in sort)

        return include, filters, sort

    def _get_join_models_list(self, model_class, include, filters, sort):
        """Return a list of models on which the query should be joined, as
        inferred from the include, filter and sort column names
        """
        if not model_class.is_resource:
            return []

        all_column_names = include + filters.keys() + sort.keys()
        join_columns = {column_name for column_name in all_column_names
                        if self._is_join_column(model_class, column_name)}

        # If the only columns included are the columns on which we would
        # normally join, there isn't actually a need to join, as the FROM
        # clause in the query will be generated from the relevant models anyway
        if include == list(join_columns):
            return []

        # Initializing a set, because the same model can appear in several
        # join lists
        join_models = set()
        for column_name in join_columns:
            join_models.update(
                model_class.join_properties[column_name]['models']
            )
        # Sort the models by their correct join order
        join_models = sorted(join_models,
                             key=lambda model: model.join_order, reverse=True)

        return join_models

    @staticmethod
    def _is_join_column(model_class, column_name):
        """Return False if the column name corresponds to a regular SQLA
        column that `model_class` has.
        Return True if the column that should be used is a join column (see
        SQLModelBase for an explanation)
        """
        return model_class.is_resource and \
            column_name in model_class.join_properties

    def _get_column(self, model_class, column_name):
        """Return the column on which an action (filtering, sorting, etc.)
        would need to be performed. Can be either an attribute of the class,
        or needs to be inferred from the class' `join_properties` property
        """
        if self._is_join_column(model_class, column_name):
            return model_class.join_properties[column_name]['column']
        else:
            return getattr(model_class, column_name)

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

    def _validate_unique_resource_id_per_tenant(self, model_class, instance):
        """Assert that only a single resource exists with a given id in a
        given tenant
        """
        # Only relevant for resources that have unique IDs and are connected
        # to a tenant
        if not model_class.is_resource or \
                not hasattr(model_class, 'tenant') or \
                not model_class.is_id_unique:
            return

        tenant_id = _get_current_tenant_id()
        filters = {'id': instance.id, 'tenant_id': tenant_id}

        # There should be only one instance with this id on this tenant
        if len(self.list(model_class, filters=filters)) != 1:
            # Delete the newly added instance, and raise an error
            db.session.delete(instance)
            self._safe_commit()

            raise manager_exceptions.ConflictError(
                '{0} with ID `{1}` already exists on tenant `{2}`'.format(
                    instance.__class__.__name__,
                    instance.id,
                    tenant_id
                )
            )

    @staticmethod
    def _load_properties(instance):
        """A helper method used to overcome a problem where the properties
        that rely on joins aren't being loaded automatically
        """
        if instance.is_resource:
            for prop in instance.join_properties:
                if prop == 'tenant_id':
                    continue
                getattr(instance, prop)

    def get(self,
            model_class,
            element_id,
            include=None,
            filters=None,
            locking=False):
        """Return a single result based on the model class and element ID
        """
        filters = filters or {'id': element_id}
        query = self._get_query(model_class, include, filters)
        if locking:
            query = query.with_for_update()
        result = query.first()

        if not result:
            raise manager_exceptions.NotFoundError(
                'Requested {0} with ID `{1}` was not found'
                .format(model_class.__name__, element_id)
            )
        return result

    def list(self,
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

    def put(self, model_class, instance):
        """Create a `model_class` instance from a serializable `model` object

        :param model_class: SQL DB table class
        :param instance: A dict with relevant kwargs, or an instance of a class
        that has a `to_dict` method, and whose attributes match the columns
        of `model_class` (might also my just an instance of `model_class`)
        :return: An instance of `model_class`
        """
        if hasattr(instance, 'tenant_id'):
            instance.tenant_id = _get_current_tenant_id()
        self.update(instance)

        self._validate_unique_resource_id_per_tenant(model_class, instance)
        return instance

    def delete(self, model_class, element_id, filters=None):
        """Delete a single result based on the model class and element ID
        """
        try:
            instance = self.get(
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
        self._load_properties(instance)
        db.session.delete(instance)
        self._safe_commit()
        return instance

    def update(self, instance):
        """Add `instance` to the DB session, and attempt to commit

        :param instance: Instance to be updated in the DB
        :return: The updated instance
        """
        db.session.add(instance)
        self._safe_commit()
        return instance

    def refresh(self, instance):
        """Reload the instance with fresh information from the DB

        :param instance: Instance to be re-loaded from the DB
        :return: The refreshed instance
        """
        db.session.refresh(instance)
        self._load_properties(instance)
        return instance


def get_storage_manager():
    """Get the current Flask app's storage manager, create if necessary
    """
    manager = current_app.config.get('storage_manager')
    if not manager:
        current_app.config['storage_manager'] = SQLStorageManager()
        manager = current_app.config.get('storage_manager')
    return manager


def _get_current_tenant_id():
    return current_app.config.get('tenant_id')


class ListResult(object):
    """
    a ListResult contains results about the requested items.
    """
    def __init__(self, items, metadata):
        self.items = items
        self.metadata = metadata

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, item):
        return self.items[item]
