import json

from manager_rest.storage import models
from manager_rest.test import base_test

from cloudify.cryptography_utils import (
    decrypt,
)
from cloudify.models_states import VisibilityState

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
            'test_key', ["a", "b", "c"], schema={'type': 'array'})
        received_secret = self.client.secrets.get(new_secret.key)
        assert received_secret.key == new_secret.key
        assert received_secret.value == ["a", "b", "c"]

    def test_create_object_secret(self):
        new_secret = self.client.secrets.create(
            'test_key', {"a": 1, "b": 2}, schema={'type': 'object'})
        received_secret = self.client.secrets.get(new_secret.key)
        assert received_secret.key == new_secret.key
        assert received_secret.value == {"a": 1, "b": 2}

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

    def test_update_secret_schema_validation_error(self):
        self.client.secrets.create('test_key', 5,
                                   schema={'type': 'number', 'minimum': 5})
        with self.assertRaisesRegex(
            CloudifyClientError,
            'Error validating secret value:.* less than the minimum',
        ):
            self.client.secrets.update('test_key', 4)

    def test_get_secret_not_found(self):
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.secrets.get('test_key')
        assert cm.exception.status_code == 404

    def test_create_secret_with_provider_options(self):
        secret_name = 'test_key'
        secret_value = 'test_value'
        provider_options = {
            'key1': 'value1',
            'key2': 'value2',
        }

        new_secret = self.client.secrets.create(
            key=secret_name,
            value=secret_value,
            provider_options=provider_options,
        )

        assert new_secret.provider_options != provider_options
        assert json.loads(
            decrypt(
                new_secret.provider_options,
            ),
        ) == provider_options

    def test_update_secret_with_provider_options(self):
        secret_name = 'test_key'
        secret_value = 'test_value'
        provider_options = {
            'key1': 'value1',
            'key2': 'value2',
        }
        updated_provider_options = {
            'key3': 'value3',
            'key4': 'value4',
        }

        self.client.secrets.create(
            key=secret_name,
            value=secret_value,
            provider_options=provider_options,
        )

        updated_secret = self.client.secrets.update(
            key=secret_name,
            provider_options=updated_provider_options,
        )

        assert updated_secret.provider_options != provider_options
        assert updated_secret.provider_options != updated_provider_options
        assert json.loads(
            decrypt(
                updated_secret.provider_options,
            ),
        ) != provider_options
        assert json.loads(
            decrypt(
                updated_secret.provider_options,
            ),
        ) == updated_provider_options

    def test_update_secret_set_visibility(self):
        key = 'sec1'
        self.client.secrets.create(
            key,
            'value1',
            visibility=VisibilityState.PRIVATE,
        )
        sec = models.Secret.query.filter_by(key=key).one()
        with self.assertRaisesRegex(CloudifyClientError, 'visibility'):
            # already private, can't set again
            self.client.secrets.set_visibility(key, VisibilityState.PRIVATE)
        assert sec.visibility == VisibilityState.PRIVATE

        self.client.secrets.set_visibility(key, VisibilityState.TENANT)
        assert sec.visibility == VisibilityState.TENANT

        self.client.secrets.set_visibility(key, VisibilityState.GLOBAL)
        assert sec.visibility == VisibilityState.GLOBAL

        with self.assertRaisesRegex(CloudifyClientError, 'wider'):
            # already has wider visibility, can't move back from global!
            self.client.secrets.set_visibility(key, VisibilityState.TENANT)
        assert sec.visibility == VisibilityState.GLOBAL
