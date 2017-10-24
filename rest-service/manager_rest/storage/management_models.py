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

from uuid import uuid4
from collections import (
    OrderedDict,
    defaultdict,
)

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from flask_security import SQLAlchemyUserDatastore, UserMixin, RoleMixin

from manager_rest.constants import BOOTSTRAP_ADMIN_ID, DEFAULT_TENANT_ID

from .idencoder import get_encoder
from .relationships import (
    foreign_key,
    many_to_many_relationship,
)
from .models_base import db, SQLModelBase, UTCDateTime, CIColumn


def _get_response_data(resources, get_data=False, name_attr='name'):
    """Either return the sorted list of resource names or their total count

    :param resources: A list/dict of users/tenants/user-groups
    :param name_attr: The name attribute (name/username)
    :param get_data: If True: return the names, o/w return the count
    """
    if get_data:
        if isinstance(resources, list):
            return sorted(getattr(res, name_attr) for res in resources)
        elif isinstance(resources, dict):
            def get_value_data(values):
                """Get data for the values in a dictionary.

                Values might be a set (User.tenants case) or a single value
                (Group.tenans case).

                """
                if isinstance(values, set):
                    return sorted([
                        getattr(value, name_attr) for value in values])
                else:
                    return getattr(values, name_attr)

            return {
                getattr(key, name_attr): get_value_data(value)
                for key, value in resources.iteritems()
            }
        else:
            raise ValueError(
                'Unexpected resources type: {0}'.format(type(resources)))
    else:
        return len(resources)


class ProviderContext(SQLModelBase):
    __tablename__ = 'provider_context'

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    context = db.Column(db.PickleType, nullable=False)


class Tenant(SQLModelBase):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, index=True)
    rabbitmq_vhost = db.Column(db.Text)
    rabbitmq_username = db.Column(db.Text)
    rabbitmq_password = db.Column(db.Text)

    user_associations = db.relationship(
        'UserTenantAssoc',
        back_populates='tenant',
        cascade='all, delete-orphan',
    )
    users = association_proxy(
        'user_associations',
        'user',
        creator=lambda user: UserTenantAssoc(user=user),
    )
    group_associations = db.relationship(
        'GroupTenantAssoc',
        back_populates='tenant',
        cascade='all, delete-orphan',
    )
    groups = association_proxy(
        'group_associations',
        'group',
        creator=lambda group: GroupTenantAssoc(group=group),
    )

    def _get_identifier_dict(self):
        return OrderedDict({'name': self.name})

    def to_response(self, get_data=False):
        tenant_dict = super(Tenant, self).to_response()
        tenant_dict['groups'] = _get_response_data(list(self.groups), get_data)
        tenant_dict['users'] = _get_response_data(
            self.all_users,
            get_data=get_data,
            name_attr='username'
        )
        return tenant_dict

    @property
    def all_users(self):
        all_users = set()
        all_users.update(self.users)
        for group in self.groups:
            all_users.update(group.users)

        return list(all_users)

    @property
    def is_default_tenant(self):
        return self.id == DEFAULT_TENANT_ID


class Group(SQLModelBase):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = CIColumn(db.Text, unique=True, nullable=False, index=True)
    ldap_dn = CIColumn(db.Text, unique=True, nullable=True, index=True)

    tenant_associations = db.relationship(
        'GroupTenantAssoc',
        back_populates='group',
        cascade='all, delete-orphan',
    )
    tenants = association_proxy('tenant_associations', 'tenant')

    def _get_identifier_dict(self):
        id_dict = OrderedDict({'name': self.name})
        if self.ldap_dn:
            id_dict['ldap_dn'] = self.ldap_dn
        return id_dict

    def to_response(self, get_data=False):
        group_dict = super(Group, self).to_response()
        group_dict['tenants'] = _get_response_data(
            {
                tenant_association.tenant: tenant_association.role
                for tenant_association in self.tenant_associations
            },
            get_data,
        )
        group_dict['users'] = _get_response_data(
            self.users,
            get_data=get_data,
            name_attr='username'
        )
        return group_dict


