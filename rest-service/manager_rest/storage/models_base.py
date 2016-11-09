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
from sqlalchemy.ext.hybrid import hybrid_property


db = SQLAlchemy()


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

    @hybrid_property
    def fields(self):
        """Return the list of field names for this table

        Mostly for backwards compatibility in the code (that uses `fields`)
        """
        return self.__table__.columns.keys()

    def _get_identifier(self):
        """A method to allow classes to override the default representation
        """
        return 'id', self.id

    @classmethod
    def unique_id(cls):
        return 'id'

    def __str__(self):
        id_name, id_value = self._get_identifier()
        return '<{0} {1}=`{2}`>'.format(
            self.__class__.__name__,
            id_name,
            id_value
        )

    def __repr__(self):
        return str(self)

    def __unicode__(self):
        return str(self)


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
