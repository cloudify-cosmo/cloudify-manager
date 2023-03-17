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

from typing import Iterable, Type, Callable, Any

import itertools
import psutil
from functools import wraps
from contextlib import contextmanager
from flask_security import current_user
from sqlalchemy import or_ as sql_or, inspect, func, sql
from sqlalchemy.orm import (
    RelationshipProperty,
    aliased,
    InstrumentedAttribute,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
    IntegrityError,
    NoResultFound,
    MultipleResultsFound,
)
from sqlalchemy.ext.associationproxy import AssociationProxyInstance
from flask import current_app, has_request_context
from sqlalchemy.orm.attributes import flag_modified

from cloudify.models_states import VisibilityState

from manager_rest.storage.models_base import db
from manager_rest import manager_exceptions, config, utils
from manager_rest.utils import (is_administrator,
                                all_tenants_authorization,
                                validate_global_modification)

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


class _Transaction(object):
    """A transaction controller yielded by `sm.transaction()`

    This allows the in-transaction code to force the transaction to commit,
    even if the block throws an exception (which would cause a rollback
    instead otherwise).
    """

    def __init__(self):
        self.force_commit = False


class SQLStorageManager(object):
    def __init__(self, user=None, tenant=None):
        self._user = user
        self._tenant = tenant
        self._in_transaction = False

    def _safe_commit(self):
        """Try to commit changes in the session. Roll back if exception raised
        Excepts SQLAlchemy errors and rollbacks if they're caught
        """
        if self._in_transaction:
            return
        try:
            db.session.commit()
        except sql_errors as e:
            db.session.rollback()

            # if is a unique constraint violation...
            if isinstance(e, IntegrityError) and e.orig.pgcode == '23505':
                problematic_instance_id = e.params['id']
                # Session has been rolled back at this point
                self.refresh(self.current_tenant)
                raise manager_exceptions.ConflictError(
                    f'Instance with ID {problematic_instance_id} cannot be '
                    f'added on {self.current_tenant} or with global visibility'
                )
            raise manager_exceptions.SQLStorageException(
                f'SQL Storage error: {e}'
            )

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
        tx = _Transaction()
        try:
            with db.session.no_autoflush:
                yield tx
        except Exception:
            self._in_transaction = False
            if tx.force_commit:
                self._safe_commit()
            else:
                db.session.rollback()
            raise
        else:
            self._in_transaction = False
            self._safe_commit()

    def _get_query(
        self,
        model_class,
        include=None,
        filters=None,
        substr_filters=None,
        sort=None,
        sort_labels=None,
        all_tenants=False,
        distinct=None,
        filter_rules=None,
        default_sorting=True,
        group_by=None,
        with_entities=None,
    ):
        # first, default all the arguments. They're all optional.
        filters = filters or {}
        sort = sort or {}
        distinct = distinct or []
        include = include or []
        with_entities = with_entities or []
        group_by = group_by or []
        substr_filters = substr_filters or {}

        query, resolved_fields, rels = self._resolve_included_fields(
            model_class,
            set(include).union(sort, distinct, filters, substr_filters),
        )

        # apply the filters. Currently, tenant filter and filter rules
        # are methods that modify the query, rather than returning filter
        # expressions. We might want to change that later.
        for filter_expr in itertools.chain(
            self._resolve_value_filters(filters, resolved_fields),
            self._resolve_substr_filters(substr_filters, resolved_fields),
            self._resolve_permissions_filter(model_class),
        ):
            query = query.filter(filter_expr)

        query = self._add_tenant_filter(query, model_class, all_tenants)
        query = self._add_filter_rules(
            query, model_class, filter_rules, joins=rels)

        # apply .with_entities, .group_by, and .distinct
        entities = [
            e for w in with_entities if (e := resolved_fields.get(w))
        ]
        if entities:
            query = query.with_entities(*entities, db.func.count('*'))

        group_columns = [
            field for g in group_by if (field := resolved_fields.get(g))
        ]
        if group_columns:
            query = query.group_by(*group_columns)

        distinct_cols = [
            field for d in distinct if (field := resolved_fields.get(d))
        ]
        if distinct_cols:
            query = query.distinct(*distinct_cols)

        # finally, apply sorting. SQL requires that distinct columns MUST
        # be the first ordering.
        for order_by in itertools.chain(
            distinct_cols,
            self._resolve_sort(resolved_fields, sort),
            self._resolve_sort_labels(model_class, sort_labels),
            self._resolve_default_sort(model_class, default_sorting),
        ):
            query = query.order_by(order_by)

        return query

    def _resolve_included_fields(
        self,
        model_class: db.Model,
        include: Iterable[str],
    ) -> tuple[
        db.Query,
        dict[str, InstrumentedAttribute],
        set[sql.ClauseElement],
    ]:
        """Examine model_class and resolve included fields.

        This fetches the actual fields to be put in the query, based
        on includes, while resolving association-proxies to be the
        target fields, and joining the related tables.

        Returns a 3-tuple of:
          - a query object with all the included relations already joined
          - a dict of resolved fields, ready to be used in filters and sorts
          - a set of the joined relations
        """
        query = model_class.query
        resolved_fields = {}
        rels = set()

        for field_name in include:
            field = getattr(model_class, field_name, None)
            if not field:
                continue

            if isinstance(field, AssociationProxyInstance):
                # specialcase if there is an assoc proxy in includes:
                # join the proxied-to relationship, but only load
                # the proxied attribute.

                # first, we'll need to figure out the whole join path
                # in case of chained assoc proxies (e.g. NI->node->dep)
                while isinstance(field, AssociationProxyInstance):
                    col_name = field.target_collection
                    col = getattr(field.owning_class, col_name)
                    target = db.aliased(field.target_class)

                    query = query.outerjoin(target, col)
                    field = getattr(target, field.value_attr)

            elif not hasattr(field, 'prop'):
                continue
            elif isinstance(field.prop, RelationshipProperty):
                rels.add(field)
            resolved_fields[field_name] = field

        for rel in rels:
            query = query.options(db.joinedload(rel))

        return query, resolved_fields, rels

    def _resolve_value_filters(
        self,
        filters: dict[str, Any],
        resolved_fields: dict[str, InstrumentedAttribute],
    ) -> Iterable[sql.ClauseElement]:
        for field_name, value in filters.items():
            field = resolved_fields.get(field_name)
            if not field:
                continue
            field, value = self._update_case_insensitive(field, value)
            if callable(value):
                exp = value(field)
            elif isinstance(value, (list, tuple)):
                if value and all(callable(item) for item in value):
                    operations_filter = (
                        operation(field) for operation in value)
                    exp = db.and_(*operations_filter)
                else:
                    exp = field.in_(value)
            else:
                exp = field == value
            yield exp

    @staticmethod
    def _add_filter_rules(query, model_class, filter_rules, joins):
        if filter_rules:
            return add_filter_rules_to_query(
                query, model_class, filter_rules,
                already_joined={j.prop.mapper for j in joins}
            )
        return query

    def _resolve_substr_filters(
        self,
        filters: dict[str, Any],
        resolved_fields: dict[str, InstrumentedAttribute],
    ) -> Iterable[sql.ClauseElement]:
        substr_conditions = []
        for colname, value in filters.items():
            column = resolved_fields.get(colname)
            if column is None:
                continue
            column, value = self._update_case_insensitive(column, value, True)
            if isinstance(value, str):
                substr_conditions.append(column.contains(value))
            else:
                raise manager_exceptions.BadParametersError(
                    'Substring filtering is only supported for strings'
                )
        if substr_conditions:
            yield sql_or(*substr_conditions)

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
            if all_tenants_authorization(self.current_user):
                return query
            # Filter by all the tenants the user is allowed to list in
            tenants = [
                tenant for tenant in self.current_user.all_tenants
                if utils.tenant_specific_authorization(tenant,
                                                       model_class.__name__)
            ]
        else:
            # Specific tenant only
            tenants = [current_tenant] if current_tenant else []
        return query.tenant(*tenants)

    def _resolve_permissions_filter(
        self,
        model_class: db.Model,
    ) -> Iterable[sql.ClauseElement]:
        """Filter by the users present in either the `viewers` or `owners`
        lists
        """
        # not used from a request handler - no relevant user
        if not has_request_context():
            return

        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered
        if not model_class.is_resource:
            return

        # For users that are allowed to see all resources, regardless of tenant
        is_admin = is_administrator(self.current_tenant, self.current_user)
        if is_admin:
            return

        # Only get resources that are public - not private (note that ~ stands
        # for NOT, in SQLA), *or* those where the current user is the creator
        yield sql_or(
            model_class.visibility != VisibilityState.PRIVATE,
            model_class.creator == self.current_user
        )

    def _resolve_sort(
        self,
        resolved_fields: dict[str, InstrumentedAttribute],
        sort: dict[str, Callable | str],
    ) -> Iterable[sql.ClauseElement]:
        for field_name, order in sort.items():
            sort_by = resolved_fields.get(field_name)
            if not sort_by:
                continue
            if order == 'desc':
                sort_by = sort_by.desc()
            elif callable(order):
                sort_by = order(sort_by)
            yield sort_by

    def _resolve_sort_labels(
        self,
        model_class: db.Model,
        sort_labels: dict[str, str],
    ) -> Iterable[sql.ClauseElement]:
        if not sort_labels:
            return
        labels_model = aliased(model_class.labels_model)
        for key, order in sort_labels.items():
            ordering = (
                db.select(
                    db.func.array_agg(db.text('value order by value asc'))
                )
                .where(labels_model._labeled_model_fk ==
                       model_class._storage_id)
                .where(labels_model.key == key)
                .scalar_subquery()
            )
            if order == 'desc':
                sort_by = db.desc(ordering)
            else:
                sort_by = db.asc(ordering)
            yield sort_by

    def _resolve_default_sort(
        self,
        model_class: db.Model,
        do_default_sort: bool,
    ) -> Iterable[sql.ClauseElement]:
        if do_default_sort:
            col = model_class.default_sort_column()
            if col:
                yield col

    @staticmethod
    def _paginate(
        model_class,
        query,
        pagination,
        get_all_results=False,
        locking=False,
    ):
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

        total = query.order_by(None).count()
        if locking:
            query = query.with_for_update(of=model_class)
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
                instance.creator = self.current_user

    @staticmethod
    def _load_relationships(instance):
        """A helper method used to overcome a problem where the relationships
        that rely on joins aren't being loaded automatically
        """
        if instance.is_resource:
            for rel in instance.__mapper__.relationships:
                getattr(instance, rel.key)

    @property
    def current_user(self):
        if self._user is not None:
            return self._user
        return current_user._get_current_object()

    @property
    def current_tenant(self):
        """Return the tenant with which the user accessed the app"""
        if self._tenant is not None:
            return self._tenant
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
        query = self._get_query(model_class, include, filters.copy(),
                                all_tenants=all_tenants)
        if locking:
            query = query.with_for_update(of=model_class)

        try:
            result = query.one()
        except (NoResultFound, MultipleResultsFound) as e:
            id_message, filters_message = self._get_err_msg_elements(filters)

            exc_class: Type[manager_exceptions.ManagerException]
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

    def list(
        self,
        model_class,
        include=None,
        filters=None,
        pagination=None,
        sort=None,
        sort_labels=None,
        all_tenants=None,
        substr_filters=None,
        get_all_results=False,
        distinct=None,
        locking=False,
        filter_rules=None,
    ):
        """Return a list of `model_class` results

        :param model_class: SQL DB table class
        :param include: An optional list of columns to include in the query
        :param filters: An optional dictionary where keys are column names to
                        filter by, and values are values applicable for those
                        columns (or lists of such values)
        :param pagination: An optional dict with size and offset keys
        :param sort: An optional dictionary where keys are column names to
                     sort by, and values are the order (asc/desc)
        :param sort_labels: An optional dictionary where keys are label name
                     to sort by, and values are the order (asc/desc)
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
        query = self._get_query(
            model_class,
            include,
            filters,
            substr_filters,
            sort,
            sort_labels,
            all_tenants,
            distinct,
            filter_rules,
        )
        results, total, size, offset = self._paginate(
            model_class,
            query,
            pagination,
            get_all_results,
            locking=locking,
        )
        pagination = {'total': total, 'size': size, 'offset': offset}
        if filter_rules:
            filtered = self._add_tenant_filter(
                model_class.query,
                model_class,
                all_tenants=all_tenants,
            ).count() - total
        else:
            filtered = None
        current_app.logger.debug('Returning: %s', results)
        return ListResult(items=results, metadata={'pagination': pagination,
                                                   'filtered': filtered})

    def summarize(self, target_field, sub_field, model_class,
                  pagination, get_all_results, all_tenants, filters):
        f = getattr(model_class, target_field, None)
        while isinstance(f, AssociationProxyInstance):
            # get the actual attribute to summarize on
            f = f.remote_attr
        fields = [f]
        string_fields = [target_field]
        if sub_field:
            subfield_col = getattr(model_class, sub_field, None)
            while isinstance(subfield_col, AssociationProxyInstance):
                # get the actual attribute to summarize on
                subfield_col = subfield_col.remote_attr
            fields.append(subfield_col)
            string_fields.append(sub_field)

        query = self._get_query(
            model_class,
            all_tenants=all_tenants,
            filters=filters,
            sort={target_field: f.desc()},
            include=string_fields,
            default_sorting=False,
            group_by=string_fields,
            with_entities=string_fields,
        )

        results, total, size, offset = self._paginate(
            model_class,
            query,
            pagination,
            get_all_results
        )
        pagination = {'total': total, 'size': size, 'offset': offset}

        return ListResult(items=results, metadata={'pagination': pagination})

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
