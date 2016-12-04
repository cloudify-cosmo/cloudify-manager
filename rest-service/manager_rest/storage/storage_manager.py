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

from manager_rest import manager_exceptions, config
from manager_rest.storage.models_base import db
from manager_rest.constants import CURRENT_TENANT_CONFIG

from sqlalchemy import or_ as sql_or
from sqlalchemy.exc import SQLAlchemyError
from sqlite3 import DatabaseError as SQLiteDBError

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

    def _get_base_query(self, model_class, include, joins):
        """Create the initial query from the model class and included columns

        :param model_class: SQL DB table class
        :param include: A (possibly empty) list of columns to include in
        the query
        :return: An SQLAlchemy AppenderQuery object
        """
        # If only some columns are included, query through the session object
        if include:
            # Make sure that attributes come before association proxies
            include.sort(key=lambda x: x.is_clause_element)
            query = db.session.query(*include)
        else:
            # If all columns should be returned, query directly from the model
            query = model_class.query

        if not self._skip_joining(joins, include):
            for join_table in joins:
                query = query.join(join_table)

        return query

    @staticmethod
    def _skip_joining(joins, include):
        """Dealing with an edge case where the only included column comes from
        an other table. In this case, we mustn't join on the same table again

        :param joins: A list of tables on which we're trying to join
        :param include: The list of
        :return: True if we need to skip joining
        """
        if not joins:
            return True
        join_table_names = [t.__tablename__ for t in joins]

        if len(include) != 1:
            return False

        column = include[0]
        if column.is_clause_element:
            table_name = column.element.table.name
        else:
            table_name = column.class_.__tablename__
        return table_name in join_table_names

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

    def _filter_query(self, query, model_class, filters):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :return: An SQLAlchemy AppenderQuery object
        """
        query = self._add_tenant_filter(query, model_class)
        query = self._add_permissions_filter(query, model_class)
        query = self._add_value_filter(query, filters)
        return query

    @staticmethod
    def _add_value_filter(query, filters):
        for column, value in filters.iteritems():
            if isinstance(value, (list, tuple)):
                query = query.filter(column.in_(value))
            else:
                query = query.filter(column == value)

        return query

    @staticmethod
    def _add_tenant_filter(query, model_class):
        """Filter by the tenant ID associated with `model_class` (either
        directly via a relationship with the tenants table, or via an
        ancestor who has such a relationship)
        """
        # System administrators should see all resources, regardless of tenant.
        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered as well
        if current_user.is_admin or not model_class.is_resource:
            return query

        # Other users should only see resources for which they were granted
        # privileges via association with a tenant
        tenant_ids = [tenant.id for tenant in current_user.get_all_tenants()]

        # Filter by the `tenant_id` column
        clauses = [model_class.tenant_id == t_id for t_id in tenant_ids]
        return query.filter(sql_or(*clauses))

    @staticmethod
    def _add_permissions_filter(query, model_class):
        """Filter by the users present in either the `viewers` or `owners`
        lists
        """
        # System administrators should see all resources, regardless of tenant.
        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered as well
        if current_user.is_admin or not model_class.is_resource:
            return query

        # Only get resources where the current user appears in `viewers` or
        # `owners` *or* where the `viewers` list is empty (meaning that this
        # resource is public) *or* where the current user is the creator
        user_filter = sql_or(
            sql_or(
                model_class.viewers.any(id=current_user.id),
                model_class.owners.any(id=current_user.id)
            ),
            # ~ means `not` - i.e. all resources that don't have any viewers
            ~model_class.viewers.any(),
            model_class.creator == current_user
        )
        return query.filter(user_filter)

    @staticmethod
    def _get_joins(model_class, columns):
        """Get a list of all the tables on which we need to join

        :param columns: A set of all columns involved in the query
        """
        joins = []  # Using a list instead of a set because order is important
        for column_name in columns:
            column = getattr(model_class, column_name)
            while not column.is_attribute:
                column = column.remote_attr
                if column.is_attribute:
                    join_class = column.class_
                else:
                    join_class = column.local_attr.class_

                # Don't add the same class more than once
                if join_class not in joins:
                    joins.append(join_class)
        return joins

    def _get_joins_and_converted_columns(self,
                                         model_class,
                                         include,
                                         filters,
                                         sort):
        """Get a list of tables on which we need to join and the converted
        `include`, `filters` and `sort` arguments (converted to actual SQLA
        column/label objects instead of column names)
        """
        include = include or []
        filters = filters or dict()
        sort = sort or OrderedDict()

        all_columns = set(include) | set(filters.keys()) | set(sort.keys())
        joins = self._get_joins(model_class, all_columns)

        include, filters, sort = self._get_columns_from_field_names(
            model_class, include, filters, sort
        )
        return include, filters, sort, joins

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

        include, filters, sort, joins = self._get_joins_and_converted_columns(
            model_class, include, filters, sort
        )

        query = self._get_base_query(model_class, include, joins)
        query = self._filter_query(query, model_class, filters)
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
        include = [self._get_column(model_class, c) for c in include]
        filters = {self._get_column(model_class, c): filters[c]
                   for c in filters}
        sort = OrderedDict((self._get_column(model_class, c), sort[c])
                           for c in sort)

        return include, filters, sort

    @staticmethod
    def _get_column(model_class, column_name):
        """Return the column on which an action (filtering, sorting, etc.)
        would need to be performed. Can be either an attribute of the class,
        or an association proxy linked to a relationship the class has
        """
        column = getattr(model_class, column_name)
        if column.is_attribute:
            return column
        else:
            # We need to get to the underlying attribute, so we move on to the
            # next remote_attr until we reach one
            while not column.remote_attr.is_attribute:
                column = column.remote_attr
            # Put a label on the remote attribute with the name of the column
            return column.remote_attr.label(column_name)

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
            SQLStorageManager._validate_pagination(size)
            offset = pagination.get('offset', 0)
            total = query.order_by(None).count()  # Fastest way to count
            results = query.limit(size).offset(offset).all()
            return results, total, size, offset
        else:
            total = query.order_by(None).count()
            SQLStorageManager._validate_returned_size(total)
            results = query.all()
            return results, len(results), 0, 0

    @staticmethod
    def _validate_pagination(pagination_size):
        if pagination_size < 0:
            raise manager_exceptions.IllegalActionError(
                'Invalid pagination size: {0}.'.format(
                    pagination_size
                )
            )

        if pagination_size > config.instance.max_results:
            raise manager_exceptions.IllegalActionError(
                'Invalid pagination size: {0}. Max allowed: {1}'.format(
                    pagination_size,
                    config.instance.max_results
                )
            )

    @staticmethod
    def _validate_returned_size(size):
        if size > config.instance.max_results:
            raise manager_exceptions.IllegalActionError(
                'Response size ({0}) bigger than max allowed ({1}), '
                'please use pagination.'.format(
                    size,
                    config.instance.max_results
                )
            )

    def _validate_unique_resource_id_per_tenant(self, instance):
        """Assert that only a single resource exists with a given id in a
        given tenant
        """
        # Only relevant for resources that have unique IDs and are connected
        # to a tenant
        if not instance.is_resource or not instance.is_id_unique:
            return

        filters = {'id': instance.id, 'tenant_id': self.current_tenant.id}

        # There should be only one instance with this id on this tenant
        if len(self.list(instance.__class__, filters=filters)) != 1:
            # Delete the newly added instance, and raise an error
            db.session.delete(instance)
            self._safe_commit()

            raise manager_exceptions.ConflictError(
                '{0} already exists on {1}'.format(
                    instance,
                    self.current_tenant
                )
            )

    def _associate_users_and_tenants(self, instance, private_resource):
        """Associate, if necessary, the instance with the current tenant/user
        """
        if instance.top_level_tenant:
            instance.tenant = self.current_tenant
        if instance.top_level_creator:
            instance.creator = current_user

            # If it's a private resource, the creator is the only viewer/owner
            if private_resource:
                instance.owners = [current_user]
                instance.viewers = [current_user]

    @staticmethod
    def _load_relationships(instance):
        """A helper method used to overcome a problem where the relationships
        that rely on joins aren't being loaded automatically
        """
        if instance.is_resource:
            for rel in instance.__mapper__.relationships:
                getattr(instance, rel.key)

    @property
    def current_tenant(self):
        """Return the tenant with which the user accessed the app
        """
        return current_app.config[CURRENT_TENANT_CONFIG]

    def get(self,
            model_class,
            element_id,
            include=None,
            filters=None,
            locking=False):
        """Return a single result based on the model class and element ID
        """
        current_app.logger.debug(
            'Get `{0}` with ID `{1}`'.format(model_class.__name__, element_id)
        )
        filters = filters or {'id': element_id}
        query = self._get_query(model_class, include, filters)
        if locking:
            query = query.with_for_update()
        result = query.first()

        if not result:
            raise manager_exceptions.NotFoundError(
                'Requested `{0}` with ID `{1}` was not found'
                .format(model_class.__name__, element_id)
            )
        current_app.logger.debug('Returning {0}'.format(result))
        return result

    def list(self,
             model_class,
             include=None,
             filters=None,
             pagination=None,
             sort=None):
        """Return a (possibly empty) list of `model_class` results
        """
        if filters:
            msg = 'List `{0}` with filter {1}'.format(model_class.__name__,
                                                      filters)
        else:
            msg = 'List `{0}`'.format(model_class.__name__)
        current_app.logger.debug(msg)
        query = self._get_query(model_class, include, filters, sort)

        results, total, size, offset = self._paginate(query, pagination)
        pagination = {'total': total, 'size': size, 'offset': offset}

        current_app.logger.debug('Returning: {0}'.format(results))
        return ListResult(items=results, metadata={'pagination': pagination})

    def put(self, instance, private_resource=False):
        """Create a `model_class` instance from a serializable `model` object

        :param instance: An instance of the SQLModelBase class (or some class
        derived from it)
        :param private_resource: If set to True, the resource's `viewers` list
        will be populated by the creating user only
        :return: The same instance, with the tenant set, if necessary
        """
        self._associate_users_and_tenants(instance, private_resource)
        current_app.logger.debug('Put {0}'.format(instance))
        self.update(instance, log=False)

        self._validate_unique_resource_id_per_tenant(instance)
        return instance

    def delete(self, instance):
        """Delete the passed instance
        """
        current_app.logger.debug('Delete {0}'.format(instance))
        self._load_relationships(instance)
        db.session.delete(instance)
        self._safe_commit()
        return instance

    def update(self, instance, log=True):
        """Add `instance` to the DB session, and attempt to commit

        :param instance: Instance to be updated in the DB
        :param log: Should the update message be logged
        :return: The updated instance
        """
        if log:
            current_app.logger.debug('Update {0}'.format(instance))
        db.session.add(instance)
        self._safe_commit()
        return instance

    def refresh(self, instance):
        """Reload the instance with fresh information from the DB

        :param instance: Instance to be re-loaded from the DB
        :return: The refreshed instance
        """
        current_app.logger.debug('Refresh {0}'.format(instance))
        db.session.refresh(instance)
        self._load_relationships(instance)
        return instance


def get_storage_manager():
    """Get the current Flask app's storage manager, create if necessary
    """
    return current_app.config.setdefault('storage_manager',
                                         SQLStorageManager())


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
