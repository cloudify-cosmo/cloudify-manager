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

from flask_security import current_user
from flask_restful import fields as flask_fields

from manager_rest.utils import classproperty
from manager_rest.constants import (OWNER_PERMISSION,
                                    VIEWER_PERMISSION,
                                    CREATOR_PERMISSION)

from .mixins import TopLevelMixin
from .models_base import db, SQLModelBase


class SQLResourceBase(SQLModelBase):
    """A class that represents SQL resource, and adds some functionality
    related to joins and tenants
    """
    # SQLAlchemy syntax
    __abstract__ = True

    # Some must-have columns for all resources
    @classmethod
    def id_column_name(cls):
        return 'storage_id'

    @classmethod
    def name_column_name(cls):
        return 'id'

    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)

    # Differentiates between resources (blueprints, nodes, etc.) and other
    # table models (users, tenants, etc.)
    is_resource = True

    # Indicates whether the `id` column in this class should be unique
    is_id_unique = True

    # A list of columns that shouldn't be serialized
    _private_fields = ['tenant_id', 'storage_id', 'creator_id']

    _extra_fields = {
        'permission': flask_fields.String,
        'tenant_name': flask_fields.String
    }

    # Lists of fields to skip when using older versions of the client
    skipped_fields = {'v1': [], 'v2': [], 'v2.1': []}

    @classproperty
    def resource_fields(cls):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        _fields = super(SQLResourceBase, cls).resource_fields

        # Filter out private fields and add extra fields (that aren't columns)
        _fields = {f: _fields[f] for f in _fields
                   if f not in cls._private_fields}
        _fields.update(SQLResourceBase._extra_fields)
        return _fields

    @property
    def permission(self):
        if self.creator == current_user:
            return CREATOR_PERMISSION
        if current_user in self.owners:
            return OWNER_PERMISSION
        if current_user in self.viewers:
            return VIEWER_PERMISSION
        return ''

    @property
    def tenant_name(self):
        return self.tenant.name

    def to_dict(self, suppress_error=False):
        result_dict = super(SQLResourceBase, self).to_dict(suppress_error)

        # Getting rid of the extra fields as these are only necessary for rest
        # responses
        for field in self._extra_fields:
            result_dict.pop(field)
        return result_dict

    def __repr__(self):
        id_name = self.name_column_name()
        return '<{0} {1}=`{2}`; tenant=`{3}`>'.format(
            self.__class__.__name__,
            id_name,
            getattr(self, id_name),
            self.tenant_name
        )


class TopLevelResource(TopLevelMixin, SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True

    is_derived = False


class DerivedResource(SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True

    is_derived = True

    # A mapping of names of attributes that are SQLA association proxies to
    # their `flask.fields` types
    proxies = {}

    @classproperty
    def resource_fields(cls):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        _fields = super(DerivedResource, cls).resource_fields
        _fields.update(cls.proxies)
        return _fields
