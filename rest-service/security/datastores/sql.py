from sqlalchemy.schema import Table, Column, ForeignKey
from sqlalchemy.types import Boolean, Integer, String, DateTime
from sqlalchemy.orm import relationship, backref
from flask.ext.sqlalchemy import SQLAlchemy, Model
from flask.ext.security import SQLAlchemyUserDatastore, UserMixin, \
    RoleMixin


class SQLDatastore(SQLAlchemyUserDatastore):

    def __init__(self, app=None):
        if not app:
            raise Exception('required parameter "app" is not set')

        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
        app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

        db = SQLAlchemy(app)

        SQLAlchemyUserDatastore.__init__(self, db, UserModel, RoleModel)


class RoleModel(Model, RoleMixin):
    id = Column(Integer(), primary_key=True)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class UserModel(Model, UserMixin):  # for SQLAlchemy this is db.Model
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    active = Column(Boolean())
    confirmed_at = Column(DateTime())

    roles_users = Table('roles_users',
                        Column('user_id', Integer(), ForeignKey('user.id')),
                        Column('role_id', Integer(), ForeignKey('role.id')))

    roles = relationship('Role', secondary=roles_users,
                         backref=backref('users', lazy='dynamic'))
