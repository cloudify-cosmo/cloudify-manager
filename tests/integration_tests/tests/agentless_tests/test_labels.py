import uuid
import pytest

from integration_tests.tests import utils
from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
class DeploymentsLabelsTest(AgentlessTestCase):
    def test_deployment_update_with_labels(self):
        deployment = self._create_deployment_from_blueprint_with_labels()
        new_blueprint_id = 'update_labels'
        dsl_path = utils.get_resource('dsl/updated_blueprint_with_labels.yaml')
        blueprint = self.client.blueprints.upload(dsl_path, new_blueprint_id)
        dep_up = self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id, new_blueprint_id)
        self.wait_for_execution_to_end(
            self.client.executions.get(dep_up.execution_id))
        updated_deployment = self.client.deployments.get(deployment.id)
        deployment_labels_list = [{'key1': 'key1_val1'},
                                  {'key2': 'key2_val1'},
                                  {'key2': 'key2_val2'},
                                  {'key2': 'updated_key2_val1'},
                                  {'updated_key': 'updated_key_val1'},
                                  {'updated_key': 'updated_key_val2'}]
        blueprint_labels_list = [{'bp_key1': 'updated_bp_key1_val1'},
                                 {'bp_key2': 'bp_key2_val1'},
                                 {'bp_key2': 'updated_bp_key2_val2'},
                                 {'updated_bp_key': 'updated_bp_key_val1'}]
        self.assert_labels(blueprint['labels'], blueprint_labels_list)
        self.assert_labels(updated_deployment.labels, deployment_labels_list)

    def _create_deployment_from_blueprint_with_labels(self, new_labels=None):
        dsl_path = utils.get_resource('dsl/blueprint_with_labels.yaml')
        blueprint_id = deployment_id = 'd{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        deployment = self.client.deployments.create(blueprint_id,
                                                    deployment_id,
                                                    labels=new_labels)
        utils.wait_for_deployment_creation_to_complete(self.env.container_id,
                                                       deployment_id,
                                                       self.client)
        return deployment
