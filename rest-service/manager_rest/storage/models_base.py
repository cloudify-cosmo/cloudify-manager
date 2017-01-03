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
from flask_restful import fields as flask_fields
from dateutil import parser as date_parser

from flask_sqlalchemy import SQLAlchemy

from manager_rest.utils import classproperty

db = SQLAlchemy()


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


class SQLModelBase(db.Model):
    """Abstract base class for all SQL models that allows [de]serialization
    """
    # SQLAlchemy syntax
    __abstract__ = True

    # Does the class represent a resource (Blueprint, Deployment, etc.) or a
    # management table (User, Tenant, etc.), as they are handled differently
    is_resource = False

    # Can this resource be attached to tenants
    top_level_tenant = False

    # Does this resource have a unique creator
    top_level_creator = False

    _sql_to_flask_type_map = {
        'Integer': flask_fields.Integer,
        'Text': flask_fields.String,
        'String': flask_fields.String,
        'PickleType': flask_fields.Raw,
        'UTCDateTime': flask_fields.String,
        'Enum': flask_fields.String,
        'Boolean': flask_fields.Boolean
    }

    def to_dict(self, suppress_error=False):
        """Return a dict representation of the model

        :param suppress_error: If set to True, sets `None` to attributes that
        it's unable to retrieve (e.g., if a relationship wasn't established
        yet, and so it's impossible to access a property through it)
        """
        if suppress_error:
            res = dict()
            for field in self.resource_fields:
                try:
                    field_value = getattr(self, field)
                except AttributeError:
                    field_value = None
                res[field] = field_value
        else:
            # Can't simply call here `self.to_response()` because inheriting
            # class might override it, but we always need the same code here
            res = {f: getattr(self, f) for f in self.resource_fields}
        return res

    def to_json(self):
        return jsonpickle.encode(self.to_dict(), unpicklable=False)

    def to_response(self):
        return {f: getattr(self, f) for f in self.resource_fields}

    @classproperty
    def resource_fields(self):
        """Return the list of field names for this table
        """
        fields_dict = dict()
        for field_name, column_obj in self.__table__.columns.items():
            type_name = column_obj.type.__class__.__name__
            fields_dict[field_name] = self._sql_to_flask_type_map[type_name]
        return fields_dict

    def _get_identifier(self):
        """A helper method that allows classes to override if in order to
        change the default string representation
        """
        return 'id', self.id

    @classmethod
    def get_fields(cls, field_list):
        """Return a subset of the available fields for this model according to
        the fields list passed
        """
        fields = cls.resource_fields
        return {k: v for k, v in fields.iteritems() if k in field_list}

    @classmethod
    def unique_id(cls):
        return 'id'

    def __repr__(self):
        id_name, id_value = self._get_identifier()
        return '<{0} {1}=`{2}`>'.format(
            self.__class__.__name__,
            id_name,
            id_value
        )
