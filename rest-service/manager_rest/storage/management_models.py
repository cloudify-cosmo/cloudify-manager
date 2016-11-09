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
from flask_security import SQLAlchemyUserDatastore, UserMixin, RoleMixin

from manager_rest.constants import ADMIN_ROLE, USER_ROLE, SUSPENDED_ROLE

from .models_base import db, SQLModelBase, UTCDateTime
from .relationships import many_to_many_relationship


class ProviderContext(SQLModelBase):
    __tablename__ = 'provider_context'

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    context = db.Column(db.PickleType, nullable=False)


class Tenant(SQLModelBase):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, index=True)

    def _get_identifier(self):
        return 'name', self.name

    def to_dict(self, suppress_error=False):
        tenant_dict = super(Tenant, self).to_dict(suppress_error)
        all_groups_names = [group.name for group in self.groups.all()]
        all_users_names = [user.username for user in self.users.all()]
        tenant_dict['groups'] = all_groups_names
        tenant_dict['users'] = all_users_names
        return tenant_dict


class Group(SQLModelBase):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    def _get_identifier(self):
        return 'name', self.name

    @declared_attr
    def tenants(cls):
        return many_to_many_relationship(cls, Tenant)

    def to_dict(self, suppress_error=False):
        group_dict = super(Group, self).to_dict(suppress_error)
        group_dict['tenants'] = [tenant.name for tenant in self.tenants]
        group_dict['users'] = [user.username for user in self.users]
        return group_dict


class Role(SQLModelBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    description = db.Column(db.Text)

    def _get_identifier(self):
        return 'name', self.name


class User(SQLModelBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), index=True, unique=True)

    active = db.Column(db.Boolean)
    created_at = db.Column(UTCDateTime)
    email = db.Column(db.String(255), index=True)
    first_name = db.Column(db.String(255))
    last_login_at = db.Column(UTCDateTime, index=True)
    last_name = db.Column(db.String(255))
    password = db.Column(db.String(255))

    def _get_identifier(self):
        return 'username', self.username

    @declared_attr
    def roles(cls):
        return many_to_many_relationship(cls, Role)

    @declared_attr
    def groups(cls):
        return many_to_many_relationship(cls, Group)

    @declared_attr
    def tenants(cls):
        return many_to_many_relationship(cls, Tenant)

    def get_all_tenants(self):
        """Return all tenants associated with a user - either directly, or
        via a group the user is in

        Note: recursive membership in groups is currently not supported
        """
        tenant_list = self.tenants
        for group in self.groups:
            for tenant in group.tenants:
                tenant_list.append(tenant)

        return list(set(tenant_list))

    def to_dict(self, suppress_error=False):
        user_dict = super(User, self).to_dict(suppress_error)
        all_tenants = [tenant.name for tenant in self.get_all_tenants()]
        user_dict['tenants'] = all_tenants
        user_dict['groups'] = [group.name for group in self.groups]
        user_dict['role'] = self.role
        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    @property
    def is_default_user(self):
        return self.role == USER_ROLE

    @property
    def is_admin(self):
        return self.role == ADMIN_ROLE

    @property
    def is_suspended(self):
        return self.role == SUSPENDED_ROLE


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
