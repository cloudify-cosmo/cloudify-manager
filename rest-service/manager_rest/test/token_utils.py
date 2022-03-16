from datetime import datetime

from flask_security.utils import hash_password

from manager_rest.storage import models, get_storage_manager, user_datastore


def create_expired_token():
    tok_id = 'abc123'
    tok_secret = 'seekrit'
    token = models.Token(
        id=tok_id,
        description='Some old token',
        secret_hash=hash_password(tok_secret),
        expiration_date=datetime.utcfromtimestamp(1),
        _user_fk=0,
    )
    get_storage_manager().put(token)
    token._secret = tok_secret
    return token.to_response()


def sm_create_token_for_user(username):
    tok_id_len = 10
    tok_id = '{}aaaaaaaaa'.format(username)[:tok_id_len]
    tok_secret = 'yxBxDS8uIjqY1oLtRo3ZgjOQPYKUsjtoY7zANyvb'
    user = user_datastore.get_user(username)
    token = models.Token(
        id=tok_id,
        secret_hash=hash_password(tok_secret),
        _user_fk=user.id,
    )
    get_storage_manager().put(token)
    token._secret = tok_secret
    return token.to_response()
