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
from copy import deepcopy

import psutil

from flask import current_app
from flask_security import current_user

from aria.storage import ModelStorage, sql_mapi, api, exceptions

from manager_rest import manager_exceptions, config
from manager_rest.storage.models_base import db
from manager_rest.constants import CURRENT_TENANT_CONFIG
from manager_rest.storage.models import Tenant

from sqlalchemy import or_ as sql_or
from sqlalchemy.exc import SQLAlchemyError
from sqlite3 import DatabaseError as SQLiteDBError

from . import models

try:
    from psycopg2 import DatabaseError as Psycopg2DBError
    sql_errors = (SQLAlchemyError, SQLiteDBError, Psycopg2DBError)
except ImportError:
    sql_errors = (SQLAlchemyError, SQLiteDBError)
    Psycopg2DBError = None


class SQLModelManager(sql_mapi.SQLAlchemyModelAPI):

    def _filter_query(self, query, filters, tenants_filter):
        """Add filter clauses to the query

        :param query: Base SQL query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :return: An SQLAlchemy AppenderQuery object
        """
        query = self._add_tenant_filter(query,
                                        tenants_filter)
        query = self._add_permissions_filter(query)
        query = super(SQLModelManager, self)._filter_query(query, filters)
        return query

    def _add_tenant_filter(self, query, tenants_filter):
        """Filter by the tenant ID associated with `model_class` (either
        directly via a relationship with the tenants table, or via an
        ancestor who has such a relationship)
        """
        # No tenant filters on models that are not defied as resources such
        # as Users/Groups
        if not self.model_cls.is_resource:
            tenants = []
        # System administrators should see all resources, regardless of tenant.
        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered as well
        elif current_user.is_admin:
            tenants = self._get_tenants_by_filter(tenants_filter)
        # Other users should only see resources for which they were granted
        # privileges via association with a tenant
        elif tenants_filter:
            tenants = self._get_user_tenants_by_filter(tenants_filter)
        else:
            tenants = current_user.get_all_tenants()

        # Filter by the `tenant_id` column. If tenant's list is empty, clauses
        # will not have effect on the query.
        clauses = [self.model_cls.tenant_id == tenant.id for tenant in tenants]
        return query.filter(sql_or(*clauses))

    def _get_user_tenants_by_filter(self, tenants_filter):
        user_tenants = current_user.get_all_tenants()
        user_tenant_names = [tenant.name for tenant in user_tenants]
        # Check if invalid filters that are not associated with the user
        # were passed
        diff = [t_name for t_name in tenants_filter if t_name not
                in user_tenant_names]
        if diff:
            raise manager_exceptions.NotFoundError(
                'One or more tenant(s) do not exist or are not associated '
                'with the current user [{0}]'.format(', '.join(diff)))
        return [tenant for tenant in user_tenants if tenant.name
                in tenants_filter]

    def _get_tenants_by_filter(self, tenants_filter):
        tenants = []
        for filter_name in tenants_filter:
            tenant = self.get(Tenant,
                              filter_name,
                              include=['id'],
                              filters={'name': filter_name})
            tenants.append(tenant)
        return tenants

    def _add_permissions_filter(self, query):
        """Filter by the users present in either the `viewers` or `owners`
        lists
        """
        # System administrators should see all resources, regardless of tenant.
        # Queries of elements that aren't resources (tenants, users, etc.),
        # shouldn't be filtered as well
        if current_user.is_admin or not self.model_cls.is_resource:
            return query

        # Only get resources where the current user appears in `viewers` or
        # `owners` *or* where the `viewers` list is empty (meaning that this
        # resource is public) *or* where the current user is the creator
        user_filter = sql_or(
            sql_or(
                self.model_cls.viewers.any(id=current_user.id),
                self.model_cls.owners.any(id=current_user.id)
            ),
            # ~ means `not` - i.e. all resources that don't have any viewers
            ~self.model_cls.viewers.any(),
            self.model_cls.creator == current_user
        )
        return query.filter(user_filter)

    def _get_query(self,
                   include=None,
                   filters=None,
                   sort=None):
        """Get an SQL query object based on the params passed

        :param include: An optional list of columns to include in the query
        :param filters: An optional dictionary where keys are column names to
        filter by, and values are values applicable for those columns (or lists
        of such values)
        :param sort: An optional dictionary where keys are column names to
        sort by, and values are the order (asc/desc)
        :return: A sorted and filtered query with only the relevant
        columns
        """
        filters = filters or dict()
        # The tenant may not necessarily be defined as a model property
        tenants_filter = filters.pop('tenant_name', [])
        include, filters, sort, joins = self._get_joins_and_converted_columns(
            include, filters, sort
        )

        query = self._get_base_query(include, joins)
        query = self._filter_query(query, filters, tenants_filter)
        query = self._sort_query(query, sort)
        return query

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
            SQLModelManager._validate_pagination(size)
            offset = pagination.get('offset', 0)
            total = query.order_by(None).count()  # Fastest way to count
            results = query.limit(size).offset(offset).all()
            return results, total, size, offset
        else:
            total = query.order_by(None).count()
            SQLModelManager._validate_returned_size(total)
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
        if len(self.list(filters=filters)) != 1:
            # Delete the newly added instance, and raise an error
            self._session.delete(instance)
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
            element_id,
            include=None,
            filters=None,
            locking=False):
        """Return a single result based on the model class and element ID
        """
        current_app.logger.debug(
            'Get `{0}` with ID `{1}`'.format(self.model_cls.__name__, element_id)
        )
        try:
            result = super(SQLModelManager, self).get_by_name(element_id, include=include)
        except exceptions.StorageError as e:
            raise manager_exceptions.NotFoundError(e)
        current_app.logger.debug('Returning {0}'.format(result))
        return result

    def _validate_available_memory(self):
        """Validate minimal available memory in manager
        """
        memory_status = psutil.virtual_memory()
        available_mb = memory_status.available / 1024 / 1024
        min_available_memory_mb = config.instance.min_available_memory_mb
        if available_mb < min_available_memory_mb:
            raise manager_exceptions.InsufficientMemoryError(
                'Insufficient memory in manager, '
                'needed: {0}mb, available: {1}mb'
                ''.format(min_available_memory_mb, available_mb))

    def list(self,
             include=None,
             filters=None,
             pagination=None,
             sort=None,
             **kwargs):
        """Return a (possibly empty) list of `model_class` results
        """
        self._validate_available_memory()
        if filters:
            msg = 'List `{0}` with filter {1}'.format(self.model_cls.__name__,
                                                      filters)
        else:
            msg = 'List `{0}`'.format(self.model_cls.__name__)
        current_app.logger.debug(msg)
        results = super(SQLModelManager, self).list(include=include,
                                                    filters=filters,
                                                    pagination=pagination,
                                                    sort=sort,
                                                    **kwargs)

        current_app.logger.debug('Returning: {0}'.format(results.items))
        metadata = deepcopy(results.metadata)
        results.metadata.clear()
        results.metadata['pagination'] = metadata
        return results

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
            SQLModelManager._validate_pagination(size)
            offset = pagination.get('offset', 0)
            total = query.order_by(None).count()  # Fastest way to count
            results = query.limit(size).offset(offset).all()
            return results, total, size, offset
        else:
            total = query.order_by(None).count()
            SQLModelManager._validate_returned_size(total)
            results = query.all()
            return results, len(results), 0, 0

    def put(self, entry, private_resource=False):
        """Create a `model_class` instance from a serializable `model` object

        :param entry: An instance of the SQLModelBase class (or some class
        derived from it)
        :param private_resource: If set to True, the resource's `viewers` list
        will be populated by the creating user only
        :return: The same instance, with the tenant set, if necessary
        """
        self._associate_users_and_tenants(entry, private_resource)
        current_app.logger.debug('Put {0}'.format(entry))
        super(SQLModelManager, self).put(entry)

        self._validate_unique_resource_id_per_tenant(entry)
        return entry

    def delete(self, entry, **kwargs):
        """Delete the passed instance
        """
        current_app.logger.debug('Delete {0}'.format(entry))
        super(SQLModelManager, self).delete(entry)
        return entry

    def update(self, entry, log=True):
        """Add `instance` to the DB session, and attempt to commit

        :param instance: Instance to be updated in the DB
        :param log: Should the update message be logged
        :return: The updated instance
        """
        if log:
            current_app.logger.debug('Update {0}'.format(entry))
            super(SQLModelManager, self).update(entry)
        return entry

    def refresh(self, entry):
        """Reload the instance with fresh information from the DB

        :param instance: Instance to be re-loaded from the DB
        :return: The refreshed instance
        """
        current_app.logger.debug('Refresh {0}'.format(entry))
        super(SQLModelManager, self).refresh(entry)
        return entry


