import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.test.security_utils import add_users_to_db, get_test_users
from manager_rest.test.token_utils import (
    create_expired_token,
    sm_create_token_for_user,
)


class TokensTestCase(BaseServerTestCase):
    def setUp(self):
        super(TokensTestCase, self).setUp()
        add_users_to_db(get_test_users())

    def _check_token(self, token, description=None, expiry=None,
                     user='alice'):
        assert token['description'] == description
        assert token['expiration_date'] == expiry

        client = self.create_client_with_tenant(
            username=user, password='{}_password'.format(user))
        retrieved_token = client.tokens.get(token['id'])

        value = token.pop('value')
        retrieved_value = retrieved_token.pop('value').rstrip('*')
        # The secret part of the token should be hidden, but the start should
        # be the same
        assert value.startswith(retrieved_value)

        assert token == retrieved_token

    def _check_tokens_list(self, existing=None, not_existing=None,
                           user='alice'):
        existing = existing or []
        not_existing = not_existing or []
        client = self.create_client_with_tenant(
            username=user, password='{}_password'.format(user))
        existing_tokens = client.tokens.list()
        existing_ids = [tok['id'] for tok in existing_tokens]
        assert all(token['id'] in existing_ids for token in existing)
        assert all(token['id'] not in existing_ids for token in not_existing)

    def _raises_404(self, function, args=None, kwargs=None):
        args = args or []
        kwargs = kwargs or {}
        try:
            function(*args, **kwargs)
            raise AssertionError('404 should have been raised.')
        except CloudifyClientError as err:
            assert err.status_code == 404

    def test_create_token(self):
        token = self.client.tokens.create()
        self._check_token(token)

    def test_create_token_with_description_and_expiry(self):
        token = self.client.tokens.create(
            description='Test token',
            expiration='2101-10-12 12:21',
        )

        self._check_token(token, 'Test token', '2101-10-12T12:21:00.000Z')

    def test_create_token_already_expired(self):
        with pytest.raises(Exception, match='date.*in.*past'):
            self.client.tokens.create(expiration='1972-02-10 12:57')

    def test_create_token_removes_expired(self):
        expired_token = create_expired_token()

        self._check_tokens_list(existing=[expired_token])

        new_token = self.client.tokens.create()

        self._check_tokens_list(existing=[new_token])
        self._check_tokens_list(not_existing=[expired_token])

    def test_user_get_tokens_for_this_and_other_user(self):
        other_user_token = sm_create_token_for_user('alice')
        this_user_token = sm_create_token_for_user('dave')
        client = self.create_client_with_tenant(
            username='dave',
            password='dave_password')
        self._check_tokens_list(
            existing=[this_user_token],
            not_existing=[other_user_token],
            user='dave',
        )
        self._raises_404(client.tokens.get, [other_user_token['id']])
        client.tokens.get(this_user_token['id'])

    def test_admin_get_tokens_for_this_and_other_user(self):
        other_user_token = sm_create_token_for_user('alice')
        this_user_token = sm_create_token_for_user('dave')
        client = self.create_client_with_tenant(
            username='alice',
            password='alice_password')
        self._check_tokens_list(
            existing=[this_user_token, other_user_token],
        )
        client.tokens.get(other_user_token['id'])
        client.tokens.get(this_user_token['id'])

    def test_delete_own_token(self):
        this_user_token = sm_create_token_for_user('dave')
        self._check_tokens_list(existing=[this_user_token])
        client = self.create_client_with_tenant(
            username='dave',
            password='dave_password')
        client.tokens.delete(this_user_token['id'])
        self._check_tokens_list(not_existing=[this_user_token])

    def test_user_delete_other_token(self):
        other_user_token = sm_create_token_for_user('alice')
        self._check_tokens_list(existing=[other_user_token])
        client = self.create_client_with_tenant(
            username='dave',
            password='dave_password')
        self._raises_404(client.tokens.delete, [other_user_token['id']])
        # Token should still exist
        self._check_tokens_list(existing=[other_user_token])

    def test_admin_delete_other_token(self):
        other_user_token = sm_create_token_for_user('dave')
        self._check_tokens_list(existing=[other_user_token])
        client = self.create_client_with_tenant(
            username='alice',
            password='alice_password')
        client.tokens.delete(other_user_token['id'])
        self._check_tokens_list(not_existing=[other_user_token])
