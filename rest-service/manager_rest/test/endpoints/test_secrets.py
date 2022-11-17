from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError


class TestSecrets(base_test.BaseServerTestCase):
    def test_create_encrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        assert 'test_value' != new_secret.value

    def test_get_decrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        received_secret = self.client.secrets.get(new_secret.key)
        assert received_secret.key == new_secret.key
        assert received_secret.value == 'test_value'

    def test_create_array_secret(self):
        new_secret = self.client.secrets.create(
            'test_key', '["a", "b", "c"]', schema={'type': 'array'})
        received_secret = self.client.secrets.get(new_secret.key)
        assert received_secret.key == new_secret.key
        assert received_secret.value == ["a", "b", "c"]

    def test_create_object_secret(self):
        new_secret = self.client.secrets.create(
            'test_key', {"a": 1, "b": 2}, schema={'type': 'object'})
        received_secret = self.client.secrets.get(new_secret.key)
        assert received_secret.key == new_secret.key
        assert received_secret.value == {"a": 1, "b": 2}

    def test_create_secret_schema_value_not_json(self):
        with self.assertRaisesRegex(
            CloudifyClientError,
            'Error decoding secret value:.* not of type \'object\'',
        ):
            self.client.secrets.create(
                'test_key',
                'a string',
                schema={'type': 'object'},
            )

    def test_create_secret_schema_type_mismatch(self):
        with self.assertRaisesRegex(
            CloudifyClientError,
            'Error validating secret value:.* not of type \'object\'',
        ):
            self.client.secrets.create(
                'test_key',
                ["a", "b", "c"],
                schema={'type': 'object'}
            )

    def test_create_secret_schema_validation_error(self):
        with self.assertRaisesRegex(
            CloudifyClientError,
            'Error validating secret value:.* greater than the maximum',
        ):
            self.client.secrets.create(
                'test_key',
                20.5,
                schema={'type': 'number', 'maximum': 20}
            )

    def test_update_encrypted_secret(self):
        key = 'test_key'
        self.client.secrets.create(key, 'test_value')
        updated_secret = self.client.secrets.update(key, 'test_value2')
        assert 'test_value2' != updated_secret.value
        updated_secret = self.client.secrets.get(key)
        assert 'test_value2' == updated_secret.value

    def test_get_secret_not_found(self):
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.secrets.get('test_key')
        assert cm.exception.status_code == 404
