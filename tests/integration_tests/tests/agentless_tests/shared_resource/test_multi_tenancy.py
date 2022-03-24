import pytest
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_premium


class TestMultiTenantSharedResource(AgentlessTestCase):
    def test_install_shared_resource(self):
        tenant_name = 't2'
        shared_resource_bp_id = 'shared-resource-bp'
        shared_resource_path = self.make_yaml_file("""
tosca_definitions_version: cloudify_dsl_1_3
imports:
  - cloudify/types/types.yaml
""")
        client_blueprint_path = self.make_yaml_file(f"""
tosca_definitions_version: cloudify_dsl_1_3
imports:
  - cloudify/types/types.yaml
node_templates:
  resource_deployment:
    type: cloudify.nodes.ServiceComponent
    properties:
      client:
        host: 127.0.0.1
        username: admin
        password: admin
        tenant: {tenant_name}
        protocol: https
        trust_all: true
      resource_config:
        blueprint:
          external_resource: true
          id: {shared_resource_bp_id}
        deployment:
          id: shared-resource-deployment
""")

        self.client.tenants.create(tenant_name)
        t2_client = self.create_rest_client(tenant='t2')
        t2_client.blueprints.upload(
            shared_resource_path, shared_resource_bp_id)
        wait_for_blueprint_upload(shared_resource_bp_id, t2_client)

        self.deploy_application(client_blueprint_path)
