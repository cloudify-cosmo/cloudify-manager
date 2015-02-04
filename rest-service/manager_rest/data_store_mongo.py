from flask.ext.mongoengine import MongoEngine
from mongoengine import Document, fields as mongo_fields
from flask.ext.security import MongoEngineUserDatastore, UserMixin, \
    RoleMixin


class MongoDataStore(MongoEngineUserDatastore):

    def __init__(self, app=None):
        if not app:
            raise Exception('required parameter "app" is not set')

        app.config['MONGODB_DB'] = 'mydatabase'
        app.config['MONGODB_HOST'] = 'localhost'
        app.config['MONGODB_PORT'] = 27017
        # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
        # app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

        MongoEngineUserDatastore.__init__(self, MongoEngine(app), User, Role)


class Role(Document, RoleMixin):
    name = mongo_fields.StringField(max_length=80, unique=True)
    description = mongo_fields.StringField(max_length=255)


class User(Document, UserMixin):  # for SQLAlchemy this is db.Model
    email = mongo_fields.StringField(max_length=255)
    password = mongo_fields.StringField(max_length=255)   # hashed password
    active = mongo_fields.BooleanField(default=True)
    confirmed_at = mongo_fields.DateTimeField()
    roles = mongo_fields.ListField(mongo_fields.ReferenceField(Role), default=[])
