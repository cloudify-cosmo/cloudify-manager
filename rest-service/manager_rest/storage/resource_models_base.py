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

from sqlalchemy.ext.hybrid import hybrid_property

from .mixins import TopLevelMixin
from .models_base import db, SQLModelBase


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

    # A list of columns that shouldn't be serialized
    _private_fields = ['tenant_id', 'storage_id', 'creator_id']

    @hybrid_property
    def fields(self):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        fields = super(SQLResourceBase, self).fields
        fields = [f for f in fields if f not in self._private_fields]
        return fields

    @classmethod
    def unique_id(cls):
        return 'storage_id'

    # Some must-have columns for all resources
    storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)


class TopLevelResource(TopLevelMixin, SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True

    is_derived = False


class DerivedResource(SQLResourceBase):
    # SQLAlchemy syntax
    __abstract__ = True

    is_derived = True

    # A list of names of attributes that are SQLA association proxies
    proxies = []

    @hybrid_property
    def fields(self):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        fields = super(DerivedResource, self).fields
        properties = set(self.proxies) - set(self._private_fields)
        fields.extend(properties)
        return fields