class SQLStorageManager(ModelStorage):

    def put(self, entry, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry.__class__)).put(entry, *args, **kwargs)

    def get(self, entry_cls, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry_cls)).get(*args, **kwargs)

    def list(self, entry_cls, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry_cls)).list(*args, **kwargs)

    def delete(self, entry, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry.__class__)).delete(entry, *args, **kwargs)

    def update(self, entry, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry.__class__)).update(entry, *args, **kwargs)

    def refresh(self, entry, *args, **kwargs):
        return getattr(self, api.generate_lower_name(entry.__class__)).refresh(entry, *args, **kwargs)


def get_storage_manager():
    """Get the current Flask app's storage manager, create if necessary
    """
    return current_app.config.setdefault(
        'storage_manager',
        SQLStorageManager(
            SQLModelManager,
            api_kwargs=dict(engine=db.engine,
                            session=db.session),
            items=[
                models.Blueprint,
                models.Deployment,
                models.DeploymentModification,
                models.DeploymentUpdate,
                models.DeploymentUpdateStep,
                models.Event,
                models.Execution,
                models.Group,
                models.Log,
                models.Node,
                models.NodeInstance,
                models.Plugin,
                models.ProviderContext,
                models.Role,
                models.Snapshot,
                models.Tenant,
                models.User
            ]
        )
    )


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
