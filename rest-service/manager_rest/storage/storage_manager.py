#########
# Copyright (c) 2013 Cloudify Platform Ltd. All rights reserved
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
from functools import wraps
from collections import OrderedDict
from contextlib import contextmanager
from flask_security import current_user
from sqlalchemy import or_ as sql_or, inspect, func
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from flask import current_app, has_request_context
from sqlalchemy.orm.attributes import flag_modified

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState

from manager_rest.storage.models_base import db
from manager_rest import manager_exceptions, config, utils
from manager_rest.utils import (is_administrator,
                                all_tenants_authorization,
                                validate_global_modification)

from .utils import get_column, get_joins
from .filters import add_filter_rules_to_query

from psycopg2 import DatabaseError as Psycopg2DBError
from psycopg2.errors import CheckViolation
sql_errors = (SQLAlchemyError, Psycopg2DBError, CheckViolation, IntegrityError)


def no_autoflush(f):
    @wraps(f)
    def wrapper(*args, **kwrags):
        with db.session.no_autoflush:
            return f(*args, **kwrags)

    return wrapper


class SQLStorageManager(object):
    def __init__(self):
        self._in_transaction = False

    @staticmethod
    def _is_unique_constraint_violation(e):
        return isinstance(e, IntegrityError) and e.orig.pgcode == '23505'

    def _safe_commit(self):
        """Try to commit changes in the session. Roll back if exception raised
        Excepts SQLAlchemy errors and rollbacks if they're caught
        """
        if self._in_transaction:
            return
        try:
            db.session.commit()
        except sql_errors as e:
            exception_to_raise = manager_exceptions.SQLStorageException(
                'SQL Storage error: {0}'.format(str(e))
            )
            db.session.rollback()
            if SQLStorageManager._is_unique_constraint_violation(e):
                problematic_instance_id = e.params['id']
                # Session has been rolled back at this point
                self.refresh(self.current_tenant)
                exception_to_raise = manager_exceptions.ConflictError(
                    'Instance with ID {0} cannot be added on {1} or with '
                    'global visibility'
                    ''.format(
                        problematic_instance_id,
                        self.current_tenant
                    )
                )
            raise exception_to_raise

    @contextmanager
    def transaction(self):
        """Ensure all DB calls under this are run as a single transaction.

        If the block exits normally, the transaction is committed; or if
        the block throws, the transaction is rolled back.
        Calls done before this transaction are committed immediately.
        """
        if self._in_transaction:
            raise RuntimeError('Subtransactions are disallowed')
        # after committing the existing transaction, a new one is started
        # automatically by sqlalchemy
        self._safe_commit()

        self._in_transaction = True
        try:
            with db.session.no_autoflush:
                yield
        except Exception:
            self._in_transaction = False
            db.session.rollback()
            raise
        else:
            self._in_transaction = False
            self._safe_commit()

    def _get_base_query(self, model_class, include, joins, distinct=None,
                        load_relationships=False):
        """Create the initial query from the model class and included columns

        :param model_class: SQL DB table class
        :param include: A (possibly empty) list of columns to include in
        the query
        :return: An SQLAlchemy AppenderQuery object
        """
        query = model_class.query
        if include:
            attrs = set()
            rels = set()
            for field in include:
                if not hasattr(field, 'prop'):
                    continue
                if isinstance(field.prop, RelationshipProperty):
                    rels.add(field)
                else:
                    attrs.add(field)
            if model_class.is_resource:
                attrs.add(model_class._tenant_id)
            if attrs:
                query = query.options(db.load_only(*attrs))
            if rels:
                query = query.options(db.joinedload(*rels))

        if load_relationships and not include:
            query = query.options(
                db.joinedload(attr)
                for attr in model_class.autoload_relationships
            )

        if distinct:
            query = query.distinct(*distinct)

        if joins:
            query = query.options(db.joinedload(join) for join in joins
                                  if join.can_joinedload)
            outer_joins = [join for join in joins if not join.can_joinedload]
            if outer_joins:
                query = query.outerjoin(*outer_joins)
        return query

    @staticmethod
    def _sort_query(query, model_class, sort=None, distinct=None,
                    default_sorting=True):
        """Add sorting clauses to the query

        :param query: Base SQL query
        :param sort: An optional dictionary where keys are column names to
            sort by, and values are the order (asc/desc), or callables that
            return sort conditions
        :return: An SQLAlchemy AppenderQuery object
        """
        if sort or distinct:
            if distinct:
                query = query.order_by(*distinct)
            for column, order in sort.items():
                if order == 'desc':
                    column = column.desc()
                if callable(order):
                    query = query.order_by(order(column))
                else:
                    query = query.order_by(column)
        if default_sorting:
            default_sort_column = model_class.default_sort_column()
            if default_sort_column:
                query = query.order_by(default_sort_column)
        return query

    def _filter_query(self,
                      query,
                      model_class,
                      filters,
                      substr_filters,
                      all_tenants,
                      filter_rules,
                      joins):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values). Each value can also be a callable which returns
        a SQLAlchemy filter
        :param substr_filters: An optional dictionary similar to filters,
                       when the results are filtered by substrings
        :return: An SQLAlchemy AppenderQuery object
        """
        query = self._add_tenant_filter(query, model_class, all_tenants)
        query = self._add_permissions_filter(query, model_class)
        query = self._add_value_filter(query, filters)
        query = self._add_substr_filter(query, substr_filters)
        query = self._add_filter_rules(query, model_class, filter_rules, joins)
        return query

    @staticmethod
    def _add_filter_rules(query, model_class, filter_rules, joins):
        if filter_rules:
            return add_filter_rules_to_query(
                query, model_class, filter_rules,
                already_joined={j.prop.mapper for j in joins}
            )
        return query

    def _add_value_filter(self, query, filters):
        for column, value in filters.items():
            column, value = self._update_case_insensitive(column, value)
            if callable(value):
                query = query.filter(value(column))
            elif isinstance(value, (list, tuple)):
                if value and all(callable(item) for item in value):
                    operations_filter = (operation(column)
                                         for operation in value)
                    query = query.filter(*operations_filter)
                else:
                    query = query.filter(column.in_(value))
            else:
                query = query.filter(column == value)
        return query

    def _add_substr_filter(self, query, filters):
        substr_conditions = []
        for column, value in filters.items():
            column, value = self._update_case_insensitive(column, value, True)
            if isinstance(value, text_type):
                substr_conditions.append(column.contains(value))
            else:
                raise manager_exceptions.BadParametersError(
                    'Substring filtering is only supported for strings'
                )
        if substr_conditions:
            query = query.filter(sql_or(*substr_conditions))

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
        if not (model_class.is_resource or model_class.is_label):
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
            tenants = [
                tenant for tenant in current_user.all_tenants
                if utils.tenant_specific_authorization(tenant,
                                                       model_class.__name__)
            ]
        else:
            # Specific tenant only
            tenants = [current_tenant] if current_tenant else []
        return query.tenant(*tenants)

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

    def _get_joins_and_converted_columns(self,
                                         model_class,
                                         include,
                                         filters,
                                         substr_filters,
                                         sort,
                                         distinct):
        """Get a list of tables on which we need to join and the converted
        `include`, `filters` and `sort` arguments (converted to actual SQLA
        column/label objects instead of column names)
        """
        include = include or []
        filters = filters or dict()
        substr_filters = substr_filters or dict()
        sort = sort or OrderedDict()
        distinct = distinct or []

        all_columns = set(include) | set(filters.keys()) | set(sort.keys())
        joins = get_joins(model_class, all_columns)

        include, filters, substr_filters, sort, distinct = \
            self._get_columns_from_field_names(model_class,
                                               include,
                                               filters,
                                               substr_filters,
                                               sort,
                                               distinct)
        return include, filters, substr_filters, sort, joins, distinct

    def _get_query(self,
                   model_class,
                   include=None,
                   filters=None,
                   substr_filters=None,
                   sort=None,
                   all_tenants=None,
                   distinct=None,
                   filter_rules=None,
                   default_sorting=True,
                   load_relationships=False):
        """Get an SQL query object based on the params passed

        :param model_class: SQL DB table class
        :param include: An optional list of columns to include in the query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :param substr_filters: An optional dictionary similar to filters,
                               when the results are filtered by substrings
        :param sort: An optional dictionary where keys are column names to
        sort by, and values are the order (asc/desc)
        :param load_relationships: automatically join all relationships
                                   declared in model.autoload_relationships
        :return: A sorted and filtered query with only the relevant
        columns
        """
        include, filters, substr_filters, sort, joins, distinct = \
            self._get_joins_and_converted_columns(model_class,
                                                  include,
                                                  filters,
                                                  substr_filters,
                                                  sort,
                                                  distinct)

        query = self._get_base_query(
            model_class, include, joins, distinct, load_relationships)
        query = self._filter_query(query,
                                   model_class,
                                   filters,
                                   substr_filters,
                                   all_tenants,
                                   filter_rules,
                                   joins)
        query = self._sort_query(query, model_class, sort, distinct,
                                 default_sorting)
        return query

    def _get_columns_from_field_names(self,
                                      model_class,
                                      include,
                                      filters,
                                      substr_filters,
                                      sort,
                                      distinct):
        """Go over the optional parameters (include, filters, sort), and
        replace column names with actual SQLA column objects
        """
        include = [get_column(model_class, c) for c in include]
        include = [item for item in include if item is not None]
        filters = {get_column(model_class, c): filters[c] for c in filters}
        filters = {k: v for k, v in filters.items() if k is not None}
        substr_filters = {get_column(model_class, c): substr_filters[c]
                          for c in substr_filters}
        substr_filters = {k: v for k, v in substr_filters.items()
                          if k is not None}
        sort = OrderedDict((get_column(model_class, c), sort[c]) for c in sort
                           if get_column(model_class, c) is not None)
        distinct = [get_column(model_class, c) for c in distinct]
        distinct = [item for item in distinct if item if item is not None]

        return include, filters, substr_filters, sort, distinct

    @staticmethod
    def _paginate(query, pagination, get_all_results=False, locking=False):
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
        if locking:
            query = query.with_for_update()
        if get_all_results:
            results = query.all()
        else:
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

    @no_autoflush
    def _validate_unique_resource_per_tenant(self, instance):
        """Assert that only a single resource exists with a given id in a
        given tenant
        """
        # Only relevant for resources that are connected to a tenant
        if not instance.is_resource:
            return

        query = instance.check_unique_query()
        if not query:
            return
        results = query.all()

        instance_flushed = inspect(instance).persistent
        num_of_allowed_entries = 1 if instance_flushed else 0
        if len(results) > num_of_allowed_entries:
            if instance_flushed:
                db.session.delete(instance)
            else:
                db.session.expunge(instance)
            self._safe_commit()

            if instance.visibility == VisibilityState.GLOBAL:
                error_msg = "Can't set or create the resource {0}, its " \
                    "visibility can't be global because it also exists " \
                    "in other tenants".format(instance)
            else:
                error_msg = '{0} already exists on {1} or with global ' \
                            'visibility'.format(instance, self.current_tenant)
            raise manager_exceptions.ConflictError(error_msg)

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
            all_tenants=None,
            fail_silently=False):
        """Return a single result based on the model class and element ID
        """
        current_app.logger.debug(
            'Get `%s` with ID `%s`', model_class.__name__, element_id,
        )
        if element_id is not None and filters:
            raise RuntimeError(
                'Providing an element_id with filters is ambiguous.'
            )
        if not filters:
            filters = {'id': element_id}
        query = self._get_query(model_class, include, filters,
                                all_tenants=all_tenants)
        if locking:
            query = query.with_for_update()

        try:
            result = query.one()
        except (NoResultFound, MultipleResultsFound) as e:
            id_message, filters_message = self._get_err_msg_elements(filters)
            if isinstance(e, NoResultFound):
                prefix = 'was not found'
                exc_class = manager_exceptions.NotFoundError
            else:
                prefix = 'returned multiple results'
                exc_class = manager_exceptions.AmbiguousName

            err_msg = f'Requested `{model_class.__name__}`{id_message} ' \
                      f'{prefix}{filters_message}'

            if fail_silently:
                current_app.logger.debug(err_msg)
                result = None
            else:
                raise exc_class(err_msg)

        current_app.logger.debug('Returning %s', result)
        return result

    @staticmethod
    def _get_err_msg_elements(filters):
        element_id = filters.pop('id', None)
        if element_id is not None:
            id_message = ' with ID `{0}`'.format(element_id)
        else:
            id_message = ''
        if filters and set(filters.keys()) != {'id'}:
            filters_message = ' (filters: {0})'.format(filters)
        else:
            filters_message = ''

        return id_message, filters_message

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
             get_all_results=False,
             distinct=None,
             locking=False,
             filter_rules=None,
             load_relationships=False):
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
        :param distinct: An optional list of columns names to get distinct
                         results by.
        :param filter_rules: A list of filter rules.
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
                                all_tenants,
                                distinct,
                                filter_rules,
                                load_relationships=load_relationships)

        results, total, size, offset = self._paginate(
            query,
            pagination,
            get_all_results,
            locking=locking,
        )
        pagination = {'total': total, 'size': size, 'offset': offset}
        if filter_rules:
            filtered = self.count(model_class, all_tenants=all_tenants) - total
        else:
            filtered = None

        current_app.logger.debug('Returning: %s', results)
        return ListResult(items=results, metadata={'pagination': pagination,
                                                   'filtered': filtered})

    def summarize(self, target_field, sub_field, model_class,
                  pagination, get_all_results, all_tenants, filters):
        f = get_column(model_class, target_field)
        fields = [f]
        string_fields = [target_field]
        if sub_field:
            fields.append(get_column(model_class, sub_field))
            string_fields.append(sub_field)
        entities = fields + [db.func.count('*')]
        query = self._get_query(
            model_class,
            all_tenants=all_tenants,
            filters=filters,
            sort={target_field: f.desc()},
            include=string_fields,
            default_sorting=False,
        ).with_entities(*entities).group_by(*fields)

        results, total, size, offset = self._paginate(query,
                                                      pagination,
                                                      get_all_results)
        pagination = {'total': total, 'size': size, 'offset': offset}

        return ListResult(items=results, metadata={'pagination': pagination})

    def count(self, model_class, filters=None, distinct_by=None,
              all_tenants=False):
        query = model_class.query
        if not all_tenants:
            self._add_tenant_filter(query, model_class, all_tenants=False)
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
        current_app.logger.debug('Put %s', instance)
        self.update(instance, log=False)

        self._validate_unique_resource_per_tenant(instance)
        return instance

    def delete(self, instance, validate_global=False):
        """Delete the passed instance
        """
        if instance.is_resource and validate_global:
            validate_global_modification(instance)
        current_app.logger.debug('Delete %s', instance)
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
            current_app.logger.debug('Update %s', instance)
        db.session.add(instance)
        self._validate_unique_resource_per_tenant(instance)
        for attr in modified_attrs:
            flag_modified(instance, attr)
        self._safe_commit()
        return instance

    def refresh(self, instance):
        """Reload the instance with fresh information from the DB

        :param instance: Instance to be re-loaded from the DB
        :return: The refreshed instance
        """
        current_app.logger.debug('Refresh %s', instance)
        db.session.refresh(instance)
        self._load_relationships(instance)
        return instance


class ReadOnlyStorageManager(SQLStorageManager):
    def put(self, instance):
        return instance

    def delete(self, instance, *_, **__):
        return instance

    def update(self, instance, *_, **__):
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

    @classmethod
    def from_list(cls, items):
        return cls(items, metadata={
            'pagination': {
                'total': len(items),
                'size': config.instance.default_page_size,
                'offset': 0,
            }
        })
