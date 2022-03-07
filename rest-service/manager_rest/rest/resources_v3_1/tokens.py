import random
import string

from cloudify.utils import parse_utc_datetime

from flask_security import current_user
from flask_security.utils import hash_password

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.rest import responses
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
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


# A bit more user friendly than uuids
def _random_string(length=10):
    charset = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choice(charset) for i in range(length))
