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

import json
import re

from collections import OrderedDict
from functools import partial

from dateutil import (
    parser as date_parser,
    tz,
)
from flask_sqlalchemy import SQLAlchemy, inspect
from flask_restful import fields as flask_fields
from sqlalchemy import MetaData
from sqlalchemy.ext.associationproxy import ASSOCIATION_PROXY

from manager_rest.utils import classproperty


db = SQLAlchemy(metadata=MetaData(naming_convention={
    # This is to generate migration scripts with constraint names
    # using the same naming convention used by PostgreSQL by default
    # http://stackoverflow.com/a/4108266/183066
    'ix': '%(table_name)s_%(column_0_name)s_idx',
    'uq': '%(table_name)s_%(column_0_name)s_key',
    'ck': '%(table_name)s_%(column_0_name)s_check',
    'fk': '%(table_name)s_%(column_0_name)s_fkey',
    'pk': '%(table_name)s_pkey',
}))


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


class LocalDateTime(UTCDateTime):

    """A datetime serialized as a iso8601 string with local timezone."""

    TRANSFORMATIONS = [
        # Add millisecons if they are missing between seconds and time zone
        partial(re.compile(r'(?<=:\d{2})(?=\+)').sub, '.000'),
        # Drop microseconds and keep just milliseconds
        partial(re.compile(r'(?<=\.\d{3})\d{3}(?=\+)').sub, ''),
        # Use Z as time zone designator for UTC
        partial(re.compile(r'\+00:00').sub, r'Z'),
    ]

    def process_result_value(self, value, engine):
        """Serialize to iso8601 string with local timezone.

        :param value: Datetime stored in the database
        :type value: :class:`datetime.datetime`

        """
        if value is None:
            return

        utc_datetime = value.replace(tzinfo=tz.tzutc())
        local_datetime = utc_datetime.astimezone(tz.tzlocal())

        serialized_datetime = local_datetime.isoformat()

        for transformation in self.TRANSFORMATIONS:
            serialized_datetime = transformation(serialized_datetime)

        return serialized_datetime


class JSONString(db.TypeDecorator):

    """A json object stored as a string.

    json encoding/decoding is handled by SQLAlchemy, so this type is database
    agnostic and is not affected by differences in underlying JSON types
    implementations.

    """

    impl = db.Text

    def process_bind_param(self, value, dialect):
        """Encode object to a string before inserting into database."""
        return json.dumps(value)

    def process_result_value(self, value, engine):
        """Decode string to an object after selecting from database."""
        if value is None:
            return

        return json.loads(value)


class CIColumn(db.Column):
    """A column for case insensitive string fields
    """
    is_ci = True


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

    def to_response(self, **kwargs):
        return {f: getattr(self, f) for f in self.resource_fields}

    @classproperty
    def resource_fields(cls):
        """Return a mapping of available field names and their corresponding
        flask types
        """
        fields = dict()
        columns = inspect(cls).columns
        columns_dict = {col.name: col.type for col in columns
                        if not col.name.startswith('_')}
        columns_dict.update(cls._get_association_proxies())
        for field_name, field_type in columns_dict.iteritems():
            field_type_name = field_type.__class__.__name__
            fields[field_name] = cls._sql_to_flask_type_map[field_type_name]
        return fields

    @classmethod
    def _get_association_proxies(cls):
        """Return a dictionary with all association proxy names as keys, and
        their types (TEXT, DateTime, etc.) as values
       """
        all_descs = inspect(cls).all_orm_descriptors
        attrs_dict = dict()

        # The descriptor needs to be invoked once (using __get__) in order
        # to have access to its attributes (e.g. `remote_attr`)
        proxies = {name: desc.__get__(None, cls)
                   for name, desc in all_descs.items()
                   if desc.extension_type is ASSOCIATION_PROXY
                   and not name.startswith('_')}

        for proxy_name, proxy in proxies.iteritems():
            # Get the underlying attribute in case of multiple assoc. proxies
            while not proxy.remote_attr.is_attribute:
                proxy = proxy.remote_attr

            # Get the type of the remote attribute
            attrs_dict[proxy_name] = proxy.remote_attr.expression.type
        return attrs_dict

    def _get_identifier_dict(self):
        """A helper method that allows classes to override if in order to
        change the default string representation
        """
        return OrderedDict({'id': self.id})

    @classmethod
    def unique_id(cls):
        return 'id'

    def __repr__(self):
        """Return a representation of the class, based on the ordered dict of
        identifiers returned by `_get_identifier_dict`
        """
        id_dict = self._get_identifier_dict()
        class_name = self.__class__.__name__
        _repr = ' '.join('{0}=`{1}`'.format(k, v) for k, v in id_dict.items())
        return '<{0} {1}>'.format(class_name, _repr)
