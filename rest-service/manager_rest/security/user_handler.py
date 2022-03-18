from datetime import datetime
import string

from flask import current_app
from flask_security.utils import verify_password

from manager_rest.storage.models import Token, User
from manager_rest.storage.models_base import db
from manager_rest.manager_exceptions import (
    NoAuthProvided,
    UnauthorizedError,
)
from manager_rest.storage import user_datastore, get_storage_manager
from manager_rest.execution_token import (set_current_execution,
                                          get_current_execution_by_token,
                                          get_execution_token_from_request)
from manager_rest.utils import is_expired


ENCODED_ID_LENGTH = 5


def user_loader(request):
    """Attempt to retrieve the current user from the request
    Either from request's Authorization attribute, or from the token header

    Having this function makes sure that this will work:
    > from flask_security import current_user
    > current_user
    <manager_rest.storage.models.User object at 0x50d9d10>

    :param request: flask's request
    :return: A user object, or None if not found
    """
    if request.authorization:
        return get_user_from_auth(request.authorization)
    execution_token = get_execution_token_from_request(request)
    if execution_token:
        execution = get_current_execution_by_token(execution_token)
        set_current_execution(execution)  # Sets the request current execution
        return execution.creator if execution else None
    token = get_token_from_request(request)
    if token:
        return get_token_status(token)
    if current_app.external_auth \
            and current_app.external_auth.can_extract_user_from_request():
        user = current_app.external_auth.get_user_from_request(request)
        if isinstance(user, User):
            return user
    return None


def get_user_from_auth(auth):
    if not auth or not auth.username:
        return None
    if auth.username[0] not in string.ascii_letters:
        return None
    return user_datastore.get_user(auth.username)


def get_token_from_request(request):
    token_auth_header = current_app.config[
        'SECURITY_TOKEN_AUTHENTICATION_HEADER']
    return request.headers.get(token_auth_header)


def get_token_status(token):

    user = None
    error = None

    token_parts = token.split('-')
    if len(token_parts) == 3:
        _, tok_id, tok_secret = token_parts

        sm = get_storage_manager()
        token = sm.get(Token, tok_id, fail_silently=True)

        error = 'Unauthorized'
        if token:
            if verify_password(tok_secret, token.secret_hash):
                user = user_datastore.find_user(id=token._user_fk)
                error = None

            if token.expiration_date is not None:
                if is_expired(token.expiration_date):
                    error = 'Token is expired'

        if not error:
            token.last_used = datetime.utcnow()
            db.session.commit()
    else:
        error = 'Invalid token structure'

    if error:
        raise UnauthorizedError(error)

    if not user:
        raise NoAuthProvided()

    return user
