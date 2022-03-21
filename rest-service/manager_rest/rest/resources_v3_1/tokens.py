from datetime import datetime

from cloudify.utils import parse_utc_datetime

from flask_security import current_user

from manager_rest.manager_exceptions import NotFoundError
from manager_rest.rest import responses
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 is_user_action_allowed)
from manager_rest.storage import models, get_storage_manager
from manager_rest.storage.models_base import db
from manager_rest.rest.rest_decorators import (
    create_filters, marshal_with, paginate, sortable)
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.token_utils import create_token


class Tokens(SecuredResource):

    @authorize('token_get')
    @marshal_with(responses.Tokens)
    @create_filters(models.Token)
    @paginate
    @sortable(models.Token)
    def get(self, filters=None, pagination=None, sort=None):
        """
        Get a list of tokens.
        """
        filters = filters or {}
        if not is_user_action_allowed('manage_others_tokens'):
            filters['_user_fk'] = current_user.id

        sm = get_storage_manager()

        result = sm.list(models.Token, filters=filters,
                         pagination=pagination, sort=sort)

        return result

    @marshal_with(responses.Tokens)
    @authorize('create_token')
    def post(self):
        """Create a new token."""
        _purge_expired_user_tokens()

        request_dict = get_json_and_verify_params({
            'description': {'type': str, 'optional': True},
            'expiration_date': {'optional': True},
        })

        expiration_date = request_dict.get('expiration_date')
        if expiration_date:
            expiration_date = parse_utc_datetime(expiration_date)

        return create_token(current_user.id,
                            request_dict.get('description'), expiration_date)


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
            raise NotFoundError(f'Could not find token {token_id}')

    @marshal_with(responses.Tokens)
    @authorize('list_token')
    def get(self, token_id):
        sm = get_storage_manager()
        token = sm.get(models.Token, token_id, fail_silently=True)

        if token and _can_manage_token(token):
            return token
        else:
            raise NotFoundError(f'Could not find token {token_id}')


def _can_manage_token(token):
    return (
        token._user_fk == current_user.id
        or is_user_action_allowed('manage_others_tokens')
    )


def _purge_expired_user_tokens():
    """Delete all expired tokens for the current user."""
    expired = models.Token.query.filter_by(
        _user_fk=current_user.id).filter(
        models.Token.expiration_date <= datetime.utcnow()
    ).all()
    if expired:
        for token in expired:
            db.session.delete(token)
        db.session.commit()
