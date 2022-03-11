class TokenTests(SecurityTestBase):
    def test_valid_token_authentication(self):

        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.create()
        self._assert_user_authorized(token=token.value)

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
