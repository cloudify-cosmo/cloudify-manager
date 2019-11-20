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

import psutil
from collections import OrderedDict
from flask_security import current_user
from sqlalchemy import or_ as sql_or, func
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app, has_request_context
from sqlite3 import DatabaseError as SQLiteDBError
from sqlalchemy.orm.attributes import flag_modified

from cloudify.models_states import VisibilityState

from manager_rest.storage.models_base import db
from manager_rest import manager_exceptions, config, utils
from manager_rest.utils import (is_administrator,
                                all_tenants_authorization,
                                validate_global_modification)

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

        query = query.outerjoin(*joins)
        return query

    @staticmethod
    def _sort_query(query, model_class, sort=None):
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
        else:
            default_sort = model_class.default_sort_column()
            if default_sort:
                query = query.order_by(default_sort)
        return query

    def _filter_query(self,
                      query,
                      model_class,
                      filters,
                      substr_filters,
                      all_tenants):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values). Each value can also be a callable which returns
        a SQLAlchemy filter
        :return: An SQLAlchemy AppenderQuery object
        """
        query = self._add_tenant_filter(query, model_class, all_tenants)
        query = self._add_permissions_filter(query, model_class)
        query = self._add_value_filter(query, filters)
        query = self._add_substr_filter(query, substr_filters)
        return query

    def _add_value_filter(self, query, filters):
        for column, value in filters.iteritems():
            column, value = self._update_case_insensitive(column, value)
            if callable(value):
                query = query.filter(value(column))
            elif isinstance(value, (list, tuple)):
                query = query.filter(column.in_(value))
            else:
                query = query.filter(column == value)
        return query

    def _add_substr_filter(self, query, filters):
        for column, value in filters.iteritems():
            column, value = self._update_case_insensitive(column, value, True)
            if isinstance(value, basestring):
                query = query.filter(column.contains(value))
            else:
                raise manager_exceptions.BadParametersError(
                    'Substring filtering is only supported for strings'
                )
        return query

    @staticmethod
    def _update_case_insensitive(column, value, force=False):
        """Check if the column in question should be case insensitive, and
        if so, make sure the column (and the value) will be converted to lower
        case

        :return: The updated column and value in a (c, v) tuple
        """
        is_case_insensitive = getattr(column, 'is_ci', False) or force
        if not is_case_insensitive:
            return column, value

        # Adding a label to preserve the column name
        column = func.lower(column).label(column.key)
        try:
            if isinstance(value, (list, tuple)):
                value = [v.lower() for v in value]
            else:
                value = value.lower()
        except AttributeError:
            raise manager_exceptions.BadParametersError(
                'Incorrect param passed to column `{0}`: {1}. '
                'Param type should be string'.format(
                    column.name, value
                )
            )

        return column, value

    def _add_tenant_filter(self, query, model_class, all_tenants):
        """Filter by the tenant ID associated with `model_class` (either
        directly via a relationship with the tenants table, or via an
        ancestor who has such a relationship)
        """
        # Users/Groups etc. don't have tenants
        if not model_class.is_resource:
            return query

        # not used from a request handler - no relevant user
        if not has_request_context():
            return query

        current_tenant = self.current_tenant

        # If a user passed the `all_tenants` flag
        if all_tenants:
            # If a user that is allowed to get all the tenants in the system
            # no need to filter
            if all_tenants_authorization():
                return query
            # Filter by all the tenants the user is allowed to list in
            tenant_ids = [
                tenant.id for tenant in current_user.all_tenants
                if utils.tenant_specific_authorization(tenant,
                                                       model_class.__name__)
                ]
        else:
            # Specific tenant only
            tenant_ids = [current_tenant.id] if current_tenant else []

        # Match any of the applicable tenant ids or if it's a global resource
        tenant_filter = sql_or(
            model_class.visibility == VisibilityState.GLOBAL,
            model_class._tenant_id.in_(tenant_ids)
        )
        return query.filter(tenant_filter)

    def _add_permissions_filter(self, query, model_class):
        """Filter by the users present in either the `viewers` or `owners`
        lists
        """
        # not used from a request handler - no relevant user
        if not has_request_context():
            return query

        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered
        if not model_class.is_resource:
            return query

        # For users that are allowed to see all resources, regardless of tenant
        is_admin = is_administrator(self.current_tenant)
        if is_admin:
            return query

        # Only get resources that are public - not private (note that ~ stands
        # for NOT, in SQLA), *or* those where the current user is the creator
        user_filter = sql_or(
            model_class.visibility != VisibilityState.PRIVATE,
            model_class.creator == current_user
        )
        return query.filter(user_filter)

    @staticmethod
    def _get_joins(model_class, columns):
        """Get a list of all the attributes on which we need to join

        :param columns: A set of all columns involved in the query
        """
        # Using an ordered dict because the order of the joins is important
        joins = OrderedDict()
        for column_name in columns:
            column = getattr(model_class, column_name)
            while not column.is_attribute:
                join_attr = column.local_attr

                # This is a hack, to deal with the fact that SQLA doesn't
                # fully support doing something like: `if join_attr in joins`,
                # because some SQLA elements have their own comparators
                join_attr_name = str(join_attr)
                if join_attr_name not in joins:
                    joins[join_attr_name] = join_attr
                column = column.remote_attr
        return joins.values()

    def _get_joins_and_converted_columns(self,
                                         model_class,
                                         include,
                                         filters,
                                         substr_filters,
                                         sort):
        """Get a list of tables on which we need to join and the converted
        `include`, `filters` and `sort` arguments (converted to actual SQLA
        column/label objects instead of column names)
        """
        include = include or []
        filters = filters or dict()
        substr_filters = substr_filters or dict()
        sort = sort or OrderedDict()

        all_columns = set(include) | set(filters.keys()) | set(sort.keys())
        joins = self._get_joins(model_class, all_columns)

        include, filters, substr_filters, sort = \
            self._get_columns_from_field_names(model_class,
                                               include,
                                               filters,
                                               substr_filters,
                                               sort)
        return include, filters, substr_filters, sort, joins

    def _get_query(self,
                   model_class,
                   include=None,
                   filters=None,
                   substr_filters=None,
                   sort=None,
                   all_tenants=None):
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
        include, filters, substr_filters, sort, joins = \
            self._get_joins_and_converted_columns(model_class,
                                                  include,
                                                  filters,
                                                  substr_filters,
                                                  sort)

        query = self._get_base_query(model_class, include, joins)
        query = self._filter_query(query,
                                   model_class,
                                   filters,
                                   substr_filters,
                                   all_tenants)
        query = self._sort_query(query, model_class, sort)
        return query

    def _get_columns_from_field_names(self,
                                      model_class,
                                      include,
                                      filters,
                                      substr_filters,
                                      sort):
        """Go over the optional parameters (include, filters, sort), and
        replace column names with actual SQLA column objects
        """
        include = [self._get_column(model_class, c) for c in include]
        filters = {self._get_column(model_class, c): filters[c]
                   for c in filters}
        substr_filters = {self._get_column(model_class, c): substr_filters[c]
                          for c in substr_filters}
        sort = OrderedDict((self._get_column(model_class, c), sort[c])
                           for c in sort)

        return include, filters, substr_filters, sort

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
    def _paginate(query, pagination, get_all_results=False):
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
            size = pagination.get('size', config.instance.default_page_size)
            SQLStorageManager._validate_pagination(size)
            offset = pagination.get('offset', 0)
        else:
            size = config.instance.default_page_size
            offset = 0

        total = query.order_by(None).count()  # Fastest way to count
        results = query.limit(size).offset(offset).all()
        return results, total, size, offset

    @staticmethod
    def _validate_pagination(pagination_size):
        if pagination_size < 0:
            raise manager_exceptions.IllegalActionError(
                'Invalid pagination size: {0}.'.format(
                    pagination_size
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

        query = self._get_unique_resource_id_query(instance.__class__,
                                                   instance.id,
                                                   instance.tenant)
        results = query.all()

        # There should be only one instance with this id on this tenant or
        # in another tenant if the resource is global
        if len(results) != 1:
            # Delete the newly added instance, and raise an error
            db.session.delete(instance)
            self._safe_commit()

            raise manager_exceptions.ConflictError(
                '{0} already exists on {1} or with global visibility'.format(
                    instance,
                    self.current_tenant
                )
            )

    def _get_unique_resource_id_query(self, model_class, resource_id,
                                      tenant):
        """
        Query for all the resources with the same id of the given instance,
        if it's in the given tenant, or if it's a global resource
        """
        query = model_class.query
        query = query.filter(model_class.id == resource_id)
        unique_resource_filter = sql_or(
            model_class.tenant == tenant,
            model_class.visibility == VisibilityState.GLOBAL
        )
        query = query.filter(unique_resource_filter)
        return query

    def _associate_users_and_tenants(self, instance):
        """Associate, if necessary, the instance with the current tenant/user
        """
        if instance.is_resource:
            if not instance.tenant:
                instance.tenant = self.current_tenant
            if not instance.creator:
                instance.creator = current_user

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
        try:
            return utils.current_tenant._get_current_object()
        except manager_exceptions.TenantNotProvided:
            return None

    def get(self,
            model_class,
            element_id,
            include=None,
            filters=None,
            locking=False,
            all_tenants=None):
        """Return a single result based on the model class and element ID
        """
        current_app.logger.debug(
            'Get `{0}` with ID `{1}`'.format(model_class.__name__, element_id)
        )
        filters = filters or {'id': element_id}
        query = self._get_query(model_class, include, filters,
                                all_tenants=all_tenants)
        if locking:
            query = query.with_for_update()
        result = query.first()

        if not result:
            if filters and set(filters.keys()) != {'id'}:
                filters_message = ' (filters: {0})'.format(filters)
            else:
                filters_message = ''
            raise manager_exceptions.NotFoundError(
                'Requested `{0}` with ID `{1}` was not found{2}'
                .format(model_class.__name__, element_id, filters_message)
            )
        current_app.logger.debug('Returning {0}'.format(result))
        return result

    @staticmethod
    def _validate_available_memory():
        """Validate minimal available memory in manager
        """
        min_available_memory_mb = config.instance.min_available_memory_mb
        if min_available_memory_mb == 0:
            return
        memory_status = psutil.virtual_memory()
        available_mb = memory_status.available / 1024 / 1024
        if available_mb < min_available_memory_mb:
            raise manager_exceptions.InsufficientMemoryError(
                'Insufficient memory in manager, '
                'needed: {0}mb, available: {1}mb'
                ''.format(min_available_memory_mb, available_mb))

    def list(self,
             model_class,
             include=None,
             filters=None,
             pagination=None,
             sort=None,
             all_tenants=None,
             substr_filters=None,
             get_all_results=False):
        """Return a list of `model_class` results

        :param model_class: SQL DB table class
        :param include: An optional list of columns to include in the query
        :param filters: An optional dictionary where keys are column names to
                        filter by, and values are values applicable for those
                        columns (or lists of such values)
        :param pagination: An optional dict with size and offset keys
        :param sort: An optional dictionary where keys are column names to
                     sort by, and values are the order (asc/desc)
        :param all_tenants: Include resources from all tenants associated
                            with the user
        :param substr_filters: An optional dictionary similar to filters,
                               when the results are filtered by substrings
        :param get_all_results: Get all the results without the limitation of
                                size or pagination. Use it carefully to
                                prevent consumption of too much memory
        :return: A (possibly empty) list of `model_class` results
        """
        self._validate_available_memory()

        if filters:
            msg = 'List `{0}` with filter {1}'.format(model_class.__name__,
                                                      filters)
        else:
            msg = 'List `{0}`'.format(model_class.__name__)

        current_app.logger.debug(msg)
        query = self._get_query(model_class,
                                include,
                                filters,
                                substr_filters,
                                sort,
                                all_tenants)

        results, total, size, offset = self._paginate(query,
                                                      pagination,
                                                      get_all_results)
        pagination = {'total': total, 'size': size, 'offset': offset}

        current_app.logger.debug('Returning: {0}'.format(results))
        return ListResult(items=results, metadata={'pagination': pagination})

    def summarize(self, target_field, sub_field, model_class,
                  pagination, get_all_results, all_tenants, filters):
        f = self._get_column(model_class, target_field)
        fields = [f]
        string_fields = [target_field]
        if sub_field:
            fields.append(self._get_column(model_class, sub_field))
            string_fields.append(sub_field)
        entities = fields + [db.func.count('*')]
        query = self._get_query(
            model_class,
            all_tenants=all_tenants,
            filters=filters,
            sort={target_field: f.desc()},
            include=string_fields,
        ).with_entities(*entities).group_by(*fields)

        results, total, size, offset = self._paginate(query,
                                                      pagination,
                                                      get_all_results)
        pagination = {'total': total, 'size': size, 'offset': offset}

        return ListResult(items=results, metadata={'pagination': pagination})

    def count(self, model_class, filters=None, distinct_by=None):
        query = model_class.query
        if filters:
            query = self._add_value_filter(query, filters)
        if distinct_by:
            query = query.filter(distinct_by != "").distinct(distinct_by)
            count = query.order_by(None).count()
        else:
            count = query.order_by(None).count()   # Fastest way to count
        return count

    def exists(self, model_class, element_id=None, filters=None,
               all_tenants=None):
        """Check if a record exists
        """
        filters = filters or {'id': element_id}
        query = self._get_query(model_class,
                                filters=filters,
                                all_tenants=all_tenants)
        return True if query.first() else False

    def full_access_list(self, model_class, filters=None):
        """Return a list of `model_class` results, without considering the
           user or the tenant

        :param model_class: SQL DB table class
        :param filters: An optional dictionary where keys are column names to
                        filter by, and values are values applicable for those
                        columns (or lists of such values)
        :return: A (possibly empty) list of `model_class` results
        """
        query = model_class.query
        if filters:
            query = self._add_value_filter(query, filters)
        return query.all()

    def put(self, instance):
        """Create a `model_class` instance from a serializable `model` object

        :param instance: An instance of the SQLModelBase class (or some class
        derived from it)
        :return: The same instance, with the tenant set, if necessary
        """
        self._associate_users_and_tenants(instance)
        current_app.logger.debug('Put {0}'.format(instance))
        self.update(instance, log=False)

        self._validate_unique_resource_id_per_tenant(instance)
        return instance

    def delete(self, instance, validate_global=False):
        """Delete the passed instance
        """
        if instance.is_resource and validate_global:
            validate_global_modification(instance)
        current_app.logger.debug('Delete {0}'.format(instance))
        self._load_relationships(instance)
        db.session.delete(instance)
        self._safe_commit()
        return instance

    def update(self, instance, log=True, modified_attrs=(),
               validate_global=False):
        """Add `instance` to the DB session, and attempt to commit

        :param instance: Instance to be updated in the DB
        :param log: Should the update message be logged
        :param modified_attrs: Names of attributes that have been modified.
                               This is only required for some nested
                               attributes (e.g. when sub-keys of a runtime
                               properties dict that have been modified).
                               If DB updates aren't happening but no errors
                               are reported then you probably need this.
        :param validate_global: Verify that modification of this global
                                resource is permitted
        :return: The updated instance
        """
        if instance.is_resource and validate_global:
            validate_global_modification(instance)
        if log:
            current_app.logger.debug('Update {0}'.format(instance))
        db.session.add(instance)
        self._validate_unique_resource_id_per_tenant(instance)
        for attr in modified_attrs:
            flag_modified(instance, attr)
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


class ReadOnlyStorageManager(SQLStorageManager):
    def put(self, instance):
        return instance

    def delete(self, instance):
        return instance

    def update(self, instance, log=True, modified_attrs=()):
        return instance


def get_storage_manager():
    """Get the current Flask app's storage manager, create if necessary
    """
    return current_app.config.setdefault('storage_manager',
                                         SQLStorageManager())


def get_read_only_storage_manager():
    """Get the current Flask app's read only storage manager, create if
    necessary"""
    return current_app.config.setdefault('read_only_storage_manager',
                                         ReadOnlyStorageManager())


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
