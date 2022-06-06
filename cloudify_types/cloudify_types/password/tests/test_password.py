import unittest
from mock import patch, Mock

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError

from cloudify_types.component.tests.client_mock import MockCloudifyRestClient

from ..operations import creation_validation, create

from string import ascii_lowercase, digits, punctuation


NODE_PROPS = {
    'length': 8,
    'uppercase': 0,
    'lowercase': 0,
    'digits': 0,
    'symbols': 0,
}


class TestPassword(unittest.TestCase):

    def setUp(self):
        self._ctx = self.get_mock_ctx('test')
        current_ctx.set(self._ctx)
        self.cfy_mock_client = MockCloudifyRestClient()

    def test_create_password_defaults(self):
        created_password = self._create_password()
        assert len(created_password) == 8

    def test_create_password_set_secret(self):
        node_props = NODE_PROPS.copy()
        node_props['secret_name'] = 'myPassword'
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        with patch('cloudify.manager.get_rest_client') as mock_client:
            self.cfy_mock_client.secrets.create = Mock()
            mock_client.return_value = self.cfy_mock_client
            created_password = self._create_password()
            self.cfy_mock_client.secrets.create.assert_called()
            _, _, kwargs = self.cfy_mock_client.secrets.create.mock_calls[0]

        assert kwargs.get('key') == 'myPassword'
        assert kwargs.get('value') == created_password

    def test_create_password_use_existing(self):
        node_props = NODE_PROPS.copy()
        node_props['secret_name'] = 'myPassword'
        node_props['use_secret_if_exists'] = True
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        with patch('cloudify.manager.get_rest_client') as mock_client:
            self.cfy_mock_client.secrets.get = Mock(return_value='123456')
            mock_client.return_value = self.cfy_mock_client
            created_password = self._create_password()
            self.cfy_mock_client.secrets.get.assert_called()
        assert created_password == '123456'

    def test_create_password_use_existing_no_secret_name(self):
        node_props = NODE_PROPS.copy()
        node_props['use_secret_if_exists'] = True
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        self.assertRaisesRegex(NonRecoverableError,
                               r'Can\'t enable `use_secret_if_exists` '
                               r'property without providing a secret_name',
                               self._create_password)

    def test_create_password_only_uppercase_and_digits(self):
        node_props = NODE_PROPS.copy()
        node_props['lowercase'] = -1
        node_props['symbols'] = -1
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        created_password = self._create_password()
        assert len(created_password) == 8
        assert not any(ch in punctuation + ' ' for ch in created_password)
        assert not any(ch in ascii_lowercase for ch in created_password)

    def test_create_password_match_requirements(self):
        node_props = NODE_PROPS.copy()
        node_props['length'] = 12
        node_props['digits'] = 2
        node_props['symbols'] = 1
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        created_password = self._create_password()
        assert len(created_password) == 12
        num_digits, num_symbols = 0, 0
        for ch in created_password:
            if ch in digits:
                num_digits += 1
            if ch in punctuation + ' ':
                num_symbols += 1
        assert num_digits >= 2
        assert num_symbols >= 1

    def test_create_password_bad_length(self):
        node_props = NODE_PROPS.copy()
        node_props['length'] = 5
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        self.assertRaisesRegex(NonRecoverableError,
                               r'Password length is required to be at '
                               r'least 6 characters',
                               self._create_password)

    def test_create_password_bad_character_group_size(self):
        node_props = NODE_PROPS.copy()
        node_props['lowercase'] = -10
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        self.assertRaisesRegex(NonRecoverableError,
                               r'expecting an integer greater than 0, or -1',
                               self._create_password)

    def test_create_password_all_character_groups_disabled(self):
        node_props = NODE_PROPS.copy()
        node_props['uppercase'] = -1
        node_props['lowercase'] = -1
        node_props['digits'] = -1
        node_props['symbols'] = -1
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        self.assertRaisesRegex(NonRecoverableError,
                               r'at least one character group should be used',
                               self._create_password)

    def test_create_password_character_groups_too_long(self):
        node_props = NODE_PROPS.copy()
        node_props['uppercase'] = 4
        node_props['lowercase'] = 5
        self._ctx = self.get_mock_ctx('test', node_props=node_props)
        current_ctx.set(self._ctx)

        self.assertRaisesRegex(NonRecoverableError,
                               r'lengths of required character groups is '
                               r'larger than the password length',
                               self._create_password)

    def _create_password(self):
        creation_validation()
        create()
        return self._ctx.instance.runtime_properties.get('password')

    @staticmethod
    def get_mock_ctx(test_name, node_props=NODE_PROPS):
        return MockCloudifyContext(
            node_id='pswd_node_id',
            node_name='pswd_node_name',
            deployment_id=f'{test_name}',
            properties=node_props
        )
