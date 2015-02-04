import datetime

from flask import abort
from flask.ext.security import Security
from data_store_mongo import MongoDataStore


class RestSecurity():

    def __init__(self, app):
        self.security = None
        self.app = app
        if not app:
            raise Exception('required parameter "app" is not set')

        self.secure_app()

    def secure_app(self):
        self.app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)
        self.app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
        user_datastore = MongoDataStore(self.app)
        self.security = Security(self.app, user_datastore)

        self.security.login_manager.request_loader(self._request_loader)
        self.security.login_manager.unauthorized_handler(self._unauthorized_handler)

    def _request_loader(self, request):
        user = None

        # first, try to login using the api_key url arg
        api_key = request.args.get('api_key')
        if api_key:
            # TODO should use find or get here?
            api_key_parts = api_key.split(':')
            username = api_key_parts[0]
            password = api_key_parts[1]
            user = self.security.datastore.get_user(username)

        if not user:
            # next, try to login using Basic Auth
            api_key = request.headers.get('Authorization')
            if api_key:
                api_key = api_key.replace('Basic ', '', 1)
                try:
                    from itsdangerous import base64_decode
                    api_key = base64_decode(api_key)
                    # api_key = base64.b64decode(api_key)
                except TypeError:
                    pass
                print '***** HERE, api_key: ', api_key
                api_key_parts = api_key.split(':')
                username = api_key_parts[0]
                password = api_key_parts[1]
                user = self.security.datastore.get_user(username)
                # user = User.query.filter_by(api_key=api_key).first()

            # validate...
            if not user:
                # self.email.errors.append(get_message('USER_DOES_NOT_EXIST')[0])
                print '***** error: USER_DOES_NOT_EXIST'
                abort(401)
            if not user.password:
                # self.password.errors.append(get_message('PASSWORD_NOT_SET')[0])
                print '***** error: PASSWORD_NOT_SET'
                abort(401)
                # TODO maybe use verify_and_update()?
            if not self.security.pwd_context.verify(password, getattr(user, 'password')):
                # self.password.errors.append(get_message('INVALID_PASSWORD')[0])
                print '***** error: INVALID_PASSWORD'
                abort(401)
            if not user.is_active():
                # self.email.errors.append(get_message('DISABLED_ACCOUNT')[0])
                print '***** error: DISABLED_ACCOUNT'
                abort(401)

            return user

        # finally, return None if both methods did not login the user
        return None

    @staticmethod
    def _unauthorized_handler(self):
        abort(401)