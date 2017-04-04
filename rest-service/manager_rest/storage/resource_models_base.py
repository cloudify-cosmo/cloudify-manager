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

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy

from manager_rest.utils import classproperty

from .models_base import db, SQLModelBase
from .management_models import Tenant, User
from .relationships import one_to_many_relationship, foreign_key


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

    _extra_fields = {}

    # Lists of fields to skip when using older versions of the client
    skipped_fields = {'v1': [], 'v2': [], 'v2.1': []}

    @classproperty
    def response_fields(cls):
        fields = cls.resource_fields.copy()
        fields.update(cls._extra_fields)
        return fields

    @classmethod
    def unique_id(cls):
        return '_storage_id'

    # Some must-have columns for all resources
    _storage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id = db.Column(db.Text, index=True)
    private_resource = db.Column(db.Boolean, default=False)

    @declared_attr
    def _tenant_id(cls):
        return foreign_key(Tenant.id)

    @declared_attr
    def _creator_id(cls):
        return foreign_key(User.id)

    @declared_attr
    def tenant(cls):
        return one_to_many_relationship(cls, Tenant, cls._tenant_id, 'id')

    @declared_attr
    def creator(cls):
        return one_to_many_relationship(cls, User, cls._creator_id, 'id')

    @declared_attr
    def tenant_name(cls):
        return association_proxy('tenant', 'name')

    @declared_attr
    def created_by(cls):
        return association_proxy('creator', 'username')

    def to_response(self, **kwargs):
        return {f: getattr(self, f) for f in self.response_fields}

    def _get_identifier_dict(self):
        id_dict = super(SQLResourceBase, self)._get_identifier_dict()
        id_dict['tenant'] = self.tenant_name
        return id_dict

    def _set_parent(self, parent_instance):
        """A convenient method for derived resources to update
        several fields that they always inherit from the parents
        """
        # We make sure the SQL query that creates the resource doesn't
        # get flushed to the DB, because it is still lacking data (the parent's
        # foreign key)
        with db.session.no_autoflush:
            self.creator = parent_instance.creator
            self.tenant = parent_instance.tenant
            self.private_resource = parent_instance.private_resource
