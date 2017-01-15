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
from sqlalchemy.ext.declarative import declared_attr

from .models_base import db
from .management_models import User, Tenant
from .relationships import many_to_many_relationship, foreign_key


class DerivedMixinBase(object):
    def __init__(self, *args, **kwargs):
        super(DerivedMixinBase, self).__init__(*args, **kwargs)

    @hybrid_property
    def parent(self):
        """Return the *instance* of the parent class via a relationship,
        e.g. self.node, self.deployment (see parent.expression)
        """
        raise NotImplemented

    @parent.expression
    def parent(cls):
        """Return the parent *class*, e.g. Blueprint, Deployment
        """
        raise NotImplemented


class TopLevelTenantMixin(object):
    # Overriding attribute from SQLModelBase
    top_level_tenant = True

    @declared_attr
    def _tenant_id(cls):
        return foreign_key(Tenant.id)

    @declared_attr
    def tenant(cls):
        return db.relationship(
            Tenant,
            backref=cls.__tablename__,
            primaryjoin=lambda: Tenant.id == cls._tenant_id)


class DerivedTenantMixin(DerivedMixinBase):
    @hybrid_property
    def tenant(self):
        return self.parent.tenant


class DerivedCreatorMixin(DerivedMixinBase):
    @hybrid_property
    def creator(self):
        return self.parent.creator

    @hybrid_property
    def viewers(self):
        return self.parent.viewers

    @hybrid_property
    def owners(self):
        return self.parent.owners


class TopLevelCreatorMixin(object):
    def __init__(self, *args, **kwargs):
        super(TopLevelCreatorMixin, self).__init__(*args, **kwargs)

    # Overriding attribute from SQLModelBase
    top_level_creator = True

    @declared_attr
    def _creator_id(cls):
        return foreign_key(User.id)

    @declared_attr
    def creator(cls):
        return db.relationship(
            User,
            backref=cls.__tablename__,
            primaryjoin=lambda: User.id == cls._creator_id)

    @declared_attr
    def viewers(cls):
        return many_to_many_relationship(cls, User, table_prefix='viewers')

    @declared_attr
    def owners(cls):
        return many_to_many_relationship(cls, User, table_prefix='owners')


class TopLevelMixin(TopLevelTenantMixin, TopLevelCreatorMixin):
    def __init__(self, *args, **kwargs):
        super(TopLevelMixin, self).__init__(*args, **kwargs)


class DerivedMixin(DerivedTenantMixin, DerivedCreatorMixin):
    def __init__(self, *args, **kwargs):
        super(DerivedMixin, self).__init__(*args, **kwargs)
