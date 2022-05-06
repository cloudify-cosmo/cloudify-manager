import pytest
from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_service_composition


class TestOnDemandSharedResource(AgentlessTestCase):
    def setUp(self):
        super(TestOnDemandSharedResource, self).setUp()
        test_blueprint = """
    tosca_definitions_version: cloudify_dsl_1_4

    imports:
      - cloudify/types/types.yaml

    node_templates:
      shared_resource_node:
        type: cloudify.nodes.SharedResource
        properties:
          resource_config:
            deployment:
                id: infra

    outputs:
      test:
        value: { get_capability: [ { get_attribute: [ shared_resource_node,  deployment, id ] }, host_private_ip ] }
    """  # NOQA
        self.test_blueprint_path = self.make_yaml_file(test_blueprint)

    def _create_on_demand_shared_resource_deployment(self):
        blueprint = """
    tosca_definitions_version: cloudify_dsl_1_4

    imports:
      - cloudify/types/types.yaml

    node_templates:
      vm:
        type: cloudify.nodes.Compute
        properties:
          ip: 127.0.0.1
          agent_config:
            user: root
            install_method: none

    capabilities:
        host_private_ip:
           value: { get_attribute: [ vm, ip ] }

    labels:
      csys-obj-type:
        values:
          - on-demand-resource
    """
        blueprint_path = self.make_yaml_file(blueprint)
        self.deploy(blueprint_path, deployment_id='infra')

    def _validate_deployment_installation_status(self, deployment_id, status):
        self.assertEqual(
            self.client.deployments.get(deployment_id).installation_status,
            status
        )

    def _validate_consumers_list(self, deployment_id, consumers_list):
        dep_labels = self.client.deployments.get(deployment_id).labels
        consumer_labels = {lb.value for lb in dep_labels
                           if lb.key == 'csys-consumer-id'}
        self.assertEqual(consumer_labels, set(consumers_list))

    def test_on_demand_shared_resource(self):
        self.logger.info('deploy (but not install) shared resource `infra`')
        self._create_on_demand_shared_resource_deployment()
        self._validate_deployment_installation_status('infra', 'inactive')
        self._validate_consumers_list('infra', [])

        self.logger.info(
            'install 1st consumer -- infra should be now installed')
        self.deploy_application(self.test_blueprint_path,
                                deployment_id='consumer1')
        self._validate_deployment_installation_status('infra', 'active')
        self._validate_consumers_list('infra', ['consumer1'])

        self.logger.info('install 2nd consumer')
        self.deploy_application(self.test_blueprint_path,
                                deployment_id='consumer2')
        self._validate_deployment_installation_status('infra', 'active')
        self._validate_consumers_list('infra', ['consumer1', 'consumer2'])

        self.logger.info(
            'uninstall 1st consumer -- infra should stay installed')
        self.execute_workflow('uninstall', 'consumer1')
        self._validate_deployment_installation_status('infra', 'active')
        self._validate_consumers_list('infra', ['consumer2'])

        self.logger.info(
            'uninstall 2nd consumer -- infra should now be uninstalled')
        self.execute_workflow('uninstall', 'consumer2')
        executions = self.client.executions.list(
            deployment_id='infra', workflow_id='uninstall')
        self.assertEqual(len(executions), 1)
        self.wait_for_execution_to_end(executions[0])
        self._validate_deployment_installation_status('infra', 'inactive')
        self._validate_consumers_list('infra', [])
