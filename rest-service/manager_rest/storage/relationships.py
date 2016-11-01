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


#  region Helper functions

def foreign_key(
        parent_table,
        id_col_name='storage_id',
        nullable=False,
        column_type=db.Integer
):
    """Return a ForeignKey object with the relevant

    :param parent_table: SQL name of the parent table
    :param id_col_name: Name of the parent table's ID column [default: `id`]
    :param nullable: Should the column be allowed to remain empty
    :param column_type: The type (integer/text/etc.) of the column
    :return:
    """
    return db.Column(
        column_type,
        db.ForeignKey(
            '{0}.{1}'.format(parent_table.__tablename__, id_col_name),
            ondelete='CASCADE'
        ),
        nullable=nullable
    )


def one_to_many_relationship(
        child_class_name,
        column_name,
        parent_class_name,
        back_reference_name,
        parent_id_name='storage_id'
):
    """Return a one-to-many SQL relationship object
    Meant to be used from inside the *child* object

    :param child_class_name: Class name of the child table
    :param column_name: Name of the column pointing to the parent table
    :param parent_class_name: Class name of the parent table
    :param back_reference_name: The name to give to the reference to the child
    :param parent_id_name: Name of the parent table's ID column [default: `id`]
    :return:
    """
    return db.relationship(
        parent_class_name,
        primaryjoin='{0}.{1} == {2}.{3}'.format(
            child_class_name,
            column_name,
            parent_class_name,
            parent_id_name
        ),
        # The following line make sure that when the *parent* is
        # deleted, all its connected children are deleted as well
        backref=db.backref(back_reference_name, cascade='all')
    )


def many_to_many_relationship(
        other_table_class_name,
        connecting_table,
        back_reference_name
):
    """Return a many-to-many SQL relationship object

    :param other_table_class_name: The name of the table we're connecting to
    :param connecting_table: The secondary table used in the relationship
    :param back_reference_name: The name to give to the reference to the
    current table from the other table
    :return:
    """
    return db.relationship(
        other_table_class_name,
        secondary=connecting_table,
        backref=db.backref(back_reference_name, lazy='dynamic')
    )


#  endregion

#  region Helper tables

tenants_groups_table = db.Table(
    'tenants_groups',
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id')),
    db.Column('tenant_id', db.Integer, db.ForeignKey('tenants.id'))
)


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

#  endregion
