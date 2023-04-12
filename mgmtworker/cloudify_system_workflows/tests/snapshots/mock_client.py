"""This is a carbon-copy of cloudify_rest_client.tests.MockClient which is not
shipped as part of cloudify-common."""

from cloudify import constants
from cloudify_rest_client import CloudifyClient

from unittest import mock


class MockHTTPClient(CloudifyClient.client_class):
    def __init__(self, *args, **kwargs):
        super(MockHTTPClient, self).__init__(*args, **kwargs)
        self._do_request = mock.Mock()


class MockClient(CloudifyClient):
    client_class = MockHTTPClient

    def __init__(self, **kwargs):
        params = {
            'host': '192.0.2.4',
        }
        params.update(kwargs)
        super(MockClient, self).__init__(**params)
        # Default to make calls have a chance of working
        self.mock_do_request.return_value = {}

    @property
    def mock_do_request(self):
        return self._client._do_request

    def assert_last_mock_call(self, endpoint, data=None, params=None,
                              expected_status_code=200, stream=False,
                              expected_method='get'):
        if not params:
            params = {}

        _, kwargs = self.mock_do_request.call_args_list[-1]

        called_endpoint = kwargs['request_url'].rpartition('v3.1')[2]
        assert endpoint == called_endpoint

        assert data == kwargs['body']
        assert params == kwargs['params']
        assert expected_status_code == kwargs['expected_status_code']
        assert stream == kwargs['stream']

        assert expected_method == kwargs['requests_method'].__name__

    @property
    def last_mock_call_headers(self):
        return self.mock_do_request.call_args_list[-1][1]['headers']

    def check_last_auth_headers(self, auth=None, token=None):
        expected = {
            constants.CLOUDIFY_EXECUTION_TOKEN_HEADER: None,
            constants.CLOUDIFY_AUTHENTICATION_HEADER: auth,
            constants.CLOUDIFY_TOKEN_AUTHENTICATION_HEADER: token,
        }

        # We don't just do a set because content-type (and other headers) may
        # be on valid requests
        for header in expected:
            if expected[header] is not None:
                assert self.last_mock_call_headers[header] == expected[header]
            else:
                assert header not in self.last_mock_call_headers
