from datetime import datetime

import pytest

from cloudify_rest_client.exceptions import UserUnauthorizedError

from manager_rest.constants import CLOUDIFY_TENANT_HEADER
from manager_rest.storage import user_datastore
from manager_rest.test.token_utils import (
    create_expired_token,
    sm_create_token_for_user,
)

from .test_base import SecurityTestBase
from ..security_utils import ADMIN_ROLE, USER_ROLE

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


class TokenTests(SecurityTestBase):
    # The default error should just be Unauthorized so that we know we're not
    # revealing any information to someone trying to probe the system
    def _assert_token_unauthorized(self, token, error='Unauthorized'):
        if error in ['deactivated', 'locked']:
            message = 'Wrong credentials or locked account'
        else:
            message = f'User unauthorized: {error}'
        with self.use_secured_client(token=token):
            with pytest.raises(UserUnauthorizedError, match=message):
                self.client.deployments.list()

    def _mangle_token_value(self, original_token, tok_id=None,
                            tok_secret=None):
        prefix, orig_id, orig_secret = original_token.value.split('-')
        return '{prefix}-{tok_id}-{tok_secret}'.format(
            prefix=prefix,
            tok_id=tok_id or orig_id,
            tok_secret=tok_secret or orig_id,
        )

    def _create_inactive_user_token(self):
        return sm_create_token_for_user('clair')

    def _lock_alice(self):
        user = user_datastore.get_user('alice')
        user.failed_logins_counter = 9999
        user.last_failed_login_at = datetime.utcnow()
        user_datastore.commit()

    def _unlock_alice(self):
        user = user_datastore.get_user('alice')
        user.failed_logins_counter = 0
        user_datastore.commit()

    def test_user_model_get_auth_token(self):
        user = user_datastore.get_user('alice')
        tok_val = user.get_auth_token(description='Execution rnd123 token.')

        tok_id = tok_val.split('-')[1]
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.get(tok_id)

        expiration = datetime.strptime(token.expiration_date, TIME_FORMAT)
        expiration_delay = expiration - datetime.utcnow()
        # This should expire in something close to ten hours, but let's be
        # lenient in case we're running on a potato
        min_expiration = 60 * 60 * 9.9
        # It shouldn't expire in more than ten hours
        max_expiration = 60 * 60 * 10
        assert min_expiration < expiration_delay.seconds <= max_expiration

    def test_valid_token_authentication(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        with self.use_secured_client(token=token.value):
            result = self.client.tokens.get(token.id)
        last_used = datetime.strptime(result.last_used, TIME_FORMAT)
        last_used_diff = datetime.utcnow() - last_used
        # Allow some time in case tests are running on a potato
        assert last_used_diff.seconds < 10

    def test_mangled_token_id(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        token_value = self._mangle_token_value(token, tok_id='x')
        self._assert_token_unauthorized(token=token_value)

    def test_mangled_token_secret(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        token_value = self._mangle_token_value(token, tok_secret='x')
        self._assert_token_unauthorized(token=token_value)

    def test_bad_token_structure(self):
        self._assert_token_unauthorized(token='ctok-invalidstructure',
                                        error='Invalid token structure')

    def test_expired_token_fails_auth(self):
        token = create_expired_token()
        self._assert_token_unauthorized(token=token['value'],
                                        error='Token is expired')

    def test_token_for_locked_account_fails_auth(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        try:
            self._lock_alice()
            self._assert_token_unauthorized(token=token.value, error='locked')
        finally:
            self._unlock_alice()

    def test_token_for_deactivated_account_fails_auth(self):
        token = self._create_inactive_user_token()
        self._assert_token_unauthorized(token=token['value'],
                                        error='deactivated')

    def test_token_returns_role(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        self.assertEqual(token.role, ADMIN_ROLE)

        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            token = self.client.tokens.create()
        self.assertEqual(token.role, USER_ROLE)

    def test_token_does_not_require_tenant_header(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            # Remove the the tenant header from the client
            self.client._client.headers.pop(CLOUDIFY_TENANT_HEADER, None)
            token = self.client.tokens.create()
        self._assert_user_authorized(token=token.value)

    def test_invalid_token_authentication(self):
        self._assert_user_unauthorized(token='wrong token')
