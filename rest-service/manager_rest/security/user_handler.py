from datetime import datetime
import string
import typing

from flask import current_app, Response, abort, Request
from flask_security.utils import verify_password

from cloudify.workflows import tasks
from cloudify.models_states import ExecutionState

from manager_rest.storage.models import Token, User
from manager_rest.storage.models_base import db
from manager_rest.manager_exceptions import (
    NoAuthProvided,
    UnauthorizedError,
)
from manager_rest.storage import user_datastore, get_storage_manager
from manager_rest.execution_token import (
    set_current_execution,
    get_current_execution_by_token,
    get_execution_token_from_request,
    current_execution,
)
from manager_rest.security import audit
from manager_rest.utils import (
    is_expired,
    is_sanity_mode,
    check_unauthenticated_endpoint
)


def user_loader(request: Request) -> typing.Optional[User]:
    """Load a user object based on the request.

    This function is passed as a flask-login request_loader, and will be
    called for all requests.

    Try several ways of retrieving the user: each of these retrieval functions
    are expected to decide whether they should be the one to get the user,
    and return one, or None. The functions can also throw, or return an error
    response immediately.
    """
    if check_unauthenticated_endpoint():
        # the selected endpoint doesn't require auth, let's not even bother
        # loading the user
        return
    for getter, method_label in [
        (_get_user_from_execution_token, 'execution_token'),
        (_get_user_from_auth, 'http_basic'),
        (_get_user_from_token, 'token'),
        (_get_user_from_external_auth, 'external'),
    ]:
        user = getter(request)
        if user is None:
            continue
        if isinstance(user, User):
            audit.set_audit_method(method_label)
            audit.set_username(user.username)
            return user
        if isinstance(user, Response):
            abort(user)


def _get_user_from_execution_token(request):
    execution_token = get_execution_token_from_request(request)
    token = get_token_from_request(request)
    if not execution_token and not token:
        return None

    # Support using the exec token as an auth token for workflows
    execution = get_current_execution_by_token(execution_token or token)
    set_current_execution(execution)  # Sets request current execution
    if not execution:
        if execution_token:
            # execution not found, but we were explicitly given an exec-token
            raise UnauthorizedError(
                'Authentication failed, invalid Execution Token')
        else:
            return None

    if (
        execution.status in ExecutionState.ACTIVE_STATES
        or _is_valid_scheduled_execution()
        or _is_valid_cancelled_execution()
    ):
        return execution.creator
    else:
        # Not an active execution
        raise UnauthorizedError(
            'Authentication failed, invalid Execution Token')


def _is_valid_scheduled_execution():
    """Check if it's a scheduled execution that is just started to run"""
    if current_execution.status == ExecutionState.SCHEDULED:
        current_time = datetime.utcnow()
        scheduled_for = datetime.strptime(current_execution.scheduled_for,
                                          '%Y-%m-%dT%H:%M:%S.%fZ')
        # The scheduled execution just started to run
        return abs((current_time - scheduled_for).total_seconds()) < 60
    return False


def _is_valid_cancelled_execution():
    """Check if it's a cancelled execution that has running operations"""
    if current_execution.status != ExecutionState.CANCELLED:
        return False

    for graph in current_execution.tasks_graphs:
        for operation in graph.operations:
            if operation.state not in tasks.TERMINATED_STATES:
                return True
    return False


def _get_user_from_external_auth(request):
    ext_auth = current_app.external_auth
    if not ext_auth or not ext_auth.configured():
        return None
    return ext_auth.authenticate(request)


def _get_user_from_auth(request):
    auth = request.authorization
    if not auth or not auth.username:
        return None
    if auth.username[0] not in string.ascii_letters:
        return None
    user = user_datastore.get_user(auth.username)

    ext_auth = current_app.external_auth
    if ext_auth and ext_auth.configured() and not user.is_bootstrap_admin:
        # external auth is configured: we need to use it. Only the bootstrap
        # admin is allowed to bypass it.
        return None

    if not user:
        return None
    if not verify_password(auth.password, user.password):
        _increment_failed_logins_counter(user)
        raise UnauthorizedError(
            'Authentication failed for <User '
            f'username=`{auth.username}`>. '
            'Wrong credentials or locked account')
    _reset_failed_logins_counter(user)
    return user


def _increment_failed_logins_counter(user):
    user.last_failed_login_at = datetime.utcnow()
    user.failed_logins_counter += 1
    user_datastore.commit()


def _reset_failed_logins_counter(user):
    user.failed_logins_counter = 0
    if not is_sanity_mode():
        now = datetime.utcnow()
        if not user.last_login_at:
            user.first_login_at = now
        user.last_login_at = now
    user_datastore.commit()


def _get_user_from_token(request):
    token = get_token_from_request(request)
    if token:
        return get_token_status(token)


def get_token_from_request(request):
    token_auth_header = current_app.config[
        'SECURITY_TOKEN_AUTHENTICATION_HEADER']
    return request.headers.get(token_auth_header, '')


def get_token_status(token):
    user = None
    error = None

    token_parts = token.split('-', 2)
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
