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
from datetime import timedelta, datetime
from dateutil import parser as date_parser

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from flask_security import SQLAlchemyUserDatastore, UserMixin, RoleMixin

from manager_rest import config
from manager_rest.constants import BOOTSTRAP_ADMIN_ID, DEFAULT_TENANT_ID

from .idencoder import get_encoder
from .relationships import (
    foreign_key,
    many_to_many_relationship,
)
from .models_base import db, SQLModelBase, UTCDateTime, CIColumn


class ProviderContext(SQLModelBase):
    __tablename__ = 'provider_context'

    id = db.Column(db.Text, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    context = db.Column(db.PickleType, nullable=False)


class Role(SQLModelBase, RoleMixin):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False, index=True)

    description = db.Column(db.Text)

    def _get_identifier_dict(self):
        return OrderedDict({'name': self.name})


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

    def _get_groups_response(self):
        """Get groups that have been added to the tenant and their roles."""
        return {
            group_association.group.name: group_association.role.name
            for group_association in self.group_associations
        }

    def _get_users_response(self):
        """Get users that have been added to the tenant and their roles.

        There are multiple possible roles because the users might have been
        added directly and/or indirectly as members of different groups.

        """
        tenant_roles = {
            user_association.user.username: user_association.role.name
            for user_association in self.user_associations
        }

        return {
            user.username: {
                'tenant-role': tenant_roles.get(user.username),
                'roles': sorted(list(role.name for role in roles)),
            }
            for user, roles in self.all_users.iteritems()
        }

    def to_response(self, get_data=False):
        tenant_dict = super(Tenant, self).to_response()
        tenant_dict['groups'] = self._get_groups_response()
        tenant_dict['users'] = self._get_users_response()

        if get_data:
            tenant_dict['user_roles'] = {
                'direct': self.direct_users,
                'groups': self.group_users
            }
        else:
            for attr in ('groups', 'users'):
                tenant_dict[attr] = len(tenant_dict[attr])

        return tenant_dict

    @property
    def direct_users(self):
        """
        Return dict of all users directly associated with the tenant (not via
        groups) and their roles in the tenant
        """
        return {
            user_association.user.username: user_association.role.name
            for user_association in self.user_associations
        }

    @property
    def group_users(self):
        """
        Return a dict of all the groups associated with the tenant, their
        roles and users
        """
        return {
            group_association.group.name: {
                'role': group_association.role.name,
                'users': [user.username
                          for user in group_association.group.users]
            }
            for group_association in self.group_associations
        }

    @property
    def all_users(self):
        """
        Return all the users associated with the tenants - either directly,
        or via group - and their roles in the tenant
        """
        all_users = defaultdict(set)
        for user_association in self.user_associations:
            all_users[user_association.user].add(user_association.role)

        for group_association in self.group_associations:
            for user in group_association.group.users:
                all_users[user].add(group_association.role)

        return all_users

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

    @declared_attr
    def roles(cls):
        return many_to_many_relationship(cls, Role)

    @property
    def role(self):
        return self.roles[0].name

    def _get_identifier_dict(self):
        id_dict = OrderedDict({'name': self.name})
        if self.ldap_dn:
            id_dict['ldap_dn'] = self.ldap_dn
        return id_dict

    def _get_tenants_response(self):
        """Get tenants to which the group has been added and the role."""
        return {
            tenant_association.tenant.name: tenant_association.role.name
            for tenant_association in self.tenant_associations
        }

    def _get_users_response(self):
        """Get users that have been added to the group."""
        return sorted(user.username for user in self.users)

    def to_response(self, get_data=False):
        group_dict = super(Group, self).to_response()
        group_dict['tenants'] = self._get_tenants_response()
        group_dict['users'] = self._get_users_response()
        group_dict['role'] = self.role

        if not get_data:
            for attr in ('tenants', 'users'):
                group_dict[attr] = len(group_dict[attr])

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
    last_failed_login_at = db.Column(UTCDateTime)
    failed_logins_counter = db.Column(db.Integer, default=0)

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
        tenant_roles = set(self.system_roles)
        if not tenant:
            return tenant_roles
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
    def user_tenants(self):
        """
        Return all tenants the user is associated to directly (not via groups),
        including the user's role in each tenant

        Note: both tenants and roles are returned by their names, not objects
        """
        return {
            tenant_association.tenant.name: tenant_association.role.name
            for tenant_association in self.tenant_associations
        }

    @property
    def group_tenants(self):
        """
        Return all tenants the user is associated to via groups,
        including the user's role in each tenant

        Note: both tenants and roles are returned by their names, not objects
        """
        group_tenants = defaultdict(dict)
        for group in self.groups:
            for tenant_association in group.tenant_associations:
                # tenant maps to a dict, within it role maps to groups
                group_tenants[tenant_association.tenant.name].setdefault(
                    tenant_association.role.name, set()).add(group.name)
        return group_tenants

    @property
    def all_tenants(self):
        """Return all tenants the user is associated to - either directly, or
        via a group the user is in - including tenant roles

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

    def _get_tenants_response(self):
        """Get tenants to which the user has been added and the roles.

        There are multiple possible roles because the users might have been
        added directly and/or indirectly as members of different groups.

        """
        tenant_roles = {
            tenant_association.tenant.name: tenant_association.role.name
            for tenant_association in self.tenant_associations
        }

        return {
            tenant.name: {
                'tenant-role': tenant_roles.get(tenant.name),
                'roles': sorted(list(role.name for role in roles)),
            }
            for tenant, roles in self.all_tenants.iteritems()
        }

    def _get_groups_response(self):
        """Get the groups to which this user has been added."""
        return sorted(group.name for group in self.groups)

    def _get_group_tenants_response(self):
        return {
            tenant: {
                role: sorted(list(self.group_tenants[tenant][role]))
                for role in self.group_tenants[tenant]
                }
            for tenant in self.group_tenants
        }

    def to_response(self, get_data=False):
        user_dict = super(User, self).to_response()
        user_dict['tenants'] = self._get_tenants_response()
        user_dict['groups'] = self._get_groups_response()
        user_dict['role'] = self.role
        user_dict['group_system_roles'] = self.group_system_roles
        user_dict['is_locked'] = self.is_locked

        if get_data:
            user_dict['tenant_roles'] = {
                'direct': self.user_tenants,
                'groups': self._get_group_tenants_response()
            }
        else:
            for attr in ('tenants', 'groups'):
                user_dict[attr] = len(user_dict[attr])

        return user_dict

    @property
    def role(self):
        return self.roles[0].name

    @property
    def group_system_roles(self):
        group_system_roles = {}
        for group in self.groups:
            group_system_roles.setdefault(group.role, []).append(group.name)
        return group_system_roles

    @property
    def system_roles(self):
        return [self.role] + [role for role in self.group_system_roles]

    @property
    def is_bootstrap_admin(self):
        return self.id == BOOTSTRAP_ADMIN_ID

    @property
    def is_locked(self):
        allowed_bad_logins = config.instance.failed_logins_before_account_lock
        if self.failed_logins_counter > allowed_bad_logins:
            lockout_period = timedelta(
                minutes=config.instance.account_lock_period)
            last_failed_login = date_parser.parse(
                self.last_failed_login_at, ignoretz=True)
            if last_failed_login + lockout_period > datetime.now():
                return True
        return False


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


class License(SQLModelBase):
    __tablename__ = 'licenses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.Text, unique=True)
    expiration_date = db.Column(UTCDateTime)
    license_edition = db.Column(db.String(255))
    trial = db.Column(db.Boolean, nullable=False, default=False)
    cloudify_version = db.Column(db.Text)
    capabilities = db.Column(db.ARRAY(db.Text))
    signature = db.Column(db.LargeBinary)

    @property
    def expired(self):
        now = datetime.utcnow()
        expiration_date = datetime.strptime(self.expiration_date,
                                            '%Y-%m-%dT%H:%M:%S.%fZ')
        return expiration_date < now

    def to_response(self, get_data=False):
        user_dict = super(License, self).to_response()
        user_dict['expired'] = self.expired
        return user_dict


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
