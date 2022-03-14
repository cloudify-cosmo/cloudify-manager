import pytest

from manager_rest.test.base_test import BaseServerTestCase


class TokensTestCase(BaseServerTestCase):
    def _check_token(self, token, description=None, expiry=None):
        assert token['description'] == description
        assert token['expiration_date'] == expiry

        retrieved_token = self.client.tokens.get(token['id'])

        value = token.pop('value')
        retrieved_value = retrieved_token.pop('value').rstrip('*')
        # The secret part of the token should be hidden, but the start should
        # be the same
        assert value.startswith(retrieved_value)

        assert token == retrieved_value

    def test_create_token(self):
        token = self.client.tokens.create()
        self._check_token(token)

    def test_create_token_with_description_and_expiry(self):
        token = self.client.tokens.create({
            description='Test token',
            expiration_date='2101-10-12 12:21',
        })

        self._check_token(token, 'Test token', '2101-10-12 12:21:00.000Z')

    def test_create_token_already_expired(self):
        with pytest.raises(Exception, matches='date.*in.*past'):
            self.client.tokens.create(expiration_date='-10h')
