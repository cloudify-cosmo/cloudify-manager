import random
import string

from cloudify.utils import parse_utc_datetime

from flask_security import current_user
from flask_security.utils import hash_password

from manager_rest.manager_exceptions import BadParametersError, NotFoundError
from manager_rest.rest import responses
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 is_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.utils import is_expired


class Tokens(SecuredResource):

    @authorize('user_token')
    def get(self):
        """
        Get token by user id
        """
        token = current_user.get_auth_token()
        return dict(username=current_user.username,
                    value=token, role=current_user.role)

    @marshal_with(responses.Tokens)
    @authorize('create_token')
    def post(self):
        """Create a new token."""
        request_dict = get_json_and_verify_params({
            'description': {'type': str},
            'expiration_date': {'optional': True},
        })

        sm = get_storage_manager()

        secret = _random_string(40)

        expiration_date = request_dict.get('expiration_date')
        if expiration_date:
            expiration_date = parse_utc_datetime(expiration_date)
        if is_expired(expiration_date):
            raise BadParametersError("Expiration date was in the past.")

        token = models.Token(
            id=_random_string(),
            description=request_dict.get('description', ''),
            secret_hash=hash_password(secret),
            expiration_date=expiration_date,
            _user_fk=current_user.id,
        )
        sm.put(token)

        # Keeping the same structure as old tokens to make migration easier,
        # but adding relevant extra details.
        return dict(username=current_user.username,
                    value=f'ctok-{token.id}-{secret}',
                    role=current_user.role,
                    expiration_date=token.expiration_date,
                    last_used=token.last_used,
                    token_id=token.id)


class TokensId(SecuredResource):
    @authorize('delete_token')
    def delete(self, token_id):
        """Delete an existing token."""
        sm = get_storage_manager()
        token = sm.get(models.Token, token_id, fail_silently=True)
        if token and _can_manage_token(token):
            sm.delete(token)
            return None, 204
        else:
            raise NotFoundError()

    @marshal_with(responses.Tokens)
    @authorize('list_token')
    def get(self, token_id):
        sm = get_storage_manager()
        token = sm.get(models.Token, token_id, fail_silently=True)

        if token and _can_manage_token(token):
            token_user = sm.get(models.User, token._user_fk)
            return dict(username=token_user.username,
                        value=f'ctok-{token.id}-********',
                        role=token_user.role,
                        expiration_date=token.expiration_date,
                        last_used=token.last_used,
                        token_id=token.id)
        else:
            raise NotFoundError()


def _can_manage_token(token):
    if token._user_fk == current_user.id:
        return True
    elif is_user_action_allowed('manage_others_tokens'):
        return True
    return False


# A bit more user friendly than uuids
def _random_string(length=10):
    charset = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(charset) for i in range(length))
