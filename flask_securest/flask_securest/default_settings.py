# import datetime
# TODO is this required?
# PERMANENT_SESSION_LIFETIME = datetime.timedelta(seconds=30)
SECRET_KEY = 'the quick brown fox jumps over the lazy dog'
# The order of authentication methods is important!
AUTHENTICATION_METHODS = [
    'flask_securest.authentication_providers.password:PasswordAuthenticator',
    'flask_securest.authentication_providers.token:TokenAuthenticator'
    ]
USERSTORE_DRIVER = 'flask_securest.userstores.file:FileUserstore'
# 'security.userstores.mongo:MongoUserstore'
USERSTORE_IDENTIFIER_ATTRIBUTE = 'username'
