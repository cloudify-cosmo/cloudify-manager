from flask.ext.mongoengine import MongoEngine
from mongoengine import Document, fields as mongo_fields
from flask.ext.security import MongoEngineUserDatastore, UserMixin, \
    RoleMixin

from flask.ext.securest.models import UserModel, RoleModel
from flask.ext.securest.userstores.abstract_userstore import AbstractUserstore


class MongoUserstore(AbstractUserstore):

    def __init__(self, app=None):
        if not app:
            # app1 = flask_g.current_app  # doesn't work... why?
            raise Exception('required parameter "app" is not set')

        app.config['MONGODB_DB'] = 'mydatabase'
        app.config['MONGODB_HOST'] = 'localhost'
        app.config['MONGODB_PORT'] = 27017
        app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = 'email'

        self.db = MongoEngine(app)
        self.store = MongoEngineUserDatastore(self.db, User, Role)

    def get_user(self, identifier):
        return self.store.get_user(identifier)


# TODO find a way to externalize the user/role models

class Role(Document, RoleMixin, RoleModel):
    name = mongo_fields.StringField(max_length=80, unique=True)
    description = mongo_fields.StringField(max_length=255)

    def get_name(self):
        return Role.name


class User(Document, UserMixin, UserModel):
    email = mongo_fields.StringField(max_length=255)
    password = mongo_fields.StringField(max_length=255)
    active = mongo_fields.BooleanField(default=True)
    confirmed_at = mongo_fields.DateTimeField()
    roles = mongo_fields.ListField(mongo_fields.ReferenceField(Role),
                                   default=[])

    def get_roles(self):
        return (role.name for role in User.roles)
