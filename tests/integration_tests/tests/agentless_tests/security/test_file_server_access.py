import pytest
import requests

from cloudify_cli.env import get_auth_header
from manager_rest.constants import DEFAULT_TENANT_ROLE

from integration_tests import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_premium


class ResourcesAvailableTest(AgentlessTestCase):

    def test_resources_access(self):
        self.client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                      entity_id='blu')
        self.client.users.create(username='u',
                                 password='password',
                                 role=USER_ROLE)
        self.client.tenants.create(tenant_name='t')
        self.client.tenants.add_user(username='u',
                                     tenant_name='t',
                                     role=DEFAULT_TENANT_ROLE)
        tenant_t_client = self.create_rest_client(tenant='t')
        tenant_t_client.blueprints.upload(resource('dsl/empty_blueprint.yaml'),
                                          entity_id='blu')

        # admin can access both blueprints
        admin_headers = self.client._client.headers
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=200)

        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/t/blu/empty_blueprint.yaml',
            expected_status_code=200)

        # user u can only access blueprints in tenant t
        user_headers = get_auth_header('u', 'password')
        # valid access
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/t/blu/empty_blueprint.yaml',
            expected_status_code=200)

        # invalid - trying to access unauthorized tenant
        self._assert_request_status_code(
            headers=user_headers,
            path='/blueprints/default_tenant/blu/empty_blueprint.yaml',
            expected_status_code=403)

        # trying to access non-existing resource
        self._assert_request_status_code(
            headers=admin_headers,
            path='/blueprints/t/blu/fake_resource_that_does_not_exist',
            expected_status_code=requests.status_codes.codes.not_found)

    def _assert_request_status_code(self,
                                    headers,
                                    path,
                                    expected_status_code):
        response = requests.get(
            'https://{0}:53333/resources{1}'.format(self.get_manager_ip(),
                                                    path),
            headers=headers,
            verify=False
        )
        assert expected_status_code == response.status_code
