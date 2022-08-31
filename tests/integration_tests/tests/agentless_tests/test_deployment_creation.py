import uuid
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDeploymentCreation(AgentlessTestCase):
    def _upload_blueprint(self):
        dsl_path = utils.get_resource('dsl/basic.yaml')
        blueprint_id = 'd{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        utils.wait_for_blueprint_upload(blueprint_id, self.client)
        return blueprint_id

    def test_deployment_with_the_same_id(self):
        """Create multiple deployments with the same ID.

        The goal of this test is run multiple create/delete deployment cycles
        to find out if there's any race condition that prevents the creation of
        a deployment of the same ID just after it's been deleted.

        """
        deployment_id = blueprint_id = self._upload_blueprint()

        deployments_count = 10
        for _ in range(deployments_count):
            self.client.deployments.create(
                blueprint_id, deployment_id, skip_plugins_validation=True)
            utils.wait_for_deployment_creation_to_complete(
                 self.env.container_id,
                 deployment_id,
                 self.client
            )
            self.client.deployments.delete(deployment_id)
            utils.wait_for_deployment_deletion_to_complete(
                deployment_id, self.client
            )

    def test_deployment_create_with_overrides(self):
        blueprint_id = self._upload_blueprint()

        string_template = 'this_is_a_test_{}'
        string_params = ['visibility', 'description', 'display_name']
        dict_params = ['inputs', 'policy_triggers', 'policy_types', 'outputs',
                       'capabilities', 'scaling_groups', 'resource_tags']
        kwargs = {
            "created_at": "2022-08-31T09:47:13.712Z",
            "created_by": "admin",
            "installation_status": "active",
            "deployment_status": "good",
            "workflows": [{"name": "install", "plugin": "abc",
                           "operation": "something", "parameters": {},
                           "is_cascading": False, "is_available": True,
                           "availability_rules": None}],
            "runtime_only_evaluation": False,
            "labels": [],
        }
        for string_param in string_params:
            kwargs[string_param] = string_template.format(string_param)
        for dict_param in dict_params:
            kwargs[dict_param] = {
                string_param: string_template.format(string_param)}

        self.client.deployments.create(
            blueprint_id,
            deployment_id=blueprint_id,
            skip_plugins_validation=True,
            # Empty workdir zip
            _workdir_zip='UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA==',
            **kwargs
        )

        dep = self.client.deployments.get(blueprint_id)

        for param in kwargs:
            assert dep[param] == kwargs[param]