class GroupTenantAssoc(SQLModelBase):
    """Association between groups and tenants.

    This is used to create a many-to-many relationship between groups and
    tenants with the ability to set the role as an additional attribute to the
    relationship.

    """
    __tablename__ = 'groups_tenants'
    group_id = foreign_key('groups.id', primary_key=True)
    tenant_id = foreign_key('tenants.id', primary_key=True)
    # TBD: Set nullable=False when role set by default in the migration script
    role_id = foreign_key('roles.id', nullable=True)

    group = db.relationship('Group', back_populates='tenant_associations')
    tenant = db.relationship('Tenant', back_populates='group_associations')
    role = db.relationship('Role')

    def _get_identifier_dict(self):
        """Return elements to display in object's string representation."""
        return OrderedDict([
            ('group', self.group.name),
            ('tenant', self.tenant.name),
            ('role', self.role.name),
        ])


class Role(SQLModelBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    description = db.Column(db.Text)

    def _get_identifier_dict(self):
        return OrderedDict({'name': self.name})


class User(SQLModelBase, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = CIColumn(db.String(255), index=True, unique=True)

    active = db.Column(db.Boolean)
    created_at = db.Column(UTCDateTime)
    email = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_login_at = db.Column(UTCDateTime)
    last_name = db.Column(db.String(255))
    password = db.Column(db.String(255))
    api_token_key = db.Column(db.String(100))

    tenant_associations = db.relationship(
        'UserTenantAssoc',
        back_populates='user',
        cascade='all, delete-orphan',
    )
    tenants = association_proxy('tenant_associations', 'tenant')

    def __init__(self, *args, **kwargs):
        super(User, self).__init__(*args, **kwargs)
        self.api_token_key = uuid4().hex

    @property
    def api_token(self):
        encoded_id = get_encoder().encode(self.id)
        return '{0}{1}'.format(encoded_id, self.api_token_key)

    def _get_identifier_dict(self):
        return OrderedDict({'username': self.username})

    @declared_attr
    def roles(cls):
        return many_to_many_relationship(cls, Role)

    def has_role_in(self, tenant, list_of_roles):
        user_roles = self.roles_in_tenant(tenant)
        return any(r in user_roles for r in list_of_roles)

    def roles_in_tenant(self, tenant):
        tenant_roles = {self.role}
        for tenant_association in self.tenant_associations:
            if tenant_association.tenant == tenant:
                tenant_roles.add(tenant_association.role)
        for group in self.groups:
            for tenant_association in group.tenant_associations:
                if tenant_association.tenant == tenant:
                    tenant_roles.add(tenant_association.role)
        return tenant_roles

    @declared_attr
    def groups(cls):
        return many_to_many_relationship(cls, Group)

    @property
    def all_tenants(self):
        """Return all tenants associated with a user - either directly, or
        via a group the user is in

        Note: recursive membership in groups is currently not supported
        """
        all_tenants = defaultdict(set)
        for tenant_association in self.tenant_associations:
            all_tenants[tenant_association.tenant].add(tenant_association.role)

        for group in self.groups:
            for tenant_association in group.tenant_associations:
                all_tenants[tenant_association.tenant].add(
                    tenant_association.role)
        return all_tenants

    def to_response(self, get_data=False):
        user_dict = super(User, self).to_response()
        user_dict['tenants'] = _get_response_data(self.all_tenants, get_data)
        user_dict['groups'] = _get_response_data(self.groups, get_data)
        user_dict['role'] = self.role
        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    @property
    def is_bootstrap_admin(self):
        return self.id == BOOTSTRAP_ADMIN_ID


class UserTenantAssoc(SQLModelBase):
    """Association between users and tenants.

    This is used to create a many-to-many relationship between users and
    tenants with the ability to set the role as an additional attribute to the
    relationship.

    """
    __tablename__ = 'users_tenants'
    user_id = foreign_key('users.id', primary_key=True)
    tenant_id = foreign_key('tenants.id', primary_key=True)
    role_id = foreign_key('roles.id')

    user = db.relationship('User', back_populates='tenant_associations')
    tenant = db.relationship('Tenant', back_populates='user_associations')
    role = db.relationship('Role')

    def _get_identifier_dict(self):
        """Return elements to display in object's string representation."""
        return OrderedDict([
            ('user', self.user.username),
            ('tenant', self.tenant.name),
            ('role', self.role.name),
        ])


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
