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

from flask_security import UserMixin, RoleMixin, SQLAlchemyUserDatastore

from manager_rest.storage.models import db, SerializableBase, UTCDateTime
from manager_rest.constants import (ADMINISTRATOR_ROLES,
                                    SYSTEM_ADMIN_ROLE,
                                    TENANT_ADMIN_ROLE,
                                    DEFAULT_ROLE,
                                    VIEWER_ROLE,
                                    SUSPENDED_ROLE)


roles_users_table = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'))
)


groups_users_table = db.Table(
    'groups_users',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'))
)


tenants_users_table = db.Table(
    'tenants_users',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('tenant_id', db.Integer, db.ForeignKey('tenants.id'))
)


class User(SerializableBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), index=True, unique=True)
    email = db.Column(db.String(255), index=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean)
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    last_login_at = db.Column(UTCDateTime)
    created_at = db.Column(UTCDateTime)

    roles = db.relationship(
        'Role',
        secondary=roles_users_table,
        backref=db.backref('users', lazy='dynamic')
    )

    groups = db.relationship(
        'Group',
        secondary=groups_users_table,
        backref=db.backref('users', lazy='dynamic')
    )

    tenants = db.relationship(
        'Tenant',
        secondary=tenants_users_table,
        backref=db.backref('users', lazy='dynamic')
    )

    def get_all_tenants(self):
        tenant_list = self.tenants
        for group in self.groups:
            for tenant in group.tenants:
                tenant_list.append(tenant)

        return list(set(tenant_list))

    def to_dict(self):
        user_dict = super(User, self).to_dict()
        all_tenants = [tenant.name for tenant in self.get_all_tenants()]
        user_dict['tenants'] = all_tenants
        user_dict['groups'] = [group.name for group in self.groups]
        user_dict['role'] = self.role
        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    def is_sys_admin(self):
        return self.role == SYSTEM_ADMIN_ROLE

    def is_tenant_admin(self):
        return self.role == TENANT_ADMIN_ROLE

    def is_default_user(self):
        return self.role == DEFAULT_ROLE

    def is_viewer(self):
        return self.role == VIEWER_ROLE

    def is_admin(self):
        return self.role in ADMINISTRATOR_ROLES

    def is_suspended(self):
        return self.role == SUSPENDED_ROLE


class Role(SerializableBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)
    description = db.Column(db.Text)


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
