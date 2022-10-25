import mock
from json import JSONDecodeError
from typing import Dict, Any

from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError


@mock.patch('manager_rest.rest.resources_v3_1.'
            'community_contacts.premium_enabled', False)
class TestCommunityContacts(base_test.BaseServerTestCase):
    data = {"first_name": "John",
            "last_name": "Smith",
            "email": "john2@smith.co",
            "phone": "+9729999999",
            "is_eula": True}

    def _mock_post_contact(self, data, return_value, return_ok=True):
        mock_return = mock.Mock()
        mock_return.json.return_value = return_value
        mock_return.ok = return_ok
        with mock.patch('manager_rest.rest.resources_v3_1.'
                        'community_contacts.post') as mock_post:
            mock_post.return_value = mock_return
            resp = self.client._client.post('/contacts', data=data)
        _, mock_args, mock_kwargs = mock_post.mock_calls[0]
        return resp, mock_kwargs

    def test_create_contact(self):
        data = self.data.copy()
        return_value = {"status": 200,
                        "company_name": "cmp1",
                        "contact_id": "123456"}
        response, mock_kwargs = self._mock_post_contact(data, return_value)
        assert mock_kwargs['json']['firstname'] == 'John'
        assert response == {'customer_id': 'COM-cmp1-123456'}

    def test_create_contact_missing_data(self):
        data: Dict[str, Any] = {}
        with self.assertRaises(CloudifyClientError) as cm:
            self._mock_post_contact(data, {})
        assert cm.exception.status_code == 400
        assert "Missing first_name in json request body" in str(cm.exception)

    def test_create_contact_no_eula(self):
        data = self.data.copy()
        data['is_eula'] = False
        with self.assertRaises(CloudifyClientError) as cm:
            self._mock_post_contact(data, {})
        assert cm.exception.status_code == 400
        assert "EULA must be confirmed by user" in str(cm.exception)

    def test_create_contact_invalid_email(self):
        data = self.data.copy()
        data["email"] = "a@a.a"
        return_value = {"status": 400,
                        "message": "Property values were not valid"}
        with self.assertRaises(CloudifyClientError) as cm:
            self._mock_post_contact(data, return_value)
        assert cm.exception.status_code == 400
        assert "problem while submitting the form" in str(cm.exception)

    def test_create_contact_post_fails(self):
        data = self.data.copy()
        with self.assertRaises(CloudifyClientError) as cm:
            self._mock_post_contact(data, return_value=None, return_ok=False)
        assert cm.exception.status_code == 400
        assert "problem while submitting the form" in str(cm.exception)

    def test_create_contact_malformed_return_value(self):
        data = self.data.copy()
        mock_return = mock.Mock()
        mock_return.json.side_effect = JSONDecodeError("", "", 0)
        mock_return.ok = True
        with self.assertRaises(CloudifyClientError) as cm:
            with mock.patch('manager_rest.rest.resources_v3_1.'
                            'community_contacts.post') as mock_post:
                mock_post.return_value = mock_return
                self.client._client.post('/contacts', data=data)
        assert cm.exception.status_code == 400
        assert "problem while submitting the form" in str(cm.exception)
