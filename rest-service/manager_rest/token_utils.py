import secrets
import string

from flask_security.utils import hash_password

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.storage import models, get_storage_manager
from manager_rest.utils import is_expired


def create_token(user_id, description=None, expiration_date=None):
    """Create and return a new token."""
    if expiration_date and is_expired(expiration_date):
        raise BadParametersError("Expiration date was in the past.")

    sm = get_storage_manager()

    secret = _random_string(40)

    token = models.Token(
        id=_random_string(),
        description=description,
        secret_hash=hash_password(secret),
        expiration_date=expiration_date,
        _user_fk=user_id,
    )
    sm.put(token)

    # Return the token with the secret or it'll never be usable
    token._secret = secret
    return token


def _random_string(length=10):
    """A random string that is a bit more user friendly than uuids"""
    charset = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(charset) for i in range(length))
