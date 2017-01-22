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
from sqlalchemy.ext.associationproxy import association_proxy

from manager_rest.utils import classproperty
from manager_rest.constants import (OWNER_PERMISSION,
                                    VIEWER_PERMISSION,
                                    CREATOR_PERMISSION)

from .models_base import db, SQLModelBase
from .mixins import TopLevelMixin, DerivedMixin


class SQLResourceBase(SQLModelBase):
    """A class that represents SQL resource, and adds some functionality
    related to joins and tenants
    """
    # SQLAlchemy syntax
    __abstract__ = True

    # Differentiates between resources (blueprints, nodes, etc.) and other
    # table models (users, tenants, etc.)
    is_resource = True

    # Indicates whether the `id` column in this class should be unique
    is_id_unique = True

    _extra_fields = {'permission': flask_fields.String}

    # Lists of fields to skip when using older versions of the client
    skipped_fields = {'v1': [], 'v2': [], 'v2.1': []}

    @classproperty
    def response_fields(cls):
        fields = cls.resource_fields
        fields.update(cls._extra_fields)
        return fields

    @classmethod
    def unique_id(cls):
        return '_storage_id'

    # Some must-have columns for all resources
    _storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)
    tenant_name = association_proxy('tenant', 'name')

    @property
    def permission(self):
        if self.creator == current_user:
            return CREATOR_PERMISSION
        if current_user in self.owners:
            return OWNER_PERMISSION
        if current_user in self.viewers:
            return VIEWER_PERMISSION
        return ''

    def to_response(self):
        return {f: getattr(self, f) for f in self.response_fields}

    def _get_identifier_dict(self):
        id_dict = super(SQLResourceBase, self)._get_identifier_dict()
        id_dict['tenant'] = self.tenant_name
        return id_dict


class TopLevelResource(TopLevelMixin, SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True


class DerivedResource(DerivedMixin, SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True
