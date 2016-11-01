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

import jsonpickle
from dateutil import parser as date_parser

from flask_sqlalchemy import SQLAlchemy

from manager_rest.utils import classproperty

db = SQLAlchemy()


class SQLModelBase(db.Model):
    """Abstract base class for all SQL models that allows [de]serialization
    """
    # SQLAlchemy syntax
    __abstract__ = True

    # Indicates to the storage manager whether the table is a resource or not
    is_resource = False

    def to_dict(self, suppress_error=False):
        """Return a dict representation of the model

        :param suppress_error: If set to True, sets `None` to attributes that
        it's unable to retrieve (e.g., if a relationship wasn't established
        yet, and so it's impossible to access a property through it)
        """
        if suppress_error:
            res = dict()
            for field in self.fields:
                try:
                    field_value = getattr(self, field)
                except AttributeError:
                    field_value = None
                res[field] = field_value
        else:
            res = {field: getattr(self, field) for field in self.fields}
        return res

    def to_json(self):
        return jsonpickle.encode(self.to_dict(), unpicklable=False)

    @classproperty
    def fields(cls):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        return cls.__table__.columns.keys()

    def _get_unique_id(self):
        """A method to allow classes to override the default representation
        """
        return 'id', self.id

    def __str__(self):
        id_name, id_value = self._get_unique_id()
        return '<{0} {1}=`{2}`>'.format(
            self.__class__.__name__,
            id_name,
            id_value
        )

    def __repr__(self):
        return str(self)

    def __unicode__(self):
        return str(self)


class SQLResource(SQLModelBase):
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
    _private_fields = ['tenant_id', 'storage_id']

    # A dictionary where the keys are names of instance properties the class
    # has, which to the rest of the code are indistinguishable from regular
    # SQLA columns [e.g. `blueprint_id`, `node_id`], but in fact are pointers
    # to attributes of a one to many relationship the class has
    # [e.g. `self.blueprint.id`, `self.node.id`], and the values are themselves
    # dicts with two fields:
    # - `models`: A list of models on which the query will need to join in
    # order to have access to the above attributes. (e.g. [Node, Deployment])
    # - `column`: The actual column on which actions would need to be performed
    # [e.g. Node.id, Blueprint.id]
    join_properties = {}

    # Should be incremented for classes that "depend" on other classes (for
    # example, Blueprint should be 1, Deployment 2, Node 3, and
    # NodeInstance 4). This is necessary in order to be able to join on all
    # those tables in the correct order, if multiple joins are necessary.
    # Note that the order is actually *descending* - meaning 3 will be joined
    # before 2, 2 before 1, etc.
    join_order = 1

    @classproperty
    def fields(cls):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        fields = cls.__table__.columns.keys()
        fields = [f for f in fields if f not in cls._private_fields]
        properties = set(cls.join_properties.keys()) - set(cls._private_fields)
        fields.extend(properties)
        return fields


class UTCDateTime(db.TypeDecorator):

    impl = db.DateTime

    def process_result_value(self, value, engine):
        # Adhering to the same norms used in the rest of the code
        if value is not None:
            # When the date has a microsecond value equal to 0,
            # isoformat returns the time as 17:22:11 instead of
            # 17:22:11.000, so we need to adjust the returned value
            if value.microsecond:
                return '{0}Z'.format(value.isoformat()[:-3])
            else:
                return '{0}.000Z'.format(value.isoformat())

    def process_bind_param(self, value, dialect):
        if isinstance(value, basestring):
            # SQLite only accepts datetime objects
            return date_parser.parse(value)
        else:
            return value
