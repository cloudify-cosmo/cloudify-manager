import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils
from integration_tests.tests.utils import get_resource as resource


pytestmark = pytest.mark.group_deployments


class IntrinsicFunctionsTest(AgentlessTestCase):
    BLUEPRINT_PATH = resource('dsl/blueprint_string_functions.yaml')
    BLUEPRINT_ID = 'bp'
    DEPLOYMENT_ID = 'dep'
    INPUTS = {'a_haystack': 'Lorem ipsum dolor sit amet',
              'a_needle': 'o',
              'a_replacement': '0',
              'an_index': 0}

    def test_basic(self):
        deployment = self.deploy(
            self.BLUEPRINT_PATH,
            blueprint_id=self.BLUEPRINT_ID,
            deployment_id=self.DEPLOYMENT_ID,
            runtime_only_evaluation=True,
            inputs=self.INPUTS)
        execution = self.execute_workflow('install', deployment.id)
        self.wait_for_execution_to_end(execution)

        caps = self.client.deployments.capabilities.get(self.DEPLOYMENT_ID)
        assert caps['capabilities'] == {
            'x_found_string_index': 1,
            'x_replaced_string': 'L0rem ipsum d0l0r sit amet',
            'x_lower_string': 'lorem ipsum dolor sit amet',
            'x_upper_string': 'LOREM IPSUM DOLOR SIT AMET',
            'x_split_string': 'L',
            'x_a_list': ['L', 'rem ipsum d', 'l', 'r sit amet']}

        execution = self.execute_workflow('uninstall', deployment.id)
        self.wait_for_execution_to_end(execution)
        self.client.deployments.delete(deployment.id)
        utils.wait_for_deployment_deletion_to_complete(
            deployment.id, self.client)
        self.client.blueprints.delete(self.BLUEPRINT_ID)

    def test_invalid_types(self):
        invalid_inputs = self.INPUTS.copy()
        invalid_inputs.update({'a_haystack': ['L', 'o', 'r', 'e', 'm']})
        deployment = self.deploy(
            self.BLUEPRINT_PATH,
            blueprint_id=self.BLUEPRINT_ID,
            deployment_id=self.DEPLOYMENT_ID,
            runtime_only_evaluation=True,
            inputs=invalid_inputs)
        execution = self.execute_workflow('install', deployment.id)
        self.wait_for_execution_to_end(execution)

        caps = self.client.deployments.capabilities.get(self.DEPLOYMENT_ID)
        assert caps['capabilities'] == {
            'x_found_string_index': 1,
            'x_replaced_string': 'L0rem ipsum d0l0r sit amet',
            'x_lower_string': 'lorem ipsum dolor sit amet',
            'x_upper_string': 'LOREM IPSUM DOLOR SIT AMET',
            'x_split_string': 'L',
            'x_a_list': ['L', 'rem ipsum d', 'l', 'r sit amet']}

        execution = self.execute_workflow('uninstall', deployment.id)
        self.wait_for_execution_to_end(execution)
        self.client.deployments.delete(deployment.id)
        utils.wait_for_deployment_deletion_to_complete(
            deployment.id, self.client)
        self.client.blueprints.delete(self.BLUEPRINT_ID)
