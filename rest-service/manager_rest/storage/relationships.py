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

from .models_base import db


def foreign_key(foreign_key_column, nullable=False):
    """Return a ForeignKey object with the relevant

    :param foreign_key_column: Unique id column in the parent table
    :param nullable: Should the column be allowed to remain empty
    """
    return db.Column(
        db.ForeignKey(foreign_key_column, ondelete='CASCADE'),
        nullable=nullable
    )


def one_to_many_relationship(child_class,
                             parent_class,
                             foreign_key_column,
                             parent_class_primary_key='_storage_id',
                             backreference=None):
    """Return a one-to-many SQL relationship object
    Meant to be used from inside the *child* object

    :param parent_class: Class of the parent table
    :param child_class: Class of the child table
    :param foreign_key_column: The column of the foreign key
    :param parent_class_primary_key: The name of the parent's primary key
    :param backreference: The name to give to the reference to the child
    """
    backreference = backreference or child_class.__tablename__
    parent_primary_key = getattr(parent_class, parent_class_primary_key)
    return db.relationship(
        parent_class,
        primaryjoin=lambda: parent_primary_key == foreign_key_column,
        # The following line makes sure that when the *parent* is
        # deleted, all its connected children are deleted as well
        backref=db.backref(backreference, cascade='all')
    )


def many_to_many_relationship(current_class, other_class, table_prefix=None):
    """Return a many-to-many SQL relationship object

    Notes:
    1. The backreference name is the current table's table name
    2. This method creates a new helper table in the DB

    :param current_class: The class of the table we're connecting from
    :param other_class: The class of the table we're connecting to
    :param table_prefix: Custom prefix for the helper table name and the
    backreference name
    """
    current_table_name = current_class.__tablename__
    current_column_name = '{0}_id'.format(current_table_name[:-1])
    current_foreign_key = '{0}.{1}'.format(
        current_table_name,
        current_class.unique_id()
    )

    other_table_name = other_class.__tablename__
    other_column_name = '{0}_id'.format(other_table_name[:-1])
    other_foreign_key = '{0}.{1}'.format(
        other_table_name,
        other_class.unique_id()
    )

    helper_table_name = '{0}_{1}'.format(
        current_table_name,
        other_table_name
    )

    backref_name = current_table_name
    if table_prefix:
        helper_table_name = '{0}_{1}'.format(table_prefix, helper_table_name)
        backref_name = '{0}_{1}'.format(table_prefix, backref_name)

    secondary_table = get_secondary_table(
        helper_table_name,
        current_column_name,
        other_column_name,
        current_foreign_key,
        other_foreign_key
    )
    return db.relationship(
        other_class,
        secondary=secondary_table,
        backref=db.backref(backref_name)
    )


def get_secondary_table(helper_table_name,
                        first_column_name,
                        second_column_name,
                        first_foreign_key,
                        second_foreign_key):
    """Create a helper table for a many-to-many relationship

    :param helper_table_name: The name of the table
    :param first_column_name: The name of the first column in the table
    :param second_column_name: The name of the second column in the table
    :param first_foreign_key: The string representing the first foreign key,
    for example `blueprint._storage_id`, or `tenants.id`
    :param second_foreign_key: The string representing the second foreign key
    :return: A Table object
    """
    return db.Table(
        helper_table_name,
        db.Column(
            first_column_name,
            db.Integer,
            db.ForeignKey(first_foreign_key)
        ),
        db.Column(
            second_column_name,
            db.Integer,
            db.ForeignKey(second_foreign_key)
        )
    )
